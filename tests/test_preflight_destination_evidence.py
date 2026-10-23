import json,pathlib,tempfile,types,unittest
from unittest.mock import patch
from game_pipeline.preflight_capture import capture_runtime
from game_pipeline.core import StageError

class DestinationEvidenceTests(unittest.TestCase):
    def run_capture(self, *, clearance=True, paired=True, oblique=False, oblique_count=3, oblique_radius=2100):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);base=root/'project';base.mkdir()
            (base/'Saved/Screenshots').mkdir(parents=True)
            directory=root/'capture';directory.mkdir()
            scene={'exploration':{'places':[{'name':n} for n in ['Gallery','Bay','Control']]}}
            def native(args,**kwargs):
                name=pathlib.Path(kwargs['log_name']).stem
                (directory/(name+'_engine.log')).write_text('No material failures')
                if name.startswith('route_'):
                    filename='GameDemoExplorationQA.json';item={'passed':True,'captured_place_indices':[0,1,2]};count=3
                else:
                    filename='GameDemoArtQA.json';count=2 if name=='overview' else oblique_count if name=='oblique' else 6 if paired else 4
                    if name=='oblique':
                        self.assertIn('-PipelinePlaceReview',args)
                        self.assertIn('-PipelinePlaceOblique',args)
                    item={'current_runtime_views':True,'view_count':count,'view_centres_verified':True,'ground_camera_clearance_verified':clearance}
                    if name=='oblique':item['oblique_perspective']=True
                    if name=='oblique':
                        (directory/(name+'_engine.log')).write_text('\n'.join(
                            f'OBLIQUE_CAMERA index={i} foreground_clear=1\nART_CAMERA_DISTANCE index={i} oblique=1 actual_cm={oblique_radius:.4f}' for i in range(count)))
                (base/'Saved'/filename).write_text(json.dumps(item))
                for i in range(count):
                    (base/f'Saved/Screenshots/{name}_{i}.png').write_bytes(b'fixture')
            ctx=types.SimpleNamespace(directory=root,machine={'unreal_editor':'fake-editor'},run=native)
            # Fresh native outputs are still collected through the producer's
            # timestamp filter; the fake native writes do not replace policy.
            return capture_runtime(ctx,str(base/'Game.uproject'),scene,directory,oblique_views=oblique)

    def test_all_three_destinations_receive_elevated_and_ground_labels(self):
        result=self.run_capture()
        self.assertEqual(len(result['views']),17)
        labels=result['labels'][2:8]
        for i,name in enumerate(['Gallery','Bay','Control']):
            self.assertIn(name+' elevated structure view',labels[i])
            self.assertIn(name+' opposing ground view',labels[i+3])

    def test_old_single_ground_view_is_not_enough(self):
        with self.assertRaises(StageError):self.run_capture(paired=False)

    def test_current_images_cannot_replace_camera_clearance(self):
        with self.assertRaises(StageError):self.run_capture(clearance=False)

    def test_oblique_views_add_each_destination_without_removing_existing_views(self):
        result=self.run_capture(oblique=True)
        self.assertEqual(len(result['views']),20)
        for i,name in enumerate(['Gallery','Bay','Control']):
            self.assertIn(name+' oblique perspective',result['labels'][8+i])
        self.assertEqual(set(result['evidence']),{'overview','places','oblique','route_first','route_third','route_isometric'})

    def test_oblique_capture_must_cover_all_destinations(self):
        with self.assertRaises(StageError):self.run_capture(oblique=True,oblique_count=2)

    def test_gameplay_radius_override_fails_even_when_focus_is_centered(self):
        with self.assertRaises(StageError):self.run_capture(oblique=True,oblique_radius=650)

if __name__=='__main__':unittest.main()
