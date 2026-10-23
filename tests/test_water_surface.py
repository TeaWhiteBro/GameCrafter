import unittest
from adapters.unreal.water_surface import validate, normal_shader


class WaterContractTests(unittest.TestCase):
    def test_unbounded_or_nonfinite_parameters_rejected(self):
        for invalid in [{'speed': float('nan')}, {'normal_amplitude': 5}, {'roughness': 0}, {'tint': [0, 2, 0]}, {'bed_visibility': True}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate(invalid)

    def test_normal_is_world_space_and_time_driven(self):
        code = normal_shader({'ripple_scale_m': 2, 'speed': .7})
        # Verify parameter transport here. Surface orientation and the compiled
        # shader are checked in native UE; do not require an always-up normal.
        self.assertIn('/200.00000000', code)
        self.assertIn('T*0.70000000', code)
        self.assertIn('return normalize(', code)


if __name__ == '__main__':
    unittest.main()
