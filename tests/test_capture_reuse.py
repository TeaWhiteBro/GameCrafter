import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
from game_pipeline.core import write_json,digest
from game_pipeline.capture_adapter import reuse_raw

class RawCaptureReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);r=Path(self.tmp.name)
        self.project=r/'project/GameDemo.uproject';self.project.parent.mkdir();self.project.write_text('{}')
        self.module=self.project.parent/'module.dll';self.module.write_bytes(b'actual runtime revision')
        self.ctx=SimpleNamespace(directory=r/'stages/new');self.ctx.directory.mkdir(parents=True)
        self.old=r/'stages/old/third';(self.old/'raw').mkdir(parents=True)
        for i in range(2):(self.old/'raw'/f'{i:06d}.json').write_text('{}')
        write_json(self.old/'capture_result.json',{'frames':2,'width':64,'height':64,'calibration_only':False,'whitebox':True})
        write_json(self.old/'validation.json',{'passed':True,'export_complete':True})
        write_json(self.old/'source.json',{'project':str(self.project.resolve()),'camera':'third','files':{'module.dll':digest(self.module)}})
        files=[self.old/'source.json',self.old/'capture_result.json']+list((self.old/'raw').glob('*'))
        write_json(self.old.parent/'receipt.json',{'_artifacts':{str(f.resolve()):digest(f) for f in files}})
    def reuse(self,**kw):
        return reuse_raw(self.ctx,'third',self.ctx.directory/'third',str(self.project),'third',kw.get('calibration',False),kw.get('frames',2),64,64,True)
    def test_committed_same_project_reuses_exact_raw(self):
        self.assertTrue(self.reuse());self.assertEqual(digest(self.old/'raw/000000.json'),digest(self.ctx.directory/'third/raw/000000.json'))
    def test_changed_runtime_cannot_reuse(self):
        self.module.write_bytes(b'new revision');self.assertFalse(self.reuse())
    def test_tampered_raw_cannot_reuse(self):
        (self.old/'raw/000000.json').write_text('{"different_pose":true}');self.assertFalse(self.reuse())
    def test_changed_camera_settings_cannot_reuse(self):
        self.assertFalse(self.reuse(frames=4));self.assertFalse(self.reuse(calibration=True))
    def test_uncommitted_capture_cannot_reuse(self):
        (self.old.parent/'receipt.json').unlink();self.assertFalse(self.reuse())

if __name__=='__main__':unittest.main()
