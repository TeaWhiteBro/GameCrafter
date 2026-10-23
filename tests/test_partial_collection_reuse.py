import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from game_pipeline.core import write_json,digest,read_json
from game_pipeline.production_capture import capture_job
from game_pipeline.rendering import profile


class PartialCollectionReuseTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);self.project=root/'project/GameDemo.uproject'
        self.project.parent.mkdir();self.project.write_text('{}')
        self.module=self.project.parent/'runtime.dll';self.module.write_bytes(b'unchanged runtime')
        self.new=root/'stages/new';self.new.mkdir(parents=True)
        self.old=root/'stages/partial/calibration_third';(self.old/'raw').mkdir(parents=True)
        self.job={'key':'calibration_third','camera':'third','activity':'idle','frames':4,
                  'width':64,'height':64,'whitebox':True,'warmup_frames':90,'calibration':True}
        (self.old/'raw/000000.json').write_text('{"frame":0}')
        write_json(self.old/'capture_result.json',{'ok':True})
        write_json(self.old/'source.json',{'project':str(self.project.resolve()),
            'rendering_profile':profile(),'files':{'runtime.dll':digest(self.module)}})
        files={str(p.relative_to(self.old)):digest(p) for p in self.old.rglob('*') if p.is_file()}
        write_json(self.old/'commit.json',{'job':self.job,'files':files})
        self.calls=[]
        def run(args,**kw):
            self.calls.append(args);out=Path(args[args.index('--out')+1]);out.mkdir(exist_ok=True)
            write_json(out/'validation.json',{'passed':True,'export_complete':True})
        self.ctx=SimpleNamespace(directory=self.new,machine={'python':'python','unreal_editor':'UE'},run=run)

    def test_completed_sequence_from_partial_collection_is_reprocessed(self):
        self.assertFalse((self.old.parent/'receipt.json').exists())
        out=capture_job(self.ctx,str(self.project),self.job)
        self.assertIn('--process-only',self.calls[0])
        self.assertEqual((out/'raw/000000.json').read_bytes(),(self.old/'raw/000000.json').read_bytes())
        self.assertEqual(read_json(out/'raw_reuse.json')['source'],str(self.old))

    def test_tampered_raw_in_partial_collection_is_not_reused(self):
        (self.old/'raw/000000.json').write_text('{"frame":99}')
        out=capture_job(self.ctx,str(self.project),self.job)
        self.assertNotIn('--process-only',self.calls[0]);self.assertFalse((out/'raw_reuse.json').exists())

    def test_uncommitted_sequence_still_requires_new_capture(self):
        (self.old/'commit.json').unlink()
        out=capture_job(self.ctx,str(self.project),self.job)
        self.assertNotIn('--process-only',self.calls[0]);self.assertFalse((out/'raw_reuse.json').exists())
