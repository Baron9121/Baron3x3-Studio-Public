import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from scripts import specialists as s
from scripts.pipeline import transcribe

class SpecialistTests(unittest.TestCase):
 def test_stt_requires_real_word_times(self):
  with self.assertRaises(ValueError):s.normalized_stt({'text':'abc'},Path('x'),2)
  with self.assertRaises(ValueError):s.normalized_stt({'words':[{'word':'abc','start':2,'end':1}]},Path('x'),2)
  raw=s.normalized_stt({'words':[{'word':'koreańskim','start':0,'end':1},{'word':'Hongcheon','start':1,'end':2}]},Path('x'),2)
  self.assertEqual(raw['text'],'koreańskim Hongcheon')
 def test_budget_counts_coordinator_and_blocks_unknown(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(s,'ROOT',Path(tmp)):
   with self.assertRaises(ValueError):
    with s.reservation('x',1,.5,.6):pass
   with s.reservation('x',1,.2,.1) as entry:entry['costUsd']=.15
   with s.reservation('x',1,.2,.2):pass
   with self.assertRaisesRegex(ValueError,'Unresolved'):
    with s.reservation('x',1,.2,.2):pass
 def test_transcript_apply_checks_hash_and_clears_old_substitutions(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(s,'ROOT',Path(tmp)):
   root=Path(tmp);source=root/'input/x.mp4';source.parent.mkdir();source.write_bytes(b'source')
   folder=root/'analysis/x/specialists';folder.mkdir(parents=True)
   raw=s.normalized_stt({'words':[{'word':'Hongcheon','start':0,'end':1}]},source,1)
   s.write(folder/'transcript-raw.json',raw)
   s.write(folder/'verify-transcript.json',{'hashes':{'source':s.sha(source),'transcript':s.sha(folder/'transcript-raw.json')},'data':{'verdict':'pass','issues':[]}})
   s.write(root/'instructions/jobs/x.replacements.json',{'Hongcheon':'Deqing'})
   s.apply_transcript('x',source,True)
   self.assertEqual(s.read(root/'instructions/jobs/x.replacements.json'),{})
   self.assertEqual(transcribe(source,root/'analysis/x','anything','pl',False)['text'],'Hongcheon')
   source.write_bytes(b'changed')
   with self.assertRaises(ValueError):transcribe(source,root/'analysis/x','anything','pl',False)
