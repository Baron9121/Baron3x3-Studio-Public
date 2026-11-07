"""B-roll and photo candidates from the library indexes, filtered by the same rules in config/przebitki.json."""
from __future__ import annotations
import hashlib
import re
import shutil
from pathlib import Path
from .core import ROOT, read, write

SUFFIXES={'video':{'.mp4'},'images':{'.jpg','.jpeg','.png','.webp'}}
FIELDS={'players':'Gracz / Gracze','team':'Zespół','tour':'Turniej','year':'Rok','desc':'Opis akcji'}

def parse_index(library, folder='video'):
    """Entries from README.md, mapped to real files (stored as ID_name.ext or name.ext)."""
    text=(library/'README.md').read_text(errors='replace')
    files=sorted(p.name for p in library.iterdir() if p.suffix.lower() in SUFFIXES[folder])
    entries=[]
    for block in re.split(r'\n(?=## )',text):
        if not block.startswith('## '): continue
        m=re.search(r'> Plik: `'+folder+r'/(.*?)`',block)
        if not m: continue
        name=m.group(1)
        e={'title':block.split('\n',1)[0][3:].strip(),'file':name}
        for key,label in FIELDS.items():
            f=re.search(r'- \*\*'+re.escape(label)+r':\*\* (.*)',block)
            e[key]=f.group(1).strip() if f else ''
        e['matches']=[f for f in files if f==name or f.endswith('_'+name)]
        entries.append(e)
    return entries

def _hits(entry, rules):
    reasons=[]
    for reason,rule in rules.items():
        for field in rule['pola']:
            value=entry.get(field,'')
            if any(re.search(p,value,re.I) for p in rule['wzorce']):
                reasons.append(f'{reason}: {field} „{value[:80]}”')
                break
    return reasons

def classify(entry, rules):
    """(excluded, review): review only for club tournaments, otherwise it excludes."""
    excluded=_hits(entry,rules['wyklucz'])
    doubtful=_hits(entry,rules['sprawdz_w_klubowych'])
    club=any(re.search(p,entry.get('tour',''),re.I) for p in rules['turnieje_klubowe'])
    if not club: excluded+=doubtful; doubtful=[]
    return excluded, doubtful

def ident(name, photos):
    # Several photos share one post ID (…_01.jpg, …_07.jpg), so photos get a short hash of the file name.
    return 'F'+hashlib.sha1(name.encode()).hexdigest()[:6] if photos else name.split('_',1)[0]

def target(photos):
    return ('zdjecia','kandydaci-zdjecia') if photos else ('przebitki','kandydaci')

def candidates(project, library=None, query='', top=0, photos=False):
    rules=read(ROOT/'config/przebitki.json')
    library=(library or ROOT/rules['biblioteka_zdjec' if photos else 'biblioteka']).resolve()
    folder,report_name=target(photos)
    tokens=re.findall(r'\w+',query.casefold())
    allowed=[];excluded=[];ambiguous=[]
    for e in parse_index(library,'images' if photos else 'video'):
        reasons,doubtful=classify(e,rules)
        if reasons:
            excluded.append({**e,'reasons':reasons}); continue
        e['sprawdz']=doubtful
        if len(e['matches'])!=1:
            ambiguous.append(e); continue
        hay=' '.join(e[k] for k in ('title','file','players','team','tour','desc')).casefold()
        e['score']=sum(hay.count(t) for t in tokens)
        e['id']=ident(e['matches'][0],photos)
        allowed.append(e)
    if tokens: allowed.sort(key=lambda e:-e['score'])
    shown=allowed[:top] if top else allowed
    review=sum(bool(e['sprawdz']) for e in allowed)
    report={'library':str(library),'query':query,'allowed':len(allowed),'review':review,'excluded':len(excluded),'ambiguous':len(ambiguous),
            'candidates':shown,'excluded_items':excluded,'ambiguous_items':ambiguous}
    write(project/f'work/{report_name}.json',report)
    lines=['# Kandydaci na zdjęcia' if photos else '# Kandydaci na przebitki','',
           f'Biblioteka: `{library}`. Dozwolone: **{len(allowed)}** (w tym do sprawdzenia: **{review}**), wykluczone: **{len(excluded)}**, bez jednoznacznego pliku: **{len(ambiguous)}**.','',
           'Opisy indeksu są automatyczne. Przed użyciem obejrzyj miniatury: reprezentacja lub koszykarka w kadrze wyklucza klip mimo braku w opisie.','',
           '„Sprawdź” = turniej klubowy, ale opis wspomina reprezentację lub zespół nazwano krajem. Użyj tylko po potwierdzeniu na miniaturach, że grają kluby.','',
           '| ID | Turniej | Zespół | Tytuł | Sprawdź |','|---|---|---|---|---|']
    lines+=[f'| {e["id"]} | {e["tour"]} | {e["team"]} | {e["title"]} | {"; ".join(e["sprawdz"])} |' for e in shown]
    (project/f'work/{report_name}.md').write_text('\n'.join(lines)+'\n')
    return {'allowed':len(allowed),'review':review,'excluded':len(excluded),'ambiguous':len(ambiguous),'shown':len(shown),'report':str(project/f'work/{report_name}.md')}

def add_broll(project, ids, photos=False):
    """Copy only files that passed the filter into the project's przebitki/ or zdjecia/."""
    folder,report_name=target(photos)
    report=read(project/f'work/{report_name}.json')
    library=Path(report['library'])
    rules=read(ROOT/'config/przebitki.json')
    by_id={}
    for e in parse_index(library,'images' if photos else 'video'):
        if len(e['matches'])==1 and not classify(e,rules)[0]: by_id[ident(e['matches'][0],photos)]=e['matches'][0]
    missing=[i for i in ids if i not in by_id]
    if missing: raise ValueError(('Zdjęcie' if photos else 'Klip')+' wykluczone lub nieznane: '+', '.join(missing))
    (project/folder).mkdir(exist_ok=True)
    copied=[]
    for i in ids:
        dest=project/folder/by_id[i]
        if not dest.exists(): shutil.copy2(library/by_id[i],dest)
        copied.append(str(dest.relative_to(project)))
    return {'copied':copied}
