import unittest
from adapters.blender.cart_tracks import profile

class CartTrackTests(unittest.TestCase):
    def test_shallow_paired_profile_preserves_central_sand(self):
        route={'surface':'earth','wheel_ruts':{'spacing_m':1.8,'width_m':.32,'depth_m':.035}}
        self.assertLess(profile(route,0)[0],.001)
        self.assertAlmostEqual(profile(route,.9)[1],-.035)
        self.assertEqual(profile(route,.9),profile(route,-.9))
        self.assertLess(profile(route,2)[0],.001)
    def test_deep_or_non_earth_ruts_rejected(self):
        for route in [{'surface':'stone','wheel_ruts':{'spacing_m':1.8,'width_m':.32,'depth_m':.035}},
                      {'surface':'earth','wheel_ruts':{'spacing_m':1.8,'width_m':.32,'depth_m':.4}}]:
            with self.assertRaises(ValueError):profile(route,1)
