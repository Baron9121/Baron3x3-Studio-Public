import json
import tempfile
import unittest
from pathlib import Path
from scripts.scenario_handoff import bind, check_scenario, write_review, check_review

class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'instructions/scenarios').mkdir(parents=True)
        self.source = self.root/'instructions/scenarios/test.md'
        self.source.write_text('Brief — zachowaj całą akcję.')
        self.plan = {'sourceRanges':[{'sourceStartMs':2000,'sourceEndMs':7000,'scaleFrom':1,'scaleTo':1.2}], 'overlays':[]}

    def test_full_snapshot_and_changed_brief_guard(self):
        text = bind(self.root,'test',self.source,'Moje instrukcje')
        self.assertIn('Moje instrukcje', text)
        self.assertIn(self.source.read_text(), text)
        check_scenario(self.root,'test')
        self.source.write_text('Nowy brief')
        with self.assertRaisesRegex(ValueError,'Scenariusz zmienił'):
            check_scenario(self.root,'test')
        bind(self.root,'test',self.source,'Moje instrukcje')
        check_scenario(self.root,'test')

    def test_review_contains_source_cuts_and_detects_zoom_change(self):
        signature = write_review(self.root,'test',self.plan)
        report = (self.root/'analysis/test/director/review-plan.md').read_text()
        self.assertIn('2000–7000',report)
        check_review(self.root,'test',self.plan,signature)
        self.plan['sourceRanges'][0]['scaleTo']=1.5
        with self.assertRaisesRegex(ValueError,'Plan lub'):
            check_review(self.root,'test',self.plan,signature)

    def test_legacy_unbound_scenario(self):
        check_scenario(self.root,'old-job')

    def test_missing_photo_metadata_is_not_silent(self):
        path=self.root/'analysis/assets/catalog.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'items':[{'id':'m','name':'matte','kind':'video','absolutePath':str(self.root/'assets/library/matte-photos/demo.mp4')}]}))
        self.plan['overlays']=[{'assetId':'m','timelineStartMs':0,'timelineEndMs':5200}]
        with self.assertRaisesRegex(ValueError,'metadanych'):
            write_review(self.root,'test',self.plan)

    def test_photo_order_and_duration_guard(self):
        path=self.root/'analysis/assets/catalog.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'items':[{'id':'m','name':'matte','kind':'video','absolutePath':str(self.root/'assets/library/matte-photos/demo.mp4')}]}))
        d=self.root/'analysis/matte-photos/demo';d.mkdir(parents=True)
        (d/'selection.json').write_text(json.dumps({'assetIds':['photo2','photo1'],'durationMs':3600}))
        (d/'props.json').write_text(json.dumps({'photoProfiles':[{'zoom':1.1},{'zoom':1}]}))
        (d/'sound-effects-relative.json').write_text('[]')
        self.plan['overlays']=[{'assetId':'m','timelineStartMs':0,'timelineEndMs':3600}]
        signature=write_review(self.root,'test',self.plan)
        report=(self.root/'analysis/test/director/review-plan.md').read_text()
        self.assertLess(report.index('photo2'),report.index('photo1'))
        (d/'props.json').write_text('{}')
        with self.assertRaises(ValueError):check_review(self.root,'test',self.plan,signature)
        self.plan['overlays'][0]['timelineEndMs']=3000
        with self.assertRaisesRegex(ValueError,'cały czas'):write_review(self.root,'test',self.plan)

class WorkflowReviewIntegration(unittest.TestCase):
    def test_import_approve_and_changed_render_are_guarded(self):
        from unittest.mock import patch
        from scripts import reel_workflow as w
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job='demo'
            directory=root/'analysis/demo/director';directory.mkdir(parents=True)
            jobs=root/'instructions/jobs';jobs.mkdir(parents=True)
            plan={'status':'ready','sourceRanges':[{'sourceStartMs':0,'sourceEndMs':5000}], 'overlays':[], 'effectCues':[], 'soundEffects':[]}
            (jobs/'demo.json').write_text(json.dumps(plan))
            (directory/'input-package.json').write_text(json.dumps({'timelineDurationMs':5000}))
            artifact={'status':'needs-review','proposal':{'beats':[]}}
            (directory/'proposal.json').write_text(json.dumps(artifact))
            with patch.multiple(w,ROOT=root,ANALYSIS=root/'analysis',JOBS=jobs,OUTPUT=root/'output'), patch.object(w,'import_cline_proposal',return_value=artifact):
                w.save_state(job,'awaiting-director-plan','test')
                result=w.import_director(job,0)
                self.assertEqual(result['phase'],'awaiting-director-approval')
                self.assertTrue((directory/'review-plan.md').exists())
                def fake_apply(*args):
                    applied=json.loads((directory/'review-plan.json').read_text())['plan']
                    applied['notes']=['approved']
                    (jobs/'demo.json').write_text(json.dumps(applied))
                    return applied
                with patch.object(w,'apply_director',side_effect=fake_apply):
                    result=w.approve_director(job,True)
                self.assertEqual(result['phase'],'ready-to-render')
                altered=json.loads((jobs/'demo.json').read_text());altered['captionStyle']='changed'
                (jobs/'demo.json').write_text(json.dumps(altered))
                with patch.object(w.subprocess,'run') as render:
                    with self.assertRaisesRegex(ValueError,'Plan lub'):w.render(job,True)
                    render.assert_not_called()

class DefaultPhotoPresentation(unittest.TestCase):
    def test_single_arena_photo_and_video_remain_regular_broll(self):
        for kind in ('image', 'video'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);p=root/'analysis/assets/catalog.json';p.parent.mkdir(parents=True)
                p.write_text(json.dumps({'items':[{'id':'arena','kind':kind,'name':'Arena'}]}))
                plan={'overlays':[{'assetId':'arena','timelineStartMs':0,'timelineEndMs':3000}]}
                write_review(root,'x',plan)
                self.assertNotIn('preparationRequired', plan['overlays'][0])
