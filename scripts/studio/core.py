from __future__ import annotations
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
IMAGE = {'.jpg','.jpeg','.png','.webp'}
# BaronMattePhotos: timing from remotion/src/matte-photos, textures and sounds stay local (outside Git).
PHOTO_TRANSITION = 12
PHOTO_MIN_STEP = 30
MATTE_ASSETS = {f'matte/{name}': ROOT/'remotion/public/matte-photos'/folder/name for folder,name in
                [('overlays','paper.jpg'),('overlays','scratches.jpg'),('overlays','element.mov'),
                 ('sfx','dragon-whoosh-short.wav'),('sfx','dragon-camera.wav')]}
GRAPHIC_ASSETS = {'graphics/tick.wav': ROOT/'assets/sfx/licznik.wav'}
# Template files each element type needs at render time; they are local and part of the approval fingerprint.
TEMPLATE_ASSETS = {'photo': MATTE_ASSETS, 'graphic': GRAPHIC_ASSETS}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def run(args):
    return subprocess.run([str(a) for a in args], check=True, text=True, capture_output=True).stdout

def probe(path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]))
    videos = [s for s in data['streams'] if s['codec_type'] == 'video']
    return {'duration': float(data['format'].get('duration', 0)),
            'video': videos[0] if videos else None,
            'audio': any(s['codec_type'] == 'audio' for s in data['streams'])}

def local(project, name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts: raise ValueError(f'Ścieżka musi być względna: {name}')
    result = (project / p).resolve()
    if not result.is_relative_to(project.resolve()): raise ValueError(f'Plik poza projektem: {name}')
    if not result.is_file(): raise ValueError(f'Brak pliku: {name}')
    return result

def sources(element):
    return [p['source'] for p in element['photos']] if element['type'] == 'photo' else [element['source']] if 'source' in element else []

def fingerprint(path):
    return {'source': str(path.name), 'sha256': sha(path), 'duration': probe(path)['duration']}

def versions(project):
    return sorted((project / 'work/history').glob('plan_v[0-9]*.json'))

def changes(before, after, allowed):
    """Protect every top-level field, element order, and unlisted element fields."""
    a = {k:v for k,v in before.items() if k != 'elements'}
    b = {k:v for k,v in after.items() if k != 'elements'}
    if a != b: raise ValueError('Zmieniono chronione pola główne planu')
    old = {e['id']:e for e in before['elements']}
    new = {e['id']:e for e in after['elements']}
    common = old.keys() & new.keys()
    if [e['id'] for e in before['elements'] if e['id'] in common] != [e['id'] for e in after['elements'] if e['id'] in common]:
        raise ValueError('Zmiana kolejności istniejących elementów jest zabroniona')
    blocked = []
    for id in old.keys() | new.keys():
        if old.get(id) == new.get(id): continue
        if id in allowed: continue
        if id not in old or id not in new: blocked.append(id); continue
        for key in old[id].keys() | new[id].keys():
            if old[id].get(key) != new[id].get(key) and f'{id}.{key}' not in allowed:
                blocked.append(f'{id}.{key}')
    if blocked: raise ValueError('Niedozwolone zmiany: ' + ', '.join(sorted(blocked)))

def _number(value): return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def check_graphic(e, fps):
    """Graphics are scenes: at least 3 s, with the data their variant needs."""
    if round(e['end']*fps) - round(e['start']*fps) < 3*fps: raise ValueError(f'Plansza krótsza niż 3 s: {e["id"]}')
    d = e['data']; allowed = {'counter': {'value','from','of','label','suffix','land_at'}, 'globe': {'city','country','lat','lon','date','from'}}[e['variant']]
    extra = set(d) - allowed
    if extra: raise ValueError(f'{e["id"]}: nieznane pola {", ".join(sorted(extra))}')
    if 'land_at' in d and not (_number(d['land_at']) and e['start'] < d['land_at'] <= e['end']): raise ValueError(f'{e["id"]}: land_at poza planszą')
    if e['variant'] == 'counter':
        if not all(_number(d.get(k, 0)) for k in ('value','from','of')) or 'value' not in d: raise ValueError(f'{e["id"]}: licznik wymaga liczby value')
    if e['variant'] == 'globe':
        place = lambda x: isinstance(x, dict) and set(x) == {'name','lat','lon'} and isinstance(x['name'], str) and _number(x['lat']) and _number(x['lon']) and -90 <= x['lat'] <= 90 and -180 <= x['lon'] <= 180
        if not (isinstance(d.get('city'), str) and d['city'] and place({'name': d['city'], 'lat': d.get('lat'), 'lon': d.get('lon')})): raise ValueError(f'{e["id"]}: globus wymaga city, lat, lon')
        if 'from' in d and not place(d['from']): raise ValueError(f'{e["id"]}: from = {{name, lat, lon}}')
        if any(k in d and not isinstance(d[k], str) for k in ('country','date')): raise ValueError(f'{e["id"]}: country i date to tekst')

def validate(plan, project, media=True):
    from jsonschema import Draft202012Validator
    errors = sorted(Draft202012Validator(read(ROOT/'schemas/plan.schema.json')).iter_errors(plan), key=lambda e:str(e.path))
    if errors: raise ValueError('; '.join(f'{list(e.path)}: {e.message}' for e in errors[:8]))
    # JSON can contain non-finite numbers when edited by hand.
    digest(plan)
    duration = plan['aroll']['duration']
    fps = plan['fps']
    ids = set()
    tracks = {}
    for e in plan['elements']:
        if e['id'] in ids: raise ValueError(f'Powtórzone ID: {e["id"]}')
        ids.add(e['id'])
        if not 0 <= e['start'] < e['end'] <= duration + 0.001: raise ValueError(f'Błędny czas: {e["id"]}')
        if round(e['end']*fps) <= round(e['start']*fps): raise ValueError(f'Element krótszy od klatki: {e["id"]}')
        if e['type'] in ('zoom','broll','caption','photo','graphic'):
            # Photos and graphics replace the picture like b-roll, so they share one track.
            tracks.setdefault('broll' if e['type'] in ('photo','graphic') else e['type'], []).append(e)
        if e['type'] == 'graphic': check_graphic(e, fps)
        if e['type'] == 'photo':
            frames = round(e['end']*fps) - round(e['start']*fps)
            if frames < 3*fps: raise ValueError(f'Animacja zdjęć krótsza niż 3 s: {e["id"]}')
            if (frames - PHOTO_TRANSITION) / len(e['photos']) < PHOTO_MIN_STEP:
                raise ValueError(f'Za dużo zdjęć na tę długość (min. 1 s na zdjęcie): {e["id"]}')
            if media:
                for name in sources(e):
                    if local(project, name).suffix.lower() not in IMAGE: raise ValueError(f'Zdjęcie musi być JPG/PNG/WebP: {e["id"]}')
        if e['type'] == 'caption':
            prev = e['start']
            for word in e['words']:
                if not e['start'] <= word['start'] < word['end'] <= e['end'] + 0.001 or word['start'] < prev - 0.001:
                    raise ValueError(f'Błędne czasy słów: {e["id"]}')
                prev = word['end']
        if media and 'source' in e:
            p = local(project, e['source'])
            m = probe(p)
            kind = e.get('kind')
            if e['type'] in ('music', 'sfx') and not m['audio']: raise ValueError(f'Brak audio: {e["id"]}')
            if e['type'] == 'broll' and not m['video']: raise ValueError(f'Brak obrazu: {e["id"]}')
            if kind != 'image' and e.get('source_start',0) + e['end']-e['start'] > m['duration'] + 1/fps:
                raise ValueError(f'Za krótki materiał: {e["id"]}')
            if kind == 'image' and p.suffix.lower() not in IMAGE:
                raise ValueError('Obraz musi być JPG/PNG/WebP')
    for track, entries in tracks.items():
        ordered = sorted(entries, key=lambda e:e['start'])
        for a,b in zip(ordered,ordered[1:]):
            if b['start'] < a['end'] - 0.001: raise ValueError(f'Nakładanie {track}: {a["id"]}, {b["id"]}')
    if media:
        p = local(project, plan['aroll']['source'])
        m = probe(p)
        if not m['video'] or not m['audio']: raise ValueError('A-roll musi zawierać obraz i dźwięk')
        if sha(p) != plan['aroll']['sha256']: raise ValueError('A-roll zmieniony: ponownie przygotuj plan')
        if abs(m['duration']-duration) > 1/fps: raise ValueError('Długość A-rollu niezgodna z planem')
    return plan

def save_version(project, plan, allowed=(), before=None):
    validate(plan, project)
    history = versions(project)
    baseline = read(history[-1]) if history else None
    if before is not None:
        if baseline is not None and before != baseline: raise ValueError('Baza musi być ostatnią wersją historii')
        baseline = before
    if baseline is not None: changes(baseline, plan, set(allowed))
    if history and read(history[-1]) == plan: return history[-1]
    target = project/'work/history'/f'plan_v{len(history)+1:03d}.json'
    if target.exists(): raise ValueError('Konflikt historii')
    write(target, plan)
    return target

def template_hash():
    paths = [ROOT/'package-lock.json', ROOT/'config/ustawienia.json', ROOT/'schemas/plan.schema.json',
             *sorted((ROOT/'remotion/studio').glob('*.tsx')),
             *sorted((ROOT/'scripts/studio').glob('*.py'))]
    return digest({str(p.relative_to(ROOT)):sha(p) for p in paths})

def receipt(project, plan):
    names = {plan['aroll']['source'], *[s for e in plan['elements'] for s in sources(e)]}
    result = {'plan':digest(plan), 'template':template_hash(),
              'media':{s:sha(local(project,s)) for s in sorted(names)}}
    needed = {k:p for t in sorted({e['type'] for e in plan['elements']} & TEMPLATE_ASSETS.keys()) for k,p in TEMPLATE_ASSETS[t].items()}
    if needed:
        missing = [str(p) for p in needed.values() if not p.is_file()]
        if missing: raise ValueError('Brak plików szablonu (MattePhotos/plansze): ' + ', '.join(missing))
        result['template_media'] = {k:sha(p) for k,p in sorted(needed.items())}
    return result

def check_receipt(project, plan):
    expected = read(project/'work/approval.json')['fingerprint']
    current = receipt(project,plan)
    if expected != current: raise ValueError('Zmienił się plan, szablon lub media; wymagana nowa akceptacja')
    return current

def now(): return datetime.now(timezone.utc).isoformat()
