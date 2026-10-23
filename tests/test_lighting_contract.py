import unittest
from game_pipeline.lighting_contract import effective_lighting

class LightingContractTests(unittest.TestCase):
    def test_positive_solar_elevation_is_not_an_engine_downward_light(self):
        for value in [52,90,float('nan'),-91,True]:
            with self.assertRaisesRegex(ValueError,'Unreal rotation'):
                effective_lighting({'sun_pitch':value})

    def test_explicit_light_repair_preserves_original_scene_geometry_contract(self):
        authored={'sun_pitch':52,'sun_intensity':5.7}
        effective=effective_lighting(authored,{'sun_pitch':-52})
        self.assertEqual(effective,{'sun_pitch':-52,'sun_intensity':5.7})
        self.assertEqual(authored['sun_pitch'],52)

if __name__=='__main__':unittest.main()
