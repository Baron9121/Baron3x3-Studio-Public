"""Versioned scenario handoff and deterministic pre-render review. Local only."""
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def bind(root, job, scenario, instructions):
    source = Path(scenario).expanduser().resolve()
    source.relative_to((root / 'instructions/scenarios').resolve())
    text = source.read_text(encoding='utf-8')
    if not text.strip():
        raise ValueError('Scenariusz jest pusty.')
    directory = root / 'analysis' / job / 'workflow'
    directory.mkdir(parents=True, exist_ok=True)
    data = {'source': str(source), 'sha256': digest(text), 'text': text, 'baseInstructions': instructions}
    (directory / 'scenario-binding.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
    (directory / 'scenario-snapshot.md').write_text(text, encoding='utf-8')
    return instructions + '\n\n## Scenariusz z czatu — pełny brief\n\n' + text


def check_scenario(root, job):
    path = root / 'analysis' / job / 'workflow/scenario-binding.json'
    if path.exists():
        data = read(path)
        source = Path(data['source'])
        if not source.is_file() or digest(source.read_text(encoding='utf-8')) != data['sha256']:
            raise ValueError('Scenariusz zmienił się lub zniknął. Użyj reel:refresh-scenario; ponownie sprawdź historię i reżyserię.')


def review_data(root, job, plan):
    catalog_path = root / 'analysis/assets/catalog.json'
    catalog = {x['id']: x for x in read(catalog_path)['items']} if catalog_path.exists() else {}
    materials = []
    for overlay in plan.get('overlays', []):
        asset = catalog.get(overlay.get('assetId'), {})
        item = {'overlay': overlay, 'name': asset.get('name', 'BRAK W KATALOGU'), 'path': asset.get('absolutePath'), 'kind': asset.get('kind')}
        if 'matte-photos/' in str(asset.get('absolutePath', '')):
            name = Path(asset['absolutePath']).stem
            directory = root / 'analysis/matte-photos' / name
            for key, filename in [('selection', 'selection.json'), ('profiles', 'props.json'), ('photoSoundEffects', 'sound-effects-relative.json')]:
                if not (directory / filename).exists():
                    raise ValueError(f'Brak metadanych animacji: {directory / filename}')
                item[key] = read(directory / filename)
            item['photos'] = [{'assetId': aid, 'name': catalog.get(aid, {}).get('name', 'BRAK W KATALOGU'), 'path': catalog.get(aid, {}).get('absolutePath')} for aid in item['selection']['assetIds']]
            duration = overlay['timelineEndMs'] - overlay['timelineStartMs']
            if abs(duration - item['selection']['durationMs']) > 1 or overlay.get('sourceStartMs', 0) != 0:
                raise ValueError('Animacja zdjęć musi zachować cały czas i początek źródła.')
        materials.append(item)
    return {'job': job, 'plan': plan, 'materials': materials}


def write_review(root, job, plan):
    data = review_data(root, job, plan)
    directory = root / 'analysis' / job / 'director'
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f'# Plan rolki przed renderem — {job}', '', 'Czasy pochodzą z planu po transkrypcji. To specyfikacja do oceny, nie podgląd obrazu.', '', '## Cięcia nagrania i kadr', '', '| Oś rolki ms | Źródło IN–OUT ms | Kadr / zoom / pozycja |', '|---|---|---|']
    cursor = 0
    for cut in plan.get('sourceRanges', []):
        duration = cut['sourceEndMs'] - cut['sourceStartMs']
        framing = {k: v for k, v in cut.items() if k not in ('sourceStartMs', 'sourceEndMs')}
        lines.append(f"| {cursor}–{cursor+duration} | {cut['sourceStartMs']}–{cut['sourceEndMs']} | {json.dumps(framing, ensure_ascii=False)} |")
        cursor += duration
    lines += ['', '## Ujęcia, zdjęcia i animacje', '']
    for item in data['materials']:
        o = item['overlay']
        end = o.get('sourceStartMs', 0) + o['timelineEndMs'] - o['timelineStartMs']
        lines += [f"### {o.get('assetId', o.get('assetFile'))} — {item['name']}", f"Oś: {o['timelineStartMs']}–{o['timelineEndMs']} ms; źródło IN–OUT: {o.get('sourceStartMs', 0)}–{end} ms (dla wideo).", f"Plik: {item['path']}", '```json', json.dumps(o, ensure_ascii=False, indent=2), '```']
        if 'photos' in item:
            lines += ['Zdjęcia w kolejności, profile ruchu i dźwięk animacji:', '```json', json.dumps({k: item[k] for k in ('selection', 'photos', 'profiles', 'photoSoundEffects')}, ensure_ascii=False, indent=2), '```']
    for field in ('storyPlan', 'captionStyle', 'visualBeats', 'effectCues', 'soundEffects'):
        lines += ['', f'## {field}', '```json', json.dumps(plan.get(field), ensure_ascii=False, indent=2), '```']
    lines += ['', f'Łączny czas wypowiedzi po cięciach: {cursor/1000:.3f} s.', 'Braki i uzasadnienia semantyczne: proposal.md. Porównaj też ze scenario-snapshot.md.']
    (directory / 'review-plan.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
    (directory / 'review-plan.md').write_text('\n'.join(lines), encoding='utf-8')
    return digest(data)


def check_review(root, job, plan, expected):
    if not expected or digest(review_data(root, job, plan)) != expected:
        raise ValueError('Plan lub metadane zdjęć zmieniły się od przeglądu. Przygotuj i zaakceptuj nową reżyserię przed renderem.')
