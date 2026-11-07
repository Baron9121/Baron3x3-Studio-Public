from __future__ import annotations
import argparse
import copy
import json
import shutil
import sys
import time
import fcntl
from pathlib import Path
from .core import *
from .media import normalize, transcribe, suggest_cuts, approve_cuts, cut, catalog, search_library
from .render import render
from .library import candidates, add_broll
from . import stock
from .sound import add_sounds

CAPTION_CHARS=30

def make_plan(project):
    path=project/'plan.json'
    if path.exists(): raise ValueError('Plan już istnieje; popraw go po ID zamiast regenerować')
    source=project/'work/aroll.mp4'; words=read(project/'work/words.corrected.json')
    if words['source_sha256']!=sha(source): raise ValueError('Czasy napisów pochodzą z innego A-rollu')
    m=probe(source)
    plan={'version':1,'project':project.name,'width':1080,'height':1920,'fps':30,
          'aroll':{'source':'work/aroll.mp4','sha256':sha(source),'duration':m['duration']},'elements':[]}
    group=[]
    def flush():
        if not group: return
        plan['elements'].append({'id':f'C{len(plan["elements"])+1:03d}','type':'caption',
                                'start':group[0]['start'],'end':group[-1]['end'],'words':copy.deepcopy(group)})
        group.clear()
    limit=read(ROOT/'config/ustawienia.json')['captionWords']
    for word in words['words']:
        # Two short lines at most: a new phrase after a pause or when the text would get too long.
        if group and (word['start']-group[-1]['end']>.5 or len(' '.join(w['text'] for w in group+[word]))>CAPTION_CHARS): flush()
        group.append(word)
        if len(group)==limit or word['text'].endswith(('.', '!', '?')): flush()
    flush()
    validate(plan,project); write(path,plan); save_version(project,plan)
    report_plan(project,plan)
    return plan

def report_plan(project, plan):
    words=[w for e in plan['elements'] if e['type']=='caption' for w in e['words']]
    # Stock is a proposal the user may swap for library b-roll, so the report names it per element.
    registry={i['sha256']:i for i in stock.sl.read_json(stock.sl.REGISTRY_JSON,{'items':[]})['items']}
    def origin(e):
        found=[registry.get(sha(project/s)) for s in sources(e) if (project/s).is_file()]
        if e['type'] in ('sfx','music'): return 'dźwięk'
        return ', '.join(f"STOCK {i['provider']}, {i['licenseName']}" for i in found if i) or ('biblioteka' if sources(e) else '')
    lines=['# Plan do akceptacji','',f'Wersja SHA-256: `{digest(plan)}`','', '| ID | Czas | Element | Źródło | Treść wypowiedzi |','|---|---|---|---|---|']
    for e in sorted(plan['elements'],key=lambda e:e['start']):
        quote=' '.join(w['text'] for w in words if w['start']<e['end'] and w['end']>e['start'])
        label=' + '.join(sources(e)) or e.get('text',e['type'])
        lines.append(f'| {e["id"]} | {e["start"]:.2f}–{e["end"]:.2f} | {label.replace("|","/")} | {origin(e)} | {quote.replace("|","/")} |')
    (project/'work/plan.md').write_text('\n'.join(lines)+'\n')

def approve_plan(project,note):
    plan=read(project/'plan.json'); validate(plan,project)
    history=versions(project)
    if not history or read(history[-1])!=plan: raise ValueError('Najpierw validate z listą dozwolonych zmian')
    fp=receipt(project,plan)
    old=project/'plan.zatwierdzony.json'
    if old.exists():
        write(project/'work/approvals'/f'{digest(read(old))}.json',read(old))
    write(old,plan)
    write(project/'work/approval.json',{'fingerprint':fp,'note':note,'at':now()})
    return {'status':'plan zatwierdzony','sha256':digest(plan)}

def approve_preview(project,note):
    plan=read(project/'plan.zatwierdzony.json'); validate(plan,project); fp=check_receipt(project,plan)
    preview=read(project/'work/preview.json')
    if preview['fingerprint']!=fp or preview['video_sha256']!=sha(project/'wynik/PODGLAD.mp4'): raise ValueError('Nieaktualny podgląd')
    write(project/'work/preview.approved.json',{'preview':preview,'note':note,'at':now()})
    return {'status':'podgląd zatwierdzony'}

def status(project):
    checks=[('work/aroll.normalized.mp4','prepare'),('work/words.raw.json','transcribe'),('work/cuts.json','suggest-cuts'),
            ('work/cuts.approved.json','akceptacja cięć'),('work/aroll.mp4','cut'),('plan.json','plan'),
            ('plan.zatwierdzony.json','akceptacja planu'),('wynik/PODGLAD.mp4','preview'),
            ('work/preview.approved.json','akceptacja podglądu'),('wynik/FINAL.mp4','final')]
    result={'project':str(project),'next':next((step for file,step in checks if not (project/file).exists()),'kontrola redakcyjna wyniku')}
    if (project/'plan.zatwierdzony.json').exists():
        try:
            approved=read(project/'plan.zatwierdzony.json'); validate(approved,project); check_receipt(project,approved)
            if read(project/'plan.json')!=approved: result['draft_changed']=True
        except (ValueError,FileNotFoundError) as e: result['next']='ponowna walidacja i akceptacja';result['reason']=str(e)
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description='Baron3x3 Studio — lokalny montaż z trzema akceptacjami')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ['init','prepare','transcribe','suggest-cuts','approve-cuts','cut','catalog','plan','validate','history','restore','approve-plan','preview','approve-preview','final','status','report','kandydaci','dodaj-przebitki','dodaj-zdjecia','stock','stock-motywy','stock-miniatury','dodaj-stock','dzwieki']:
        p=sub.add_parser(name); p.add_argument('project',type=Path)
        if name=='init':
            p.add_argument('--source',type=Path,required=True);p.add_argument('--scenario',type=Path)
        if name=='transcribe': p.add_argument('--model')
        if name=='validate':
            p.add_argument('--pozwol',default='');p.add_argument('--before',type=Path);p.add_argument('--after',type=Path)
        if name=='restore': p.add_argument('version',type=int);p.add_argument('--note',required=True)
        if name.startswith('approve-'): p.add_argument('--note',required=True,help='Zapis jawnej akceptacji użytkownika')
        if name=='approve-cuts': p.add_argument('--ids',required=True,help='K01,K02 albo none')
        if name=='kandydaci':
            p.add_argument('--biblioteka',type=Path);p.add_argument('--zapytanie',default='');p.add_argument('--top',type=int,default=0)
            p.add_argument('--zdjecia',action='store_true',help='Zdjęcia do BaronMattePhotos zamiast klipów wideo')
        if name=='dodaj-przebitki': p.add_argument('ids',nargs='+',help='ID klipów z work/kandydaci.md')
        if name=='stock':
            p.add_argument('zapytanie');p.add_argument('--typ',choices=['video','image'],default='video')
            p.add_argument('--provider',choices=['pexels','commons']);p.add_argument('--limit',type=int,default=20);p.add_argument('--strony',type=int,default=1)
        if name=='stock-motywy':
            p.add_argument('--limit',type=int,default=10,help='Wyników na zapytanie i orientację');p.add_argument('--na-motyw',type=int,default=6)
        if name=='dodaj-stock':
            p.add_argument('ids',nargs='+',help='ID S… z work/stock-kandydaci.md');p.add_argument('--zatwierdzone',action='store_true',help='Użytkownik zaakceptował pobranie')
        if name=='dzwieki': p.add_argument('--efekty',default='',help='rodzaj:czas, np. impact:29.55,swish:12.4,riser:3.1 (config/dzwieki.json)')
        if name=='dodaj-zdjecia': p.add_argument('ids',nargs='+',help='ID zdjęć z work/kandydaci-zdjecia.md')
    p=sub.add_parser('search');p.add_argument('library',type=Path);p.add_argument('query');p.add_argument('--top',type=int,default=10)
    args=parser.parse_args(argv); start=time.monotonic()
    if args.command=='search':
        print(json.dumps(search_library(args.library,args.query,args.top),ensure_ascii=False,indent=2));return
    project=args.project.resolve()
    if args.command=='init':
        if project.exists(): raise ValueError('Folder istnieje; nie nadpisuję projektu')
        if not args.source.is_file(): raise ValueError('Brak źródła')
        for folder in ('work','wynik','przebitki','zdjecia','audio'): (project/folder).mkdir(parents=True,exist_ok=True)
        dest=project/('aroll'+args.source.suffix.lower());shutil.copy2(args.source,dest)
        write(project/'work/project.json',{'source':dest.name,'source_sha256':sha(dest),'created_at':now()})
        write(project/'poprawki_slow.json',{})
        if args.scenario: shutil.copy2(args.scenario,project/'scenariusz.md')
        print(json.dumps(status(project),ensure_ascii=False));return
    if not (project/'work/project.json').exists(): raise ValueError('Najpierw init')
    with (project/'work/.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Inna komenda pracuje nad tym projektem')
        result=execute(args,project)
        with (project/'work/timing.jsonl').open('a') as f:
            f.write(json.dumps({'command':args.command,'seconds':round(time.monotonic()-start,2),'at':now()})+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))

def execute(args,p):
    c=args.command
    if c=='prepare':
        meta=read(p/'work/project.json');source=local(p,meta['source']);target=p/'work/aroll.normalized.mp4'
        cache=p/'work/prepare.json'; fingerprint={'source':sha(source),'preset':'1080x1920-30fps-loudnorm-v2'}
        if cache.exists() and target.exists() and read(cache).get('input')==fingerprint and read(cache).get('output')==sha(target): return {'status':'cache'}
        if versions(p): raise ValueError('Projekt ma plan; utwórz nowy projekt dla zmienionego A-rollu')
        normalize(source,target);write(cache,{'input':fingerprint,'output':sha(target)});return {'status':'przygotowano','metadata':probe(target)}
    if c=='transcribe':
        r=transcribe(p,args.model);return {'words':len(r['words']),'model':r['model']}
    if c=='suggest-cuts':
        r=suggest_cuts(p);return {'proposals':len(r['proposals']),'report':str(p/'work/cuts.md')}
    if c=='approve-cuts':
        approve_cuts(p,[] if args.ids=='none' else args.ids.split(','),args.note);return {'status':'cięcia zatwierdzone'}
    if c=='cut':
        if versions(p): raise ValueError('Plan już istnieje; ponowne cięcie wymaga nowego projektu')
        r=cut(p);return {'words':len(r['words']),'aroll':str(p/'work/aroll.mp4')}
    if c=='kandydaci': return candidates(p,args.biblioteka.resolve() if args.biblioteka else None,args.zapytanie,args.top,args.zdjecia)
    if c=='dodaj-przebitki': return add_broll(p,args.ids)
    if c=='dodaj-zdjecia': return add_broll(p,args.ids,True)
    if c=='stock': return stock.candidates(p,args.zapytanie,args.typ,args.provider,args.limit,args.strony)
    if c=='dzwieki': return add_sounds(p,[(k,float(t)) for k,t in (x.split(':') for x in args.efekty.split(',') if x)])
    if c=='stock-motywy': return stock.motifs(p,args.limit,args.na_motyw)
    if c=='stock-miniatury': return stock.previews(p)
    if c=='dodaj-stock': return stock.add(p,args.ids,args.zatwierdzone)
    if c=='catalog': return {'items':len(catalog(p)),'catalog':str(p/'work/catalog.json')}
    if c=='plan':
        plan=make_plan(p);return {'status':'plan roboczy','elements':len(plan['elements'])}
    if c=='validate':
        plan=read(args.after or p/'plan.json');v=save_version(p,plan,args.pozwol.split(',') if args.pozwol else [],read(args.before) if args.before else None)
        if args.after: write(p/'plan.json',plan)
        report_plan(p,plan);return {'valid':True,'version':str(v)}
    if c=='history': return [str(v) for v in versions(p)]
    if c=='restore':
        history=versions(p); source=p/'work/history'/f'plan_v{args.version:03d}.json'
        if source not in history: raise ValueError('Brak takiej wersji')
        plan=read(source);validate(plan,p)
        write(p/'work/history'/f'plan_v{len(history)+1:03d}.json',plan);write(p/'plan.json',plan)
        write(p/'work/last-restore.json',{'version':args.version,'note':args.note,'at':now()});report_plan(p,plan)
        return {'status':'przywrócono wersję roboczą; akceptacja pozostaje osobna'}
    if c=='approve-plan': return approve_plan(p,args.note)
    if c=='preview': return render(p)
    if c=='approve-preview': return approve_preview(p,args.note)
    if c=='final': return render(p,True)
    if c=='status': return status(p)
    if c=='report': report_plan(p,read(p/'plan.json'));return {'report':str(p/'work/plan.md')}

if __name__=='__main__':
    try: main()
    except (ValueError,FileNotFoundError,subprocess.CalledProcessError) as e:
        print(f'STOP: {e}',file=sys.stderr)
        if isinstance(e,subprocess.CalledProcessError) and e.stderr: print(e.stderr[-2000:],file=sys.stderr)
        sys.exit(2)
