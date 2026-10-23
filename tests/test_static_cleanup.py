import importlib.util,pathlib,unittest
P=pathlib.Path(__file__).resolve().parents[1]/'adapters/blender/static_cleanup.py'
spec=importlib.util.spec_from_file_location('static_cleanup',P);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class StaticCleanupBounds(unittest.TestCase):
    def test_rejects_nonfinite_axis_scale(self):
        for values in [[1,float('nan'),1],[1,float('inf'),1],[1,3,1],[1,0,1],[True,1,1]]:
            with self.assertRaises(ValueError):module.validate({'axis_scale':values})
    def test_detail_region_must_have_volume(self):
        with self.assertRaises(ValueError):module.validate({'duplicate_regions':[{'min':[0,.5,0],'max':[1,.5,1],'offset':[0,0,0]}]})
    def test_detail_copy_must_be_bounded(self):
        with self.assertRaises(ValueError):module.validate({'duplicate_regions':[{'min':[0,0,0],'max':[1,1,1],'offset':[2,0,0]}]})
    def test_rejects_unbounded_detail_count(self):
        with self.assertRaises(ValueError):module.validate({'duplicate_regions':[{}]*4})
    def test_accepts_normalized_local_repair(self):
        config={'axis_scale':[1.1,2.05,1],'duplicate_regions':[{'min':[.7,.36,.32],'max':[.96,.41,.44],'offset':[-.01,.11,0]}]}
        self.assertEqual(module.validate(config),config)
