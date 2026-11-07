"""Prepare a reusable matte slideshow from unique, catalog-selected image IDs."""
import argparse,json,shutil,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def duration_frames(n):
    if n<1: raise ValueError('Wybierz przynajmniej jedno zdjęcie')
    return 60+(n-1)*48

def prepare(name,ids,profiles=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',name): raise ValueError('Nazwa: litery ASCII, cyfry, - lub _')
    ids=list(dict.fromkeys(ids))
    duration=duration_frames(len(ids))
    catalog=json.loads((ROOT/'analysis/assets/catalog.json').read_text())
    lookup={x['id']:x for x in catalog['items']}
    selected=[]
    for asset_id in ids:
        item=lookup.get(asset_id)
        if not item or item.get('kind')!='image' or item.get('status')!='available':
            raise ValueError(f'Niedostępne zdjęcie: {asset_id}')
        path=Path(item['absolutePath'])
        if not path.is_file(): raise ValueError(f'Brak pliku: {asset_id}')
        selected.append((item,path))
    target=ROOT/'remotion/public/matte-photos/jobs'/name
    target.mkdir(parents=True,exist_ok=True)
    props={'photos':[],'photoProfiles':[]}
    for item,path in selected:
        dest=target/(item['id']+path.suffix.lower());shutil.copy2(path,dest)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(dest)]))['streams'][0]
        profile={'face':[.5,.5],'contain':True,'zoom':1,'width':probe['width'],'height':probe['height']}
        profile.update((profiles or {}).get(item['id'],{}))
        props['photos'].append(dest.relative_to(ROOT/'remotion/public').as_posix())
        props['photoProfiles'].append(profile)
    work=ROOT/'analysis/matte-photos'/name;work.mkdir(parents=True,exist_ok=True)
    file=work/'props.json';file.write_text(json.dumps(props,indent=2))
    (work/'selection.json').write_text(json.dumps({'assetIds':ids,'durationInFrames':duration,'durationMs':duration/30*1000,'template':'BaronMattePhotos'},indent=2))
    cues=[{'id':f'{name}-whoosh-{i}', 'type':'dragon-whoosh', 'timelineStartMs':round(((i+1)*48-2)/30*1000), 'volume':.14, 'speechDucking':.72, 'reason':'Przejście do kolejnego zdjęcia w zaakceptowanym pokazie'} for i in range(len(ids)-1)]
    for i in range(len(ids)):
        start=0 if i==0 else i*48-2+21
        end=duration if i==len(ids)-1 else (i+1)*48-2
        for t in range(start,end,11):
            cues.append({'id':f'{name}-camera-{i}-{t}', 'type':'dragon-camera', 'timelineStartMs':round(t/30*1000), 'durationMs':min(11,end-t)/30*1000, 'volume':.12, 'speechDucking':.72, 'reason':'Pętla migawki między whooshami'})
    (work/'sound-effects-relative.json').write_text(json.dumps(cues,indent=2))
    return file

def main():
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--asset-id',action='append',required=True);p.add_argument('--profiles',type=Path);p.add_argument('--render-broll',action='store_true');a=p.parse_args()
    file=prepare(a.name,a.asset_id,json.loads(a.profiles.read_text()) if a.profiles else None)
    print(file)
    if a.render_broll:
        target=ROOT/'assets/library/matte-photos'/f'{a.name}.mp4';target.parent.mkdir(parents=True,exist_ok=True)
        temp=file.parent/'broll-pending.mp4'
        subprocess.run([str(ROOT/'node_modules/.bin/remotion'),'render','remotion/src/index.ts','BaronMattePhotos',str(temp),'--props',str(file),'--codec=h264','--crf=18','--concurrency=2','--overwrite'],cwd=ROOT,check=True)
        shutil.copy2(temp,target)
        subprocess.run(['npm','run','assets:scan'],cwd=ROOT,check=True)
        print(target)
if __name__=='__main__':main()
