import unittest
from adapters.unreal.surface_wetness import evaluate,evaluate_unreal,validate,shader

class SurfaceWetnessTests(unittest.TestCase):
    def test_draining_strip_is_local_rotatable_and_bounded(self):
        z=[{'center':[4,7],'radii':[8,.5],'yaw_deg':90,'strength':.9}]
        self.assertAlmostEqual(evaluate(z,4,7),.9)
        self.assertAlmostEqual(evaluate(z,4,12),.9)
        self.assertEqual(evaluate(z,5,7),0)
        self.assertEqual(evaluate(z,4,15),0)
        self.assertTrue(0<evaluate(z,4,14)<.9)
    def test_overlapping_masks_do_not_add_beyond_strongest(self):
        self.assertAlmostEqual(evaluate([{'center':[0,0],'radii':[2,2],'strength':.7}]*3,0,0),.7)
    def test_invalid_or_excessive_regions_rejected(self):
        for z in [[{'center':[0,0],'radii':[0,1]}],[{'center':[0,float('nan')],'radii':[1,1]}],[{'center':[0,0],'radii':[1,1],'strength':1.1}],[{}]*25]:
            with self.assertRaises(ValueError):validate(z)
    def test_shader_uses_metric_world_xy_and_upward_normal_mask(self):
        code=shader([{'center':[4,-7],'radii':[8,.5]}])
        self.assertIn('P.xy*float2(0.01,0.01)',code);self.assertIn('float2(4.0,-7.0)',code);self.assertIn('N.z',code)
    def test_exported_asymmetric_world_point_reaches_authored_drain_not_mirror(self):
        # Final imported UE bounds independently measured on asymmetric props.
        zones=[{'center':[25,-24],'radii':[3,.5],'strength':.9}]
        self.assertAlmostEqual(evaluate_unreal(zones,2500,-2400),.9)
        self.assertEqual(evaluate_unreal(zones,2500,2400),0)
        rotated=[{'center':[4,7],'radii':[8,.5],'yaw_deg':90,'strength':.8}]
        self.assertAlmostEqual(evaluate_unreal(rotated,400,1200),.8)

if __name__=='__main__':unittest.main()
