from __future__ import annotations
import copy
import json
import re
import shutil
from pathlib import Path
from .core import ROOT, read, write, sha, digest, probe, run, local

VIDEO = {'.mp4','.mov','.mkv','.m4v'}
IMAGE = {'.jpg','.jpeg','.png','.webp'}

def normalize(source, target):
    """Single A/V encoding path; original source is never changed."""
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.stem+'.pending.mp4')
    run(['ffmpeg','-v','error','-y','-i',source,'-map','0:v:0','-map','0:a:0',
         '-vf','setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30',
         '-af','asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000',
         '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
         '-c:a','aac','-b:a','192k','-movflags','+faststart',temp])
    temp.replace(target)

def transcribe(project, model=None):
    from faster_whisper import WhisperModel
    cfg=read(ROOT/'config/ustawienia.json')
    source=project/'work/aroll.normalized.mp4'
    settings={'source':sha(source),'model':model or cfg['whisperModel'],'language':cfg['language'],
              'dictionary':(ROOT/'config/slownik.txt').read_text(),
              'scenario':(project/'scenariusz.md').read_text() if (project/'scenariusz.md').exists() else ''}
    cache=project/'work/words.raw.json'
    if cache.exists() and read(cache).get('fingerprint') == digest(settings): return read(cache)
    audio=project/'work/transcribe.wav'
    run(['ffmpeg','-v','error','-y','-i',source,'-vn','-ac','1','-ar','16000',audio])
    whisper=WhisperModel(settings['model'],device='cpu',compute_type=cfg['computeType'],cpu_threads=4)
    segments,info=whisper.transcribe(str(audio),language=cfg['language'],word_timestamps=True,
                                  initial_prompt=(settings['dictionary']+'\n'+settings['scenario'])[:4000],vad_filter=True)
    words=[]
    for segment in segments:
        for word in segment.words or []:
            if word.end > word.start:
                words.append({'text':word.word.strip(),'start':word.start,'end':word.end,'confidence':word.probability})
    result={'fingerprint':digest(settings),'source_sha256':settings['source'],'model':settings['model'],
            'language':info.language,'words':words}
    write(cache,result)
    return result

def corrected(project):
    words=copy.deepcopy(read(project/'work/words.raw.json')['words'])
    corrections=read(project/'poprawki_slow.json')
    if not isinstance(corrections,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not k or not v for k,v in corrections.items()):
        raise ValueError('poprawki_slow.json musi zawierać mapę tekst → tekst')
    # Longest exact phrase first; preserve original timestamps and punctuation.
    for wrong,right in sorted(corrections.items(),key=lambda p:-len(p[0].split())):
        tokens=wrong.split(); out=[]; i=0
        while i<len(words):
            group=words[i:i+len(tokens)]
            if [w['text'].strip('.,!?;:') for w in group] == tokens:
                tail=re.search(r'[.,!?;:]+$',group[-1]['text'])
                out.append({**group[0],'text':right+(tail.group() if tail else ''),'end':group[-1]['end']})
                i+=len(tokens)
            else: out.append(words[i]); i+=1
        words=out
    return words

def suggest_cuts(project):
    raw=read(project/'work/words.raw.json')
    if raw['source_sha256'] != sha(project/'work/aroll.normalized.mp4'): raise ValueError('Transkrypcja jest nieaktualna')
    words=corrected(project); proposals=[]
    threshold=read(ROOT/'config/ustawienia.json')['silenceSeconds']
    for a,b in zip(words,words[1:]):
        if b['start']-a['end'] > threshold:
            proposals.append({'start':round(a['end']+.15,3),'end':round(b['start']-.15,3),
                              'reason':f'Pauza między „{a["text"]}” i „{b["text"]}”','kind':'pause'})
    # Repeated adjacent words/phrases are suggestions only, never automatic cuts.
    clean=[w['text'].lower().strip('.,!?;:') for w in words]
    for n in (3,2,1):
        for i in range(len(words)-2*n+1):
            if clean[i:i+n] == clean[i+n:i+2*n]:
                proposals.append({'start':words[i]['start'],'end':words[i+n]['start'],
                                  'reason':'Możliwy dubel: '+' '.join(clean[i:i+n]),'kind':'repeat'})
    for i,w in enumerate(words):
        if clean[i] in ('yyy','eee','hmm'):
            proposals.append({'start':w['start'],'end':w['end'],'reason':'Możliwe wtrącenie','kind':'filler'})
    for i,e in enumerate(proposals): e['id']=f'K{i+1:02d}'
    report={'source_sha256':raw['source_sha256'],'transcript_sha256':sha(project/'work/words.raw.json'),
            'corrections_sha256':sha(project/'poprawki_slow.json'),'proposals':proposals,
            'low_confidence':[w for w in words if (w.get('confidence') or 0)<.65],
            'notice':'Propozycje wymagają odsłuchu. Powtórzenie może być zamierzone.'}
    write(project/'work/cuts.json',report)
    lines=['# Cięcia do akceptacji','',report['notice'],'','| ID | Od | Do | Powód |','|---|---:|---:|---|']
    lines += [f'| {p["id"]} | {p["start"]:.3f} | {p["end"]:.3f} | {p["reason"]} |' for p in proposals]
    lines += ['',f'Słowa o niskiej pewności: {len(report["low_confidence"])}. Pełna lista w cuts.json.']
    (project/'work/cuts.md').write_text('\n'.join(lines)+'\n')
    return report

def approve_cuts(project, ids, note):
    report=read(project/'work/cuts.json')
    if report['source_sha256'] != sha(project/'work/aroll.normalized.mp4'): raise ValueError('Nieaktualny raport cięć')
    valid={e['id'] for e in report['proposals']}
    if not set(ids)<=valid: raise ValueError('Nieznane ID cięcia')
    ranges=sorted([e for e in report['proposals'] if e['id'] in ids],key=lambda e:e['start'])
    duration=probe(project/'work/aroll.normalized.mp4')['duration']
    last=0
    for e in ranges:
        if not last<=e['start']<e['end']<=duration: raise ValueError('Cięcia nakładają się lub wykraczają poza materiał')
        last=e['end']
    write(project/'work/cuts.approved.json',{'report':report,'ids':ids,'note':note})

SLACK=.15
MIN_KEPT=.08

def cut(project):
    approval=read(project/'work/cuts.approved.json'); report=approval['report']
    source=project/'work/aroll.normalized.mp4'
    if report != read(project/'work/cuts.json') or report['source_sha256']!=sha(source) or report['transcript_sha256']!=sha(project/'work/words.raw.json') or report['corrections_sha256']!=sha(project/'poprawki_slow.json'):
        raise ValueError('Zmienione wejście cięć; ponów raport i akceptację')
    ranges=sorted([e for e in report['proposals'] if e['id'] in approval['ids']],key=lambda e:e['start'])
    duration=probe(source)['duration']; keep=[]; cursor=0
    ranges=[{**e,'start':round(e['start']*30)/30,'end':round(e['end']*30)/30} for e in ranges]
    # Boundaries the user approved after listening override Whisper's word edges (words are clipped instead).
    heard={round(t,4) for e in ranges if e.get('sprawdzone_na_sluch') for t in (e['start'],e['end'])}
    for e in ranges:
        if e['start']>cursor: keep.append((cursor,e['start']))
        cursor=e['end']
    if cursor<duration: keep.append((cursor,duration))
    if not keep: raise ValueError('Nie można usunąć całej rolki')
    words=[]; offset=0; source_words=corrected(project)
    # A word spanning a removed range may touch two kept segments; keep it only where most of it remains.
    best={}
    for n,w in enumerate(source_words):
        spans=[min(w['end'],e)-max(w['start'],s) for s,e in keep]
        best[n]=max(range(len(keep)),key=lambda k:spans[k])
    for k,(start,end) in enumerate(keep):
        for n,w in enumerate(source_words):
            # Whisper word edges are estimates (often touching, off the 30 fps grid, or ~0.1 s late).
            # A word overlapping a boundary by at most SLACK belongs to the side holding the rest of it;
            # a larger split is a real cut inside a word.
            overlap=min(w['end'],end)-max(w['start'],start)
            if overlap<=0: continue
            if overlap >= w['end']-w['start']-SLACK:
                words.append({**w,'start':max(0,max(w['start'],start)-start+offset),'end':min(w['end'],end)-start+offset})
            elif any(round(b,4) in heard for b,out in ((start,w['start']<start),(end,w['end']>end)) if out):
                if overlap>=MIN_KEPT and best[n]==k:
                    words.append({**w,'start':max(0,max(w['start'],start)-start+offset),'end':min(w['end'],end)-start+offset})
            elif overlap > SLACK:
                raise ValueError(f'Cięcie przecina słowo: {w["text"]}; popraw granicę propozycji')
        offset+=end-start
    target=project/'work/aroll.mp4'
    if not ranges: shutil.copy2(source,target)
    else:
        filters=[]
        for i,(start,end) in enumerate(keep):
            d=end-start; fade=min(.005,d/4)
            filters += [f'[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]',
                        f'[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,afade=t=in:d={fade},afade=t=out:st={d-fade}:d={fade}[a{i}]']
        filters += [''.join(f'[v{i}][a{i}]' for i in range(len(keep)))+f'concat=n={len(keep)}:v=1:a=1[v][a]']
        temp=target.with_name('aroll.pending.mp4')
        run(['ffmpeg','-v','error','-y','-i',source,'-filter_complex',';'.join(filters),'-map','[v]','-map','[a]',
             '-c:v','libx264','-crf','20','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-ar','48000',temp])
        temp.replace(target)
    result={'source_sha256':sha(target),'cuts_sha256':digest(approval),'words':words,'keep':keep}
    write(project/'work/words.corrected.json',result)
    return result

def catalog(project):
    from PIL import Image, ImageDraw
    entries=[]; folder=project/'work/catalog'; folder.mkdir(parents=True,exist_ok=True)
    for p in sorted(p for folder in ('przebitki','zdjecia') if (project/folder).is_dir() for p in (project/folder).rglob('*')):
        if not p.is_file() or p.suffix.lower() not in VIDEO|IMAGE: continue
        rel=str(p.relative_to(project)); local(project,rel)
        h=sha(p); ident=h[:12]; meta=probe(p); frames=[]
        kind='image' if p.suffix.lower() in IMAGE else 'video'
        for i,fraction in enumerate([0] if kind=='image' else [0,.25,.5,.75,.95]):
            t=max(0,min(meta['duration']-.1,meta['duration']*fraction)); out=folder/f'{ident}-{i}.jpg'
            if not out.exists():
                run(['ffmpeg','-v','error','-y',*(['-ss',str(t)] if kind=='video' else []),'-i',p,
                     '-frames:v','1','-vf','scale=216:320:force_original_aspect_ratio=decrease,pad=216:350:(ow-iw)/2:0:color=black',out])
            im=Image.open(out).convert('RGB'); ImageDraw.Draw(im).text((8,327),f'{t:.2f}s',fill='white'); frames.append(im)
        sheet=Image.new('RGB',(216*len(frames),350),'black')
        for i,im in enumerate(frames): sheet.paste(im,(216*i,0))
        sheet.save(folder/f'{ident}.jpg')
        proxy=None
        if kind=='video':
            proxy=folder/f'{ident}.proxy.mp4'
            if not proxy.exists():
                run(['ffmpeg','-v','error','-y','-i',p,'-an','-vf','scale=540:960:force_original_aspect_ratio=decrease,setsar=1,fps=30',
                     '-c:v','libx264','-preset','fast','-crf','24','-pix_fmt','yuv420p',proxy])
        size=[meta['video']['width'],meta['video']['height']] if meta['video'] else None
        entries.append({'id':ident,'source':rel,'sha256':h,'kind':kind,'duration':meta['duration'],'size':size,
                        'sheet':str((folder/f'{ident}.jpg').relative_to(project)),
                        'proxy':str(proxy.relative_to(project)) if proxy else None,'description':'','reviewed':False})
    write(project/'work/catalog.json',entries)
    return entries

def search_library(path, query, top=10):
    tokens=re.findall(r'\w+',query.casefold()); results=[]
    if not tokens: raise ValueError('Puste wyszukiwanie')
    files=[path] if path.is_file() else path.rglob('*.md')
    for p in files:
        content=p.read_text(errors='replace')
        # The global index can be large: rank blocks, not whole files.
        blocks=re.split(r'\n(?=##? |\|)',content) if len(content)>10000 else [content]
        for block in blocks:
            hay=(p.stem+' '+block).casefold(); score=sum(hay.count(t) for t in tokens)
            if score: results.append({'file':str(p),'score':score,'excerpt':block[:1200]})
    return sorted(results,key=lambda r:-r['score'])[:top]
