"""Technical end-to-end test using generated media, never human approval."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from studio.core import ROOT, write, read, sha, run, validate, save_version
from studio.cli import main, approve_plan, approve_preview
from studio.render import render

def smoke(destination):
    p=destination.resolve()
    if p.exists(): raise ValueError('Choose a new smoke directory')
    for f in ('work','wynik','przebitki','audio'): (p/f).mkdir(parents=True,exist_ok=True)
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=1080x1920:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
         '-t','8','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-shortest',p/'aroll.mp4'])
    write(p/'work/project.json',{'source':'aroll.mp4','source_sha256':sha(p/'aroll.mp4')})
    main(['prepare',str(p)])
    words=[{'text':t,'start':i*.5+.1,'end':i*.5+.45,'confidence':1} for i,t in enumerate(['Test','Baron','3x3.','Siedemnaście','punktów','Francji.'])]
    write(p/'work/words.raw.json',{'words':words,'source_sha256':sha(p/'work/aroll.normalized.mp4')})
    write(p/'poprawki_slow.json',{})
    main(['suggest-cuts',str(p)]);main(['approve-cuts',str(p),'--ids','none','--note','SYNTHETIC TEST ONLY']);main(['cut',str(p)]);main(['plan',str(p)])
    from PIL import Image
    Image.new('RGB',(1080,1920),(20,40,28)).save(p/'przebitki/test.jpg')
    (p/'zdjecia').mkdir()
    for i,color in enumerate([(160,40,30),(30,60,160)]): Image.new('RGB',(1440,1800),color).save(p/f'zdjecia/{i}.jpg')
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:sample_rate=48000','-t','8',p/'audio/music.wav'])
    plan=read(p/'plan.json');plan['elements'] += [
        {'id':'Z01','type':'zoom','start':0,'end':1.5,'scale_from':1,'scale_to':1.08},
        {'id':'B01','type':'broll','kind':'image','start':1.5,'end':3.8,'source':'przebitki/test.jpg','scale_from':1,'scale_to':1.05},
        {'id':'P01','type':'photo','start':4,'end':7.6,'photos':[{'source':'zdjecia/0.jpg'},{'source':'zdjecia/1.jpg','face':[.5,.3],'contain':False,'zoom':1.1}]},
        {'id':'M01','type':'music','start':0,'end':8,'source':'audio/music.wav','volume':.05,'fade_seconds':.2}]
    write(p/'plan.json',plan);save_version(p,plan,{'Z01','B01','P01','M01'})
    approve_plan(p,'SYNTHETIC TEST ONLY');render(p);approve_preview(p,'SYNTHETIC TEST ONLY');render(p,True)
    print('SMOKE PASS:',p/'wynik/FINAL.mp4')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);args=parser.parse_args();smoke(args.destination)
