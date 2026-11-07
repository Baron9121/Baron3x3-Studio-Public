#!/usr/bin/env python3
"""Normalize exactly 10 replacement photos, generate cutouts locally, then publish atomically per file."""
import argparse,subprocess,tempfile,os
from pathlib import Path
from PIL import Image,ImageOps
p=argparse.ArgumentParser()
p.add_argument('photos',type=Path,help='Directory containing 01.jpg … 10.jpg (PNG/WebP also accepted)')
p.add_argument('--public',type=Path,required=True,help='Remotion public directory')
a=p.parse_args()
sources=[]
for i in range(1,11):
 candidates=[a.photos/f'{i:02d}{ext}' for ext in ['.jpg','.jpeg','.png','.webp'] if (a.photos/f'{i:02d}{ext}').is_file()]
 if len(candidates)!=1: p.error(f'Expected exactly one file for slot {i:02d}, found {len(candidates)}')
 sources.append(candidates[0])
out=a.public/'lewy-photos';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='.lewy-',dir=a.public) as temp:
 stage=Path(temp)
 for i,src in enumerate(sources,1):
  with Image.open(src) as im:
   im=ImageOps.exif_transpose(im).convert('RGB')
   im=ImageOps.fit(im,(720,1280),method=Image.Resampling.LANCZOS,centering=(.5,.5))
   im.save(stage/f'{i:02d}.png')
  if i in [2,7]:
   subprocess.run(['swift',str(Path(__file__).with_name('cutout.swift')),str(stage/f'{i:02d}.png'),str(stage/f'{i:02d}-cutout.png')],check=True)
   with Image.open(stage/f'{i:02d}-cutout.png') as cut:
    alpha=cut.getchannel('A');low,high=alpha.getextrema()
    if low==high:raise RuntimeError(f'Slot {i}: segmentation returned no useful transparency')
 # Publish only after every image and both cutouts succeeded.
 for f in stage.iterdir():os.replace(f,out/f.name)
print(f'Ready: {out}. Animation timing remains fixed.')
