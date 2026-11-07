import copy, unittest
from scripts.resolve_free.pipeline import ROOT,decode_model_clips,validate,lua,media_path,search_library
class ResolveFreeTest(unittest.TestCase):
 def setUp(self):
  self.p={'version':1,'fps':30,'name':'Baron3x3-unit','clips':[{'file':str(ROOT/'analysis/resolve-poc/source.mp4'),'in':0,'out':3,'at':0,'track':1,'kind':'video','zoom':1}]}
 def test_frame_count(self): self.assertEqual(validate(self.p)[1],90)
 def test_overlap(self):
  self.p['clips']*=2
  with self.assertRaisesRegex(ValueError,'Nakładanie'): validate(self.p)
 def test_gap(self):
  self.p['clips'][0]['at']=1
  with self.assertRaisesRegex(ValueError,'Luka'): validate(self.p)
 def test_beyond_source(self):
  self.p['clips'][0]['out']=20
  with self.assertRaises(ValueError): validate(self.p)
 def test_nan(self):
  self.p['clips'][0]['zoom']=float('nan')
  with self.assertRaises(ValueError): validate(self.p)
 def test_outside_path(self):
  with self.assertRaises(ValueError): media_path('/etc/passwd')
 def test_invalid_name(self):
  self.p['name']='../../bad'
  with self.assertRaises(ValueError): validate(self.p)
 def test_lua_injection(self):
  self.assertEqual(lua('"\n\\'), '"\\034\\010\\092"')
 def test_unaligned_frame(self):
  self.p['clips'][0]['out']=1.01
  with self.assertRaises(ValueError): validate(self.p)
 def test_index_search(self):
  self.assertTrue(search_library('Polonia'))
 def test_curated_jimmer_search(self):
  self.assertEqual(len(search_library('Jimmer Fredette')),3)
 def test_audio_track_limit(self):
  self.p['clips'][0].update(kind='audio',track=2)
  with self.assertRaises(ValueError): validate(self.p)
 def test_compact_model_clip(self):
  raw={'file':str(ROOT/'analysis/resolve-poc/source.mp4'),'in':0,'out':3,'at':0,'track':1,'kind':'video','zoom':1}
  self.assertEqual(decode_model_clips([{'clipJson':__import__('json').dumps(raw)}]),[raw])
 def test_compact_model_clip_rejects_extra_field(self):
  with self.assertRaises(ValueError): decode_model_clips([{'clipJson':'{"file":"x"}'}])
if __name__=='__main__': unittest.main()
