import unittest
from game_pipeline.local_lights import validate

class OptionalAtmosphere(unittest.TestCase):
    def test_ue_visible_sky_range_rejected_before_native_import(self):
        for value in [-1,.02,20001,float('nan')]:
            with self.subTest(value=value),self.assertRaises(ValueError):validate({'sky_luminance_factor':value})
        for value in [1,20000]:validate({'sky_luminance_factor':value})
    def test_fog_color_and_distance_are_bounded(self):
        validate({'fog_color':[.03,.18,.21],'fog_start_m':10,'fog_height_falloff':.02})
        for data in [{'fog_color':[2,0,0]},{'fog_start_m':-1},{'fog_height_falloff':0}]:
            with self.subTest(data=data),self.assertRaises(ValueError):validate(data)
