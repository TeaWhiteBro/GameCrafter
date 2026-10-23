import unittest
from adapters.blender.exploration import RouteField

class FoundationHeightTests(unittest.TestCase):
    def test_polygon_foundation_does_not_flatten_an_unrelated_circular_clearing(self):
        f=RouteField({'foundation_pads':[{'center':[0,0,2],'radius':10,'outline':[[-2,-4],[2,-4],[2,4],[-2,4]],'edge_fade_m':2}]})
        self.assertEqual(f.height(0,3,8),2)
        self.assertEqual(f.height(5,0,8),8)
        self.assertAlmostEqual(f.height(3,0,8),5)
        self.assertEqual(f.height(0,7,8),8)

    def test_legacy_radius_is_preserved_when_no_outline_is_authored(self):
        f=RouteField({'places':[{'center':[0,0,2],'radius':10}]})
        self.assertEqual(f.height(9,0,8),2)
        self.assertAlmostEqual(f.height(11.5,0,8),5)
        self.assertEqual(f.height(14,0,8),8)
