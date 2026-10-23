import json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from game_pipeline.camera_validation import run
from game_pipeline.core import StageError


class CameraFailureEvidenceTests(unittest.TestCase):
    def test_runtime_rejection_retains_current_camera_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'Game/Game.uproject';project.parent.mkdir();project.write_text('{}')
            out=root/'stage';out.mkdir()
            def execute(*args,**kwargs):
                saved=project.parent/'Saved';shots=saved/'Screenshots/WindowsEditor';shots.mkdir(parents=True)
                (saved/'GameDemoCameraQA.json').write_text(json.dumps({'passed':False,'probe_space_validated':True,'probe_queries':140,'cases':[]}))
                for i in range(4):(shots/f'{i}.png').write_bytes(b'fresh failure evidence')
            ctx=SimpleNamespace(directory=out,machine={'unreal_editor':'UE.exe'},
                inputs={'playtest':{'passed':True},'ue_assemble':{'project':str(project)}},run=execute)
            with self.assertRaisesRegex(StageError,'incomplete or failed'):run(ctx,{})
            self.assertEqual(len(list(out.glob('view_*.png'))),4)
            self.assertFalse(json.loads((out/'validation.json').read_text())['passed'])
