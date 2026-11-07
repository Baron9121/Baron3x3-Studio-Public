"""Sound effects by fixed rules from config/dzwieki.json: a whoosh when the picture jumps from the face
to a b-roll block, other effects at the times the agent picks. Speech always stays on top."""
from __future__ import annotations
import re
import subprocess
from .core import ROOT, read, write, run

def config():
    return read(ROOT/'config/dzwieki.json')

def install(project, effects):
    """Copy the effects into audio/, peak-normalized to -1 dBFS so plan volumes mean the same for every file."""
    (project/'audio').mkdir(exist_ok=True)
    for effect in effects.values():
        target = project/'audio'/effect['plik']
        if target.exists(): continue
        source = ROOT/'assets/sfx'/effect['plik']
        if not source.is_file(): raise ValueError(f'Brak efektu {source}')
        log = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(source), '-af', 'volumedetect', '-f', 'null', '-'], capture_output=True, text=True).stderr
        peak = float(re.search(r'max_volume: (-?[\d.]+) dB', log).group(1))
        run(['ffmpeg', '-v', 'error', '-y', '-i', source, '-af', f'volume={-1-peak:.2f}dB', target])

def block_starts(plan):
    """Cuts where the picture changes from the face to b-roll. MattePhotos bring their own whooshes."""
    picture = sorted((e for e in plan['elements'] if e['type'] in ('broll', 'photo')), key=lambda e: e['start'])
    starts, previous_end = [], None
    for e in picture:
        face_before = previous_end is None or e['start'] - previous_end > .01
        if face_before and e['type'] == 'broll' and e['start'] > .5: starts.append(e['start'])
        previous_end = e['end']
    return starts

def length(project, name):
    from .core import probe
    return probe(project/'audio'/name)['duration']

def add_sounds(project, chosen=()):
    """Append sfx elements to plan.json. `chosen` = [(kind, time)] picked by the agent; they win over
    automatic whooshes closer than the minimum gap. Per-reel limits come from the config."""
    cfg = config(); effects = cfg['efekty']; gap = cfg['odstep_min_s']
    plan = read(project/'plan.json'); duration = plan['aroll']['duration']
    unknown = {k for k, _ in chosen} - effects.keys()
    if unknown: raise ValueError('Nieznane efekty: ' + ', '.join(sorted(unknown)) + '; dostępne: ' + ', '.join(effects))
    install(project, effects)
    by_file = {e['plik']: k for k, e in effects.items()}
    existing = [e for e in plan['elements'] if e['type'] == 'sfx']
    kind_of = lambda e: by_file.get(e['source'].split('/')[-1], 'whoosh')
    taken = [e['start'] + effects[kind_of(e)]['lead'] for e in existing]
    counts = {}
    for e in existing: counts[kind_of(e)] = counts.get(kind_of(e), 0) + 1
    wanted = sorted(chosen, key=lambda x: x[1]) + [('whoosh', t) for t in block_starts(plan)]
    numbers = [int(m.group(1)) for e in plan['elements'] if (m := re.fullmatch(r'S(\d+)', e['id']))]
    added, skipped = [], []
    for kind, t in wanted:
        s = effects[kind]
        reason = (f'limit {s["max"]} na rolkę' if counts.get(kind, 0) >= s['max'] else
                  f'mniej niż {gap:.0f} s od innego dźwięku' if any(abs(t - x) < gap for x in taken) else
                  'poza rolką' if not 0 <= t - s['lead'] < duration - .1 else '')
        if reason:
            skipped.append({'rodzaj': kind, 'czas': round(t, 2), 'powod': reason}); continue
        start = round(t - s['lead'], 3); end = round(min(duration, start + length(project, s['plik'])), 3)
        numbers.append(max(numbers, default=0) + 1)
        plan['elements'].append({'id': f'S{numbers[-1]:02d}', 'type': 'sfx', 'start': start, 'end': end, 'source': f"audio/{s['plik']}",
                                 'volume': s['glosnosc'], 'fade_seconds': .05, 'reason': f'{kind} na {t:.2f} s'})
        taken.append(t); counts[kind] = counts.get(kind, 0) + 1; added.append(plan['elements'][-1]['id'])
    write(project/'plan.json', plan)
    return {'added': added, 'skipped': skipped, 'next': f"validate --pozwol {','.join(added)}" if added else 'bez zmian'}
