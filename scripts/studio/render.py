from __future__ import annotations
import copy
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .core import ROOT, TEMPLATE_ASSETS, read, write, sha, digest, run, probe, local, validate, receipt, check_receipt, now

def check_output(meta, plan, final):
    # Length is measured on the video stream: AAC priming/padding makes the container a few frames longer.
    scale=1 if final else .5
    video=meta['video']
    length=float(video.get('duration') or meta['duration']) if video else 0
    if not video or not meta['audio'] or (video['width'],video['height'])!=(int(plan['width']*scale),int(plan['height']*scale)) or abs(length-plan['aroll']['duration'])>2/plan['fps']:
        raise ValueError('Render nie przeszedł kontroli rozmiaru, dźwięku lub długości')

def render(project, final=False):
    start=time.monotonic()
    plan=read(project/'plan.zatwierdzony.json')
    validate(plan,project)
    fp=check_receipt(project,plan)
    if final:
        approved=read(project/'work/preview.approved.json')
        preview=read(project/'work/preview.json')
        if approved['preview']!=preview or preview['fingerprint']!=fp or preview['video_sha256']!=sha(project/'wynik/PODGLAD.mp4'):
            raise ValueError('Brak aktualnej akceptacji podglądu')
    output=project/'wynik'; output.mkdir(exist_ok=True)
    target=output/('FINAL.mp4' if final else 'PODGLAD.mp4')
    pending=output/(target.stem+'.pending.mp4')
    with tempfile.TemporaryDirectory(prefix='render-',dir=project/'work') as temp:
        stage=Path(temp); public=stage/'public';public.mkdir()
        mapping={}
        # Only media referenced by the approved plan is exposed to the renderer.
        for i,name in enumerate(fp['media']):
            source=local(project,name); dest=f'media-{i}{source.suffix.lower()}'
            shutil.copy2(source,public/dest)
            if sha(public/dest)!=fp['media'][name]: raise ValueError('Media zmieniły się podczas kopiowania')
            mapping[name]=dest
        for name,digest_ in fp.get('template_media',{}).items():
            source={k:v for group in TEMPLATE_ASSETS.values() for k,v in group.items()}[name]
            (public/name).parent.mkdir(exist_ok=True); shutil.copy2(source,public/name)
            if sha(public/name)!=digest_: raise ValueError('Pliki szablonu zmieniły się podczas kopiowania')
        props=copy.deepcopy(plan);props['aroll']['source']=mapping[plan['aroll']['source']]
        for e in props['elements']:
            if 'source' in e: e['source']=mapping[e['source']]
            for photo in e.get('photos',[]):
                # The template needs the real size to crop around the face anchor.
                video=probe(local(project,photo['source']))['video']
                photo['width'],photo['height']=video['width'],video['height']
                photo['source']=mapping[photo['source']]
        write(stage/'props.json',{'plan':props,'theme':read(ROOT/'config/ustawienia.json')})
        cmd=[ROOT/'node_modules/.bin/remotion','render',ROOT/'remotion/studio/index.tsx','BaronStudio',pending,
             '--props='+str(stage/'props.json'),'--public-dir='+str(public),'--codec=h264','--pixel-format=yuv420p',
             '--crf=18' if final else '--crf=25','--scale=1' if final else '--scale=0.5','--concurrency=2','--overwrite']
        log=project/'work'/('final-render.log' if final else 'preview-render.log')
        with log.open('w') as f: subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    meta=probe(pending)
    check_output(meta,plan,final)
    run(['ffmpeg','-v','error','-xerror','-i',pending,'-f','null','-'])
    if check_receipt(project,plan)!=fp: raise ValueError('Wejście zmienione podczas renderu')
    if digest(read(project/'plan.zatwierdzony.json'))!=digest(plan): raise ValueError('Zatwierdzony plan zmieniony podczas renderu')
    pending.replace(target)
    result={'fingerprint':fp,'video_sha256':sha(target),'created_at':now(),'seconds':round(time.monotonic()-start,2),
            'technical_qa':'passed','editorial_qa':'requires human viewing and listening','metadata':meta}
    write(project/'work'/('final.json' if final else 'preview.json'),result)
    if final:
        from .stock import attributions
        result['stock']=len(attributions(project,plan))
    contact_sheet(project,target)
    return result

def contact_sheet(project,video):
    from PIL import Image, ImageDraw
    duration=probe(video)['duration']; frames=[]
    for i in range(9):
        t=duration*i/9; p=project/'work'/f'qa-{i}.jpg'
        run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',video,'-frames:v','1','-vf','scale=216:384',p])
        im=Image.open(p).convert('RGB'); ImageDraw.Draw(im).rectangle((0,355,216,384),fill='black');ImageDraw.Draw(im).text((8,363),f'{t:.2f}s',fill='white');frames.append(im)
    sheet=Image.new('RGB',(648,1152),'black')
    for i,im in enumerate(frames): sheet.paste(im,((i%3)*216,(i//3)*384))
    sheet.save(project/'wynik'/f'{video.stem}-klatki.jpg')
