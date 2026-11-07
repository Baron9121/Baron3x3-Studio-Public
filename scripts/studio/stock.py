"""Free stock (Pexels, Wikimedia Commons) for a project: the same content rules as the library,
quality limits for the Studio template, a durable license record and attributions for the final."""
from __future__ import annotations
import hashlib
import shutil
import sys
import time
import urllib.error
from pathlib import Path
from .core import ROOT, read, write, sha, probe, run
from .library import classify

sys.path.insert(0, str(ROOT/'scripts'))
import stock_library as sl

MIN_SECONDS = 3.0
MIN_VIDEO = (1080, 1920)
MIN_IMAGE_SIDE = 1080
PREVIEW_BYTES = 8 * 1024 * 1024

def ident(candidate_id):
    return 'S' + hashlib.sha1(candidate_id.encode()).hexdigest()[:6]

def quality(c, kind):
    """Reasons a result cannot be used in a 1080×1920 reel, empty when it can."""
    w, h = c.get('width') or 0, c.get('height') or 0
    if kind == 'video':
        reasons = []
        # Portrait from 1080×1920; landscape only when a 9:16 crop still has 1080 px (height >= 1920, i.e. 4K).
        if h > w and (w < MIN_VIDEO[0] or h < MIN_VIDEO[1]): reasons.append(f'rozdzielczość {w}×{h} < 1080×1920')
        if h <= w and h < MIN_VIDEO[1]: reasons.append(f'poziome {w}×{h}: kadr 9:16 wymaga wysokości 1920 (4K)')
        if w % 2 or h % 2: reasons.append('nieparzyste wymiary')
        if (c.get('durationMs') or 0) < MIN_SECONDS * 1000: reasons.append('krótsze niż 3 s')
        return reasons
    return [] if min(w, h) >= MIN_IMAGE_SIDE else [f'rozdzielczość {w}×{h} < {MIN_IMAGE_SIDE} px']

def search(query, kind, provider, limit, pages=1):
    if provider == 'commons':
        if kind == 'video': raise ValueError('Commons: tylko zdjęcia (filmy są w WebM i poziome); wideo szukaj w Pexels')
        time.sleep(1)  # Commons answers 429 to bursts of queries
        return sl.search_commons(query, kind, limit)
    key = sl.get_pexels_api_key()
    if not key: raise ValueError('Brak klucza Pexels w pęku kluczy (docs/STOCK.md)')
    results, rejected = [], 0
    # Thematic shots (money, flights, flags) are often filmed landscape in 4K, so both orientations are searched.
    for orientation in (['portrait', 'landscape'] if kind == 'video' else ['portrait']):
        for page in range(1, pages + 1):
            found, r = sl.search_pexels(query, kind, limit, key, page=page, orientation_filter=orientation)
            results += found; rejected += r
            if len(found) < limit: break
    return results, rejected

def fold(text):
    return sl.slug(text or '', 10_000).replace('-', ' ')

def names(m):
    return [n for n in [m.get('nazwa'), *m.get('aliasy', [])] if n]

def expand(m, kinds):
    """Queries for a motif: explicit `zapytania`, otherwise templates of its `rodzaj` for the name and each alias."""
    if m.get('zapytania'): return m['zapytania']
    if m.get('rodzaj') not in kinds: raise ValueError(f"{m['id']}: nieznany rodzaj {m.get('rodzaj')!r}; dostępne: {', '.join(kinds)} albo własne `zapytania`")
    rule = kinds[m['rodzaj']]; templates = rule[m.get('typ', 'video')]
    if rule['wymaga_nazwy'] and not names(m): raise ValueError(f"{m['id']}: rodzaj {m['rodzaj']} wymaga `nazwa`")
    queries = [t.format(nazwa=n) for t in templates for n in (names(m) if '{nazwa}' in t else [None])]
    if not queries: raise ValueError(f"{m['id']}: brak szablonów dla typu {m.get('typ', 'video')}")
    return list(dict.fromkeys(queries))

def place_confirmed(c, m):
    """The stock must actually show the named place: its name has to appear in the title, description or source URL."""
    # Commons falls back to the search query as description; that must not count as confirmation.
    desc = '' if c.get('description', '').startswith('Wynik wyszukiwania:') else c.get('description', '')
    hay = fold(' '.join([c.get('title', ''), desc, c.get('sourcePage', ''), c.get('suggestedFilename', '')]))
    return any(f' {fold(n)} ' in f' {hay} ' for n in names(m))

def collect(motifs, limit, pages, per_motif):
    """Search every query of every motif, apply content rules and quality, keep the best per motif."""
    rules = read(ROOT/'config/przebitki.json')
    kinds = read(ROOT/'config/stock.json')['rodzaje']
    registry = {i['id']: i for i in sl.read_json(sl.REGISTRY_JSON, {'items': []})['items']}
    allowed, excluded, rejected, seen = [], [], 0, set()
    errors = []
    for m in motifs:
        kind = m.get('typ', 'video'); provider = m.get('provider') or ('pexels' if kind == 'video' else 'commons')
        m['zapytania'] = expand(m, kinds)
        check_place = not m.get('bez_kontroli_nazwy') and kinds.get(m.get('rodzaj'), {}).get('wymaga_nazwy')
        ranked = []
        for query in m['zapytania']:
            kept = []
            try: results, r = search(query, kind, provider, limit, pages)
            except (urllib.error.URLError, TimeoutError) as e:
                errors.append(f"{m['id']} „{query}”: {e}"); continue
            rejected += r
            for c in results:
                if c['id'] in seen: continue
                seen.add(c['id'])
                entry = {'title': c['title'], 'file': c['suggestedFilename'], 'desc': c.get('description', ''), 'players': '', 'team': '', 'tour': ''}
                # Same content rules as the library: no national teams, no women. Stock has no tournament, so doubts exclude.
                reasons = classify(entry, rules)[0] + quality(c, kind)
                if check_place and not place_confirmed(c, m): reasons.append(f"opis nie potwierdza miejsca: {', '.join(names(m))}")
                c = {**c, 'sid': ident(c['id']), 'motif': m['id'], 'query': query, 'inLibrary': registry.get(c['id'], {}).get('localPath')}
                if reasons: excluded.append({**c, 'reasons': reasons})
                else: kept.append(c)
            ranked.append(kept)
        # Provider order is relevance: interleave the queries rank by rank so each idea gets a place.
        interleaved = [c for rank in range(max(map(len, ranked), default=0)) for kept in ranked if rank < len(kept) for c in [kept[rank]]]
        allowed += interleaved[:per_motif]
    return allowed, excluded, rejected, errors

def report(project, motifs, allowed, excluded, rejected, errors=()):
    write(project/'work/stock-kandydaci.json', {'motifs': motifs, 'rejectedByLicense': rejected, 'candidates': allowed, 'excluded': excluded, 'errors': list(errors)})
    lines = ['# Stock tematyczny', '',
             f'Dopuszczone: **{len(allowed)}**, odrzucone przez reguły lub jakość: **{len(excluded)}**, przez licencję: **{rejected}**.', '',
             'Tytuły stocków są ogólne. Przed wyborem obejrzyj arkusz (`stock-miniatury`): kobieta, reprezentacja, logo lub napis w kadrze wyklucza wynik.', '']
    for m in motifs:
        lines += [f"## {m['id']}: „{m.get('fraza', '')}”", '', f"Zapytania: {', '.join(m['zapytania'])}", '',
                  '| ID | Tytuł | Format | Czas | Autor | Licencja | W bibliotece |', '|---|---|---|---|---|---|---|']
        for c in [c for c in allowed if c['motif'] == m['id']]:
            seconds = f"{c['durationMs']/1000:.1f} s" if c.get('durationMs') else ''
            lines.append(f"| {c['sid']} | {c['title'].replace('|','/')} | {c.get('width')}×{c.get('height')} | {seconds} | {c['author'].replace('|','/')} | {c['licenseName']} | {c['inLibrary'] or ''} |")
        lines.append('')
    if errors:
        lines += ['## Nieudane zapytania (ponów później)', ''] + [f'- {e}' for e in errors] + ['']
    if excluded:
        lines += ['## Odrzucone', ''] + [f"- {c['motif']} {c['title']}: {'; '.join(c['reasons'])}" for c in excluded]
    (project/'work/stock-kandydaci.md').write_text('\n'.join(lines) + '\n')
    return {'motifs': len(motifs), 'allowed': len(allowed), 'excluded': len(excluded), 'rejectedByLicense': rejected, 'errors': len(errors), 'report': str(project/'work/stock-kandydaci.md')}

def candidates(project, query, kind='video', provider=None, limit=20, pages=1):
    """One ad hoc query, reported like a single motif."""
    motifs = [{'id': 'M00', 'fraza': query, 'zapytania': [query], 'typ': kind, 'provider': provider}]
    return report(project, motifs, *collect(motifs, limit, pages, limit * 2))

def motifs(project, limit=10, per_motif=6):
    """Thematic stock for the phrases listed in work/stock-motywy.json (written from the scenario)."""
    path = project/'work/stock-motywy.json'
    if not path.exists(): raise ValueError('Brak work/stock-motywy.json: wypisz motywy ze scenariusza (id, fraza, zapytania, typ)')
    items = read(path)
    ids = [m['id'] for m in items]
    if len(set(ids)) != len(ids): raise ValueError('Motywy muszą mieć unikalne id')
    return report(project, items, *collect(items, limit, 1, per_motif))

def previews(project):
    """Provider previews of the allowed results, one row per motif, for review before any download."""
    from PIL import Image, ImageDraw, ImageFont
    data = read(project/'work/stock-kandydaci.json')
    folder = project/'work/stock'; folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in data['motifs']:
        tiles = []
        for c in [c for c in data['candidates'] if c['motif'] == m['id']]:
            out = folder/f"{c['sid']}.jpg"
            if not out.exists():
                raw = folder/f"{c['sid']}.part"
                sl.download_file(c.get('previewUrl') or c['downloadUrl'], raw, PREVIEW_BYTES)
                run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-vf', 'scale=216:384:force_original_aspect_ratio=decrease', out])
                raw.unlink()
            im = Image.new('RGB', (216, 410), 'black'); th = Image.open(out).convert('RGB')
            im.paste(th, ((216 - th.width)//2, (384 - th.height)//2))
            ImageDraw.Draw(im).text((6, 392), c['sid'] + ('' if c['height'] > c['width'] else ' poziome'), fill='white')
            tiles.append(im)
        if tiles: rows.append((m, tiles))
    if not rows: raise ValueError('Brak dopuszczonych wyników')
    cols = max(len(t) for _, t in rows)
    try: font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 18)
    except OSError: font = None
    sheet = Image.new('RGB', (216*cols, 440*len(rows)), 'black'); draw = ImageDraw.Draw(sheet)
    for r, (m, tiles) in enumerate(rows):
        draw.text((6, 440*r + 6), f"{m['id']}: {m.get('fraza', '')}"[:110], fill='yellow', font=font)
        for i, im in enumerate(tiles): sheet.paste(im, (216*i, 440*r + 30))
    sheet.save(project/'work/stock-kandydaci.jpg')
    return {'previews': sum(len(t) for _, t in rows), 'sheet': str(project/'work/stock-kandydaci.jpg')}

def add(project, ids, approved):
    """Download approved results into the stock library (license record) and copy them into the project."""
    if not approved: raise ValueError('Pobranie stocku wymaga --zatwierdzone po akceptacji użytkownika')
    data = read(project/'work/stock-kandydaci.json')
    by_id = {c['sid']: c for c in data['candidates']}
    missing = [i for i in ids if i not in by_id]
    if missing: raise ValueError('Stock odrzucony lub nieznany: ' + ', '.join(missing))
    copied = []
    for i in ids:
        c = dict(by_id[i]); kind = c['mediaType']
        folder = project/('przebitki' if kind == 'video' else 'zdjecia'); folder.mkdir(exist_ok=True)
        for key in ('sid', 'inLibrary', 'motif'): c.pop(key, None)
        dest = sl.LIBRARY_DIR/c['providerKey']/c['suggestedFilename']
        digest = sha(dest) if dest.is_file() else sl.download_file(c['downloadUrl'], dest)
        c.update({k: v for k, v in sl.probe_download(dest).items() if v is not None})
        if quality(c, kind):
            raise ValueError(f"{i}: pobrany plik nie spełnia wymagań: {'; '.join(quality(c, kind))}")
        sl.register_download(c, dest, digest)
        target = folder/dest.name
        if not target.exists(): shutil.copy2(dest, target)
        copied.append(str(target.relative_to(project)))
    return {'copied': copied, 'licenses': str(sl.REGISTRY_MD)}

def attributions(project, plan):
    """wynik/ATRYBUCJE.md: stock used in the plan, matched by SHA-256 against the license record."""
    from .core import local, sources
    registry = {i['sha256']: i for i in sl.read_json(sl.REGISTRY_JSON, {'items': []})['items']}
    used = []
    for name in sorted({s for e in plan['elements'] for s in sources(e)}):
        item = registry.get(sha(local(project, name)))
        if item: used.append(item)
    path = project/'wynik/ATRYBUCJE.md'
    if not used:
        path.unlink(missing_ok=True); return []
    lines = ['# Materiały stockowe w rolce', '',
             'Podpisy do opisu posta. „Wymagany” oznacza licencję z obowiązkiem uznania autorstwa (CC BY / CC BY-SA).', '']
    for item in used:
        lines.append(f"- {'**Wymagany:** ' if item['licenseRequiresAttribution'] else ''}{item['attribution']} ({item['sourcePage']})")
    path.write_text('\n'.join(lines) + '\n')
    return used
