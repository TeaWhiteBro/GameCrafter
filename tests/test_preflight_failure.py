import unittest,tempfile,time,os,json
from pathlib import Path
from game_pipeline.scene_preflight import preserve_failed_runtime

class PreflightFailureTests(unittest.TestCase):
 def test_timeout_retains_fresh_partial_images_but_not_stale_pass(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t)/'project';shots=base/'Saved/Screenshots';shots.mkdir(parents=True);out=Path(t)/'out';out.mkdir()
   start=time.time();old=shots/'old.png';old.write_bytes(b'old');os.utime(old,(start-30,start-30))
   fresh=shots/'new.png';fresh.write_bytes(b'new');os.utime(fresh,(start+1,start+1))
   stale=base/'Saved/QA.json';stale.write_text('{"passed":true}');os.utime(stale,(start-30,start-30))
   preserve_failed_runtime(out,base,'walk','QA.json',start,RuntimeError('timeout'))
   record=json.loads((out/'failed_walk_process.json').read_text())
   self.assertFalse(record['passed']);self.assertEqual(len(record['partial_evidence']),1)
   self.assertEqual(Path(record['partial_evidence'][0]).read_bytes(),b'new')
   self.assertFalse((out/'failed_walk.json').exists())
