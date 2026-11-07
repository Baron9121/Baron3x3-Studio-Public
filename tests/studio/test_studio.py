import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from studio.core import changes,validate,write,read,sha,receipt,check_receipt,save_version
from studio.cli import approve_plan,approve_preview
from studio.media import corrected,approve_cuts,cut
from studio.render import render, check_output

def plan():
    return {'version':1,'project':'test','fps':30,'width':1080,'height':1920,
        'aroll':{'source':'work/aroll.mp4','sha256':'a'*64,'duration':10},
        'elements':[{'id':'B01','type':'broll','start':0,'end':3,'source':'przebitki/a.mp4','kind':'video'},
                    {'id':'Z01','type':'zoom','start':3,'end':6,'scale_from':1,'scale_to':1.1}]}
class Protection(unittest.TestCase):
    def test_scoped_field_change(self):
        a=plan();b=copy.deepcopy(a);b['elements'][0]['source']='przebitki/b.mp4';changes(a,b,{'B01.source'})
        b['elements'][0]['end']=4
        with self.assertRaises(ValueError):changes(a,b,{'B01.source'})
    def test_unlisted_element(self):
        a=plan();b=copy.deepcopy(a);b['elements'][1]['scale_to']=1.2
        with self.assertRaises(ValueError):changes(a,b,{'B01'})
    def test_global_protected(self):
        a=plan();b=copy.deepcopy(a);b['aroll']['duration']=11
        with self.assertRaises(ValueError):changes(a,b,{'B01','Z01'})
    def test_delete_and_add_need_whole_id(self):
        a=plan();b=copy.deepcopy(a);b['elements'].pop(0)
        with self.assertRaises(ValueError):changes(a,b,{'B01.source'})
        changes(a,b,{'B01'})
        changes(b,a,{'B01'})
    def test_order_is_protected(self):
        a=plan();b=copy.deepcopy(a);b['elements'].reverse()
        with self.assertRaises(ValueError):changes(a,b,{'B01','Z01'})
    def test_schema_timings_unknown_fields(self):
        validate(plan(),Path('.'),False)
        for mutate in [lambda p:p.update(fps=25),lambda p:p['elements'][0].update(end=11),lambda p:p['elements'][0].update(start=2.99,end=3),lambda p:p.update(unknown=True)]:
            p=plan();mutate(p)
            with self.assertRaises(ValueError):validate(p,Path('.'),False)
    def test_stat_card_rejected(self):
        p=plan();p['elements'].append({'id':'P01','type':'stat_card','start':6,'end':8,'text':'17','preset':'number-impact'})
        with self.assertRaises(ValueError):validate(p,Path('.'),False)
    def photo(self,start=6,end=9.4,n=2):
        return {'id':'P01','type':'photo','start':start,'end':end,'photos':[{'source':f'zdjecia/{i}.jpg','face':[.5,.3]} for i in range(n)]}
    def test_photo_animation_is_one_scene_of_at_least_3s(self):
        p=plan();p['elements'].append(self.photo());validate(p,Path('.'),False)
        p=plan();p['elements'].append(self.photo(end=8.9))
        with self.assertRaisesRegex(ValueError,'krótsza niż 3 s'):validate(p,Path('.'),False)
    def test_photos_may_change_faster_but_not_below_1s(self):
        p=plan();p['elements'].append(self.photo(end=9.9,n=3));validate(p,Path('.'),False)
        p=plan();p['elements'].append(self.photo(end=9.9,n=4))
        with self.assertRaisesRegex(ValueError,'min. 1 s'):validate(p,Path('.'),False)
    def test_photo_shares_track_with_broll(self):
        p=plan();p['elements'].append(self.photo(start=2,end=5.5))
        with self.assertRaisesRegex(ValueError,'Nakładanie broll'):validate(p,Path('.'),False)
    def test_receipt_covers_photos_and_matte_textures(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();(p/'przebitki').mkdir();(p/'zdjecia').mkdir();(p/'work/aroll.mp4').write_bytes(b'a');(p/'przebitki/a.mp4').write_bytes(b'b')
            for i in range(2):(p/f'zdjecia/{i}.jpg').write_bytes(b'p%d'%i)
            tex=p/'paper.jpg';tex.write_bytes(b't')
            pl=plan();pl['elements'].append(self.photo())
            with patch.dict('studio.core.TEMPLATE_ASSETS',{'photo':{'matte/paper.jpg':tex}},clear=True):
                r=receipt(p,pl);self.assertIn('zdjecia/1.jpg',r['media']);self.assertIn('matte/paper.jpg',r['template_media'])
                write(p/'work/approval.json',{'fingerprint':r})
                tex.write_bytes(b'changed')
                with self.assertRaises(ValueError):check_receipt(p,pl)
            with patch.dict('studio.core.TEMPLATE_ASSETS',{'photo':{'matte/paper.jpg':p/'missing.jpg'}},clear=True):
                with self.assertRaisesRegex(ValueError,'szablonu'):receipt(p,pl)
    def test_caption_phrase_up_to_8_words(self):
        words=lambda n:[{'text':'słowo','start':i*.3,'end':i*.3+.25} for i in range(n)]
        p=plan();p['elements'].append({'id':'C01','type':'caption','start':6,'end':8.5,'words':[{**w,'start':w['start']+6,'end':w['end']+6} for w in words(6)]})
        validate(p,Path('.'),False)
        p['elements'][-1]['words']=[{**w,'start':w['start']+6,'end':w['end']+6} for w in words(9)]
        with self.assertRaises(ValueError):validate(p,Path('.'),False)
    def test_duplicate_ids(self):
        p=plan();p['elements'].append(copy.deepcopy(p['elements'][0]))
        with self.assertRaises(ValueError):validate(p,Path('.'),False)
    def test_overlap(self):
        p=plan();z=copy.deepcopy(p['elements'][1]);z.update(id='Z02',start=5,end=8);p['elements'].append(z)
        with self.assertRaises(ValueError):validate(p,Path('.'),False)
    def test_word_outside_caption(self):
        p=plan();p['elements'].append({'id':'C01','type':'caption','start':0,'end':1,'words':[{'text':'test','start':0,'end':2}]})
        with self.assertRaises(ValueError):validate(p,Path('.'),False)
    def test_nan(self):
        p=plan();p['elements'][1]['scale_to']=float('nan')
        with self.assertRaises(ValueError):validate(p,Path('.'),False)
    def test_path_escape_and_symlink(self):
        from studio.core import local
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'project';p.mkdir();(root/'secret').write_text('x');(p/'link').symlink_to(root/'secret')
            for name in ['../secret',str(root/'secret'),'link']:
                with self.assertRaises(ValueError):local(p,name)
    def test_receipt_detects_same_duration_media_change(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();(p/'przebitki').mkdir();(p/'work/aroll.mp4').write_bytes(b'a');(p/'przebitki/a.mp4').write_bytes(b'b')
            write(p/'work/approval.json',{'fingerprint':receipt(p,plan())});check_receipt(p,plan())
            (p/'przebitki/a.mp4').write_bytes(b'c')
            with self.assertRaises(ValueError):check_receipt(p,plan())
    def test_receipt_detects_template_change(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();(p/'przebitki').mkdir();(p/'work/aroll.mp4').write_bytes(b'a');(p/'przebitki/a.mp4').write_bytes(b'b')
            write(p/'work/approval.json',{'fingerprint':receipt(p,plan())})
            with patch('studio.core.template_hash',return_value='changed'):
                with self.assertRaises(ValueError):check_receipt(p,plan())
    def test_final_refuses_missing_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            with self.assertRaises(FileNotFoundError):render(p,True)
    def test_history_cannot_use_old_baseline(self):
        with tempfile.TemporaryDirectory() as temp,patch('studio.core.validate'):
            p=Path(temp);a=plan();save_version(p,a);b=copy.deepcopy(a);b['elements'][0]['source']='b';save_version(p,b,{'B01.source'})
            with self.assertRaises(ValueError):save_version(p,a,{'B01.source'},before=a)
    def test_approve_requires_validated_history(self):
        with tempfile.TemporaryDirectory() as temp,patch('studio.cli.validate'):
            p=Path(temp);write(p/'plan.json',plan())
            with self.assertRaises(ValueError):approve_plan(p,'test')
    def test_phrase_corrections_keep_time_and_raw(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);raw={'words':[{'text':'Tiroar','start':1,'end':2},{'text':'Samson.','start':2,'end':3}]}
            write(p/'work/words.raw.json',raw);write(p/'poprawki_slow.json',{'Tiroar Samson':'Thirouard-Samson'})
            out=corrected(p);self.assertEqual(out,[{'text':'Thirouard-Samson.','start':1,'end':3}]);self.assertEqual(read(p/'work/words.raw.json'),raw)
    def test_cut_blocks_stale_report(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);write(p/'work/cuts.approved.json',{'report':{'source_sha256':'a'},'ids':[]});write(p/'work/cuts.json',{'source_sha256':'b'})
            with self.assertRaises(ValueError):cut(p)
if __name__=='__main__': unittest.main()

class MediaIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil
        if not shutil.which('ffmpeg'): raise unittest.SkipTest('FFmpeg required')
    def test_cut_duration_words_and_audio(self):
        from studio.core import run,probe
        from studio.media import suggest_cuts,approve_cuts
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir()
            source=p/'work/aroll.normalized.mp4'
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:size=108x192:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-c:a','aac',source])
            write(p/'work/words.raw.json',{'source_sha256':sha(source),'words':[{'text':'Raz','start':.1,'end':.5},{'text':'Dwa','start':2,'end':2.5}]})
            write(p/'poprawki_slow.json',{})
            r=suggest_cuts(p);self.assertEqual(len(r['proposals']),1)
            approve_cuts(p,['K01'],'SYNTHETIC TEST')
            out=cut(p);m=probe(p/'work/aroll.mp4')
            self.assertTrue(m['audio']);self.assertAlmostEqual(m['duration'],1.8,delta=.05)
            self.assertAlmostEqual(out['words'][1]['start'],.8,delta=.04)
            run(['ffmpeg','-v','error','-xerror','-i',p/'work/aroll.mp4','-f','null','-'])
    def test_cut_at_touching_words_off_frame_grid(self):
        from studio.core import run
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();source=p/'work/aroll.normalized.mp4'
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:size=108x192:rate=30','-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264','-c:a','aac',source])
            write(p/'work/words.raw.json',{'source_sha256':sha(source),'words':[{'text':'A','start':.1,'end':.5},{'text':'B','start':.6,'end':1.01},{'text':'C','start':1.01,'end':1.6}]});write(p/'poprawki_slow.json',{})
            report={'source_sha256':sha(source),'transcript_sha256':sha(p/'work/words.raw.json'),'corrections_sha256':sha(p/'poprawki_slow.json'),'proposals':[{'id':'K01','start':.55,'end':1.01}]}
            write(p/'work/cuts.json',report);approve_cuts(p,['K01'],'SYNTHETIC TEST')
            out=cut(p)
            self.assertEqual([w['text'] for w in out['words']],['A','C'])
            self.assertLess(abs(out['words'][1]['start']-out['words'][0]['end']),.1)
    def test_cut_in_pause_before_late_whisper_boundary(self):
        from studio.core import run
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();source=p/'work/aroll.normalized.mp4'
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:size=108x192:rate=30','-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264','-c:a','aac',source])
            write(p/'work/words.raw.json',{'source_sha256':sha(source),'words':[{'text':'A','start':.1,'end':.4},{'text':'Zwykle','start':.6,'end':1.1},{'text':'chodzi','start':1.1,'end':1.6}]});write(p/'poprawki_slow.json',{})
            report={'source_sha256':sha(source),'transcript_sha256':sha(p/'work/words.raw.json'),'corrections_sha256':sha(p/'poprawki_slow.json'),'proposals':[{'id':'K01','start':.5,'end':1.0}]}
            write(p/'work/cuts.json',report);approve_cuts(p,['K01'],'SYNTHETIC TEST')
            self.assertEqual([w['text'] for w in cut(p)['words']],['A','chodzi'])
    def test_listened_boundary_clips_misaligned_word(self):
        from studio.core import run
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();source=p/'work/aroll.normalized.mp4'
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:size=108x192:rate=30','-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264','-c:a','aac',source])
            words=[{'text':'Tour.','start':.1,'end':.4},{'text':'Zwykle','start':.6,'end':1.0},{'text':'chodzi','start':1.0,'end':1.5}]
            write(p/'work/words.raw.json',{'source_sha256':sha(source),'words':words});write(p/'poprawki_slow.json',{})
            def run_cut(flag):
                prop={'id':'K01','start':.5,'end':1.3}
                if flag: prop['sprawdzone_na_sluch']=True
                write(p/'work/cuts.json',{'source_sha256':sha(source),'transcript_sha256':sha(p/'work/words.raw.json'),'corrections_sha256':sha(p/'poprawki_slow.json'),'proposals':[prop]})
                approve_cuts(p,['K01'],'SYNTHETIC TEST');return cut(p)
            with self.assertRaises(ValueError):run_cut(False)
            out=run_cut(True)
            self.assertEqual([w['text'] for w in out['words']],['Tour.','chodzi'])
            self.assertAlmostEqual(out['words'][1]['end']-out['words'][1]['start'],.2,delta=.04)
    def test_listened_cut_inside_long_word_keeps_it_once(self):
        from studio.core import run
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();source=p/'work/aroll.normalized.mp4'
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:size=108x192:rate=30','-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264','-c:a','aac',source])
            write(p/'work/words.raw.json',{'source_sha256':sha(source),'words':[{'text':'dopiero','start':.1,'end':.5},{'text':'próbują','start':.5,'end':1.6}]});write(p/'poprawki_slow.json',{})
            write(p/'work/cuts.json',{'source_sha256':sha(source),'transcript_sha256':sha(p/'work/words.raw.json'),'corrections_sha256':sha(p/'poprawki_slow.json'),'proposals':[{'id':'K01','start':.7,'end':1.1,'sprawdzone_na_sluch':True}]})
            approve_cuts(p,['K01'],'SYNTHETIC TEST')
            self.assertEqual([w['text'] for w in cut(p)['words']],['dopiero','próbują'])
    def test_cut_inside_word_never_replaces_existing_output(self):
        from studio.core import run, digest
        from studio.media import approve_cuts
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'work').mkdir();source=p/'work/aroll.normalized.mp4'
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:size=108x192:rate=30','-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264','-c:a','aac',source])
            write(p/'work/words.raw.json',{'source_sha256':sha(source),'words':[{'text':'słowo','start':.2,'end':1.5}]});write(p/'poprawki_slow.json',{})
            report={'source_sha256':sha(source),'transcript_sha256':sha(p/'work/words.raw.json'),'corrections_sha256':sha(p/'poprawki_slow.json'),'proposals':[{'id':'K01','start':.5,'end':1}]}
            write(p/'work/cuts.json',report);approve_cuts(p,['K01'],'SYNTHETIC TEST');(p/'work/aroll.mp4').write_bytes(b'previous good output')
            with self.assertRaises(ValueError):cut(p)
            self.assertEqual((p/'work/aroll.mp4').read_bytes(),b'previous good output')

from studio.library import candidates, add_broll
class Library(unittest.TestCase):
    def entry(self,title,name,team,tour,desc='Akcja pod koszem.'):
        return f"## {title}\n\n> Plik: `video/{name}`\n\n- **Gracz / Gracze:** nieustalone\n- **Zespół:** {team}\n- **Turniej:** {tour}\n- **Rok:** 2026\n- **Opis akcji:** {desc}\n\n---\n"
    def test_filters_national_women_and_flags_club_countries(self):
        with tempfile.TemporaryDirectory() as t:
            lib=Path(t)/'video';lib.mkdir();proj=Path(t)/'p';(proj/'work').mkdir(parents=True);(proj/'przebitki').mkdir()
            items=[('Wsad Ub','ub.mp4','Ub','FIBA 3x3 World Tour Zadar'),
                   ('Polska w MŚ','pl.mp4','Polska','FIBA 3x3 World Cup'),
                   ('koszykarka rzuca','k.mp4','Paris','FIBA 3x3 World Tour'),
                   ('Serbia w Zadarze','rs.mp4','Serbia','FIBA 3x3 World Tour Zadar'),
                   ('Serbia w ME','rs2.mp4','Serbia','nieustalone')]
            (lib/'README.md').write_text(''.join(self.entry(*i) for i in items))
            for n,(_,f,_,_) in enumerate(items): (lib/f'{n+1}_{f}').write_bytes(b'x')
            r=candidates(proj,lib)
            self.assertEqual((r['allowed'],r['review'],r['excluded']),(2,1,3))
            add_broll(proj,['1','4'])
            self.assertTrue((proj/'przebitki/1_ub.mp4').exists())
            for bad in ('2','3','5'):
                with self.assertRaises(ValueError):add_broll(proj,[bad])

    def test_photos_use_the_same_filter_and_go_to_zdjecia(self):
        with tempfile.TemporaryDirectory() as t:
            lib=Path(t)/'images';lib.mkdir();proj=Path(t)/'p';(proj/'work').mkdir(parents=True)
            items=[('Ub cieszy się','7_ub - 01.jpg','Ub','FIBA 3x3 World Tour Zadar'),
                   ('Ub po meczu','7_ub - 02.jpg','Ub','FIBA 3x3 World Tour Zadar'),
                   ('Polska w MŚ','pl.jpg','Polska','FIBA 3x3 World Cup'),
                   ('koszykarka','k.jpg','Paris','FIBA 3x3 World Tour')]
            (lib/'README.md').write_text(''.join(self.entry(*i).replace('`video/','`images/') for i in items))
            for _,f,_,_ in items:(lib/f).write_bytes(b'x')
            r=candidates(proj,lib,photos=True)
            self.assertEqual((r['allowed'],r['excluded']),(2,2))
            ids=[e['id'] for e in read(proj/'work/kandydaci-zdjecia.json')['candidates']]
            self.assertEqual(len(set(ids)),2)
            add_broll(proj,ids,True)
            self.assertTrue((proj/'zdjecia/7_ub - 02.jpg').exists())
            excluded=[e['matches'][0] for e in read(proj/'work/kandydaci-zdjecia.json')['excluded_items']]
            from studio.library import ident
            with self.assertRaises(ValueError):add_broll(proj,[ident(excluded[0],True)],True)

class RenderCheck(unittest.TestCase):
    def meta(self,video_len,container_len,w=540,h=960,audio=True):
        return {'duration':container_len,'audio':audio,'video':{'width':w,'height':h,'duration':str(video_len)}}
    def test_audio_padding_does_not_fail_length(self):
        p=plan();p['aroll']['duration']=83.704
        check_output(self.meta(83.733333,83.776),p,False)
    def test_real_length_size_and_audio_errors(self):
        p=plan();p['aroll']['duration']=83.704
        for m in [self.meta(83.9,83.9),self.meta(83.73,83.73,w=1080,h=1920),self.meta(83.73,83.73,audio=False)]:
            with self.assertRaises(ValueError):check_output(m,p,False)
        check_output(self.meta(83.73,83.78,w=1080,h=1920),p,True)

from studio import stock
class Stock(unittest.TestCase):
    def result(self,n,title,w=1080,h=1920,ms=8000):
        return {'id':f'pexels:{n}','provider':'Pexels','providerKey':'pexels','mediaType':'video','title':title,'description':title,
                'author':'A','authorUrl':'','sourcePage':f'https://pexels.com/{n}','originalUrl':'https://x','downloadUrl':f'https://x/{n}.mp4',
                'width':w,'height':h,'durationMs':ms,'licenseName':'Pexels License','licenseUrl':'https://www.pexels.com/license/',
                'licenseRequiresAttribution':False,'attribution':f'Video by A via Pexels','usageWarning':'-','suggestedFilename':f'pexels-{n}.mp4'}
    def test_quality_limits_for_the_template(self):
        self.assertEqual(stock.quality(self.result(1,'ok'),'video'),[])
        for bad in [self.result(2,'x',1920,1080),self.result(3,'x',720,1280),self.result(4,'x',1081,1921),self.result(5,'x',ms=2500)]:
            self.assertTrue(stock.quality(bad,'video'))
    def test_same_content_rules_approval_attributions(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t);proj=t/'p';(proj/'work').mkdir(parents=True)
            found=[self.result(1,'Mezczyzna wsad do kosza'),self.result(2,'Kobieta gra w koszykowke'),self.result(3,'Reprezentacja w koszykowke'),self.result(4,'Mezczyzna pozioma',1920,1080)]
            def fake_download(url,dest,*a):
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(url.encode());return sha(dest)
            with patch.object(stock,'search',return_value=(found,1)),patch.object(stock.sl,'REGISTRY_JSON',t/'reg.json'),patch.object(stock.sl,'REGISTRY_MD',t/'reg.md'),\
                 patch.object(stock.sl,'LIBRARY_DIR',t/'lib'),patch.object(stock.sl,'ROOT',t),patch.object(stock.sl,'download_file',side_effect=fake_download),\
                 patch.object(stock.sl,'probe_download',return_value={'width':1080,'height':1920,'durationMs':8000}):
                r=stock.candidates(proj,'wsad')
                self.assertEqual((r['allowed'],r['excluded'],r['rejectedByLicense']),(1,3,1))
                sid=read(proj/'work/stock-kandydaci.json')['candidates'][0]['sid']
                with self.assertRaises(ValueError):stock.add(proj,[sid],False)
                with self.assertRaises(ValueError):stock.add(proj,[stock.ident('pexels:2')],True)
                self.assertEqual(stock.add(proj,[sid],True)['copied'],['przebitki/pexels-1.mp4'])
                self.assertEqual(read(t/'reg.json')['items'][0]['id'],'pexels:1')
                (proj/'wynik').mkdir()
                p=plan();p['elements'][0]['source']='przebitki/pexels-1.mp4'
                self.assertEqual(len(stock.attributions(proj,p)),1)
                self.assertIn('Video by A via Pexels',(proj/'wynik/ATRYBUCJE.md').read_text())
    def test_place_motif_needs_the_name_in_the_source(self):
        m={'id':'M01','rodzaj':'miasto','nazwa':'Athens','aliasy':['Ateny']}
        kinds=read(Path(__file__).resolve().parents[2]/'config/stock.json')['rodzaje']
        self.assertIn('Ateny aerial',stock.expand(m,kinds))
        ok=self.result(1,'Widok z lotu ptaka na ateny');other=self.result(2,'Widok z lotu ptaka na miasto')
        self.assertTrue(stock.place_confirmed(ok,m));self.assertFalse(stock.place_confirmed(other,m))
        fallback={**other,'description':'Wynik wyszukiwania: Athens aerial'}
        self.assertFalse(stock.place_confirmed(fallback,m))
        with self.assertRaises(ValueError):stock.expand({'id':'M02','rodzaj':'miasto'},kinds)

from studio import sound
class Sound(unittest.TestCase):
    def plan(self):
        p=plan();p['aroll']['duration']=40
        p['elements']=[{'id':'B01','type':'broll','start':0,'end':3,'source':'a','kind':'video'},
                       {'id':'B02','type':'broll','start':6,'end':9,'source':'a','kind':'video'},
                       {'id':'B03','type':'broll','start':9,'end':12,'source':'a','kind':'video'},
                       {'id':'P01','type':'photo','start':14,'end':17.4,'photos':[{'source':'z'}]},
                       {'id':'B04','type':'broll','start':20,'end':24,'source':'a','kind':'video'}]
        return p
    def run_add(self,chosen):
        with tempfile.TemporaryDirectory() as t:
            proj=Path(t);write(proj/'plan.json',self.plan())
            with patch.object(sound,'install'),patch.object(sound,'length',return_value=.7):r=sound.add_sounds(proj,chosen)
            return r,[e for e in read(proj/'plan.json')['elements'] if e['type']=='sfx']
    def test_whoosh_only_where_face_turns_into_broll(self):
        self.assertEqual(sound.block_starts(self.plan()),[6,20])
    def test_chosen_effects_win_gap_and_limits(self):
        r,s=self.run_add([('impact',22.0),('doping',30.0),('doping',37.0),('riser',1.0)])
        self.assertEqual([x['source'] for x in s],['audio/impact-low.wav','audio/doping.wav','audio/dragon-whoosh-short.wav'])
        reasons={(x['rodzaj'],x['czas']):x['powod'] for x in r['skipped']}
        self.assertIn('limit',reasons[('doping',37.0)]);self.assertIn('poza',reasons[('riser',1.0)]);self.assertIn('5 s',reasons[('whoosh',20)])
        self.assertAlmostEqual(s[2]['start'],5.7)
    def test_unknown_effect(self):
        with self.assertRaises(ValueError):self.run_add([('syrena',10.0)])

class Graphics(unittest.TestCase):
    def add(self,**e):
        p=plan();p['elements'].append({'id':'G01','type':'graphic','start':6,'end':9.5,**e});return p
    def test_counter_data(self):
        validate(self.add(variant='counter',data={'value':32,'label':'punkty','land_at':8.4}),Path('.'),False)
        for bad in [dict(variant='counter',data={'label':'x'}),dict(variant='counter',data={'value':3,'land_at':12}),
                    dict(variant='counter',data={'value':3,'color':'red'}),dict(variant='scoreboard',data={'teams':[{'name':'A','score':1},{'name':'B','score':2}]}),
                    dict(variant='globe',data={})]:
            with self.assertRaises(ValueError):validate(self.add(**bad),Path('.'),False)
    def test_graphic_is_a_scene_on_the_broll_track(self):
        p=self.add(variant='counter',data={'value':3});p['elements'][-1]['end']=8.5
        with self.assertRaisesRegex(ValueError,'3 s'):validate(p,Path('.'),False)
        p=self.add(variant='counter',data={'value':3});p['elements'][-1]['start']=2
        with self.assertRaisesRegex(ValueError,'Nakładanie'):validate(p,Path('.'),False)
    def test_globe_data(self):
        validate(self.add(variant='globe',data={'city':'Antwerpia','country':'Belgia','lat':51.22,'lon':4.4}),Path('.'),False)
        validate(self.add(variant='globe',data={'city':'Hongcheon','lat':37.7,'lon':127.9,'date':'18–19 września','from':{'name':'Warszawa','lat':52.23,'lon':21.01}}),Path('.'),False)
        for bad in [{'city':'X','lat':95,'lon':0},{'city':'X','lat':1},{'lat':1,'lon':1},{'city':'X','lat':1,'lon':1,'from':{'name':'Y'}},{'city':'X','lat':1,'lon':1,'zoom':3}]:
            with self.assertRaises(ValueError):validate(self.add(variant='globe',data=bad),Path('.'),False)
