import copy,unittest
from game_pipeline.scene_geometry import validate
from game_pipeline.core import StageError

class SceneGeometryTests(unittest.TestCase):
    def report(self):
        return {'ok':True,'exploration':{'route_edges':4},'whitebox':{'route_clearance':{'passed':True,'samples':600,'obstructions':[]}}}
    def test_export_success_does_not_override_obstruction(self):
        r=self.report();r['whitebox']['route_clearance']['obstructions']=[{'route':3,'hit_m':[1,2,3]}]
        with self.assertRaises(StageError):validate(r)
    def test_missing_or_failed_samples_are_not_clear_routes(self):
        for delta in [{'passed':False},{'samples':0}]:
            r=self.report();r['whitebox']['route_clearance'].update(delta)
            with self.assertRaises(StageError):validate(r)
        r=self.report();r.pop('whitebox')
        with self.assertRaises(StageError):validate(r)
    def test_valid_geometry_and_explicit_legacy_arena(self):
        self.assertTrue(validate(self.report())['ok'])
        self.assertTrue(validate({'ok':True})['ok'])
