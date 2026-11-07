import argparse,json,subprocess,tempfile,os
from pathlib import Path
from PIL import Image,ImageOps
p=argparse.ArgumentParser();p.add_argument('photos',type=Path);p.add_argument('--public',type=Path,required=True);a=p.parse_args()
files=sorted(f for f in a.photos.iterdir() if f.suffix.lower() in ['.jpg','.jpeg','.png','.webp'])
if not files: p.error('No photos found')
a.public.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=a.public) as tmp:
 stage=Path(tmp);entries=[]
 for i,src in enumerate(files):
  name=f'{i+1:03}.png'
  with Image.open(src) as im:ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(720,1280),method=Image.Resampling.LANCZOS).save(stage/name)
  entry={'src':f'flexible-photos/{name}'}
  if i>0 and (i-1)%4==0:
   cut=f'{i+1:03}-cutout.png'
   subprocess.run(['swift',str(Path(__file__).with_name('cutout.swift')),str(stage/name),str(stage/cut)],check=True)
   entry['cutout']=f'flexible-photos/{cut}'
  entries.append(entry)
 out=a.public/'flexible-photos';out.mkdir(exist_ok=True)
 for f in stage.iterdir():os.replace(f,out/f.name)
 (a.public/'flexible-photos.json').write_text(json.dumps({'photos':entries},indent=2))
print(f'Prepared {len(entries)} photos')
