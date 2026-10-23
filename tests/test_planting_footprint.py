import unittest,math
from adapters.blender.planting_footprint import validate_outline,validate_place,signed_distance
from adapters.blender.exploration import RouteField

class PlantingFootprint(unittest.TestCase):
 def test_actual_footprint_preserves_garden_margin_and_route(self):
  polygon=[[-2,-1],[2,-1],[2,1],[-2,1]]
  field=RouteField({'routes':[{'width':2,'points':[[5,-8,0],[5,8,0]]}], 'places':[{'center':[0,0,0],'radius':6,'surface':'none','clear_outline':polygon}]})
  self.assertTrue(field.clear(0,0));self.assertTrue(field.clear(2.2,0,.3))
  self.assertFalse(field.clear(0,3));self.assertTrue(field.clear(5,3))
  self.assertEqual(field.height(0,0,9),0)
 def test_clearing_cannot_leave_paving_unprotected(self):
  p={'surface':'stone','outline':[[-3,-2],[3,-2],[3,2],[-3,2]],'clear_outline':[[-2,-2],[2,-2],[2,2],[-2,2]]}
  with self.assertRaisesRegex(ValueError,'complete paved'):validate_place(p)
  p['clear_outline']=p['outline'];validate_place(p)
 def test_rotated_margin_is_euclidean_and_winding_independent(self):
  p=[[0,-2],[2,0],[0,2],[-2,0]]
  for points in [p,p[::-1]]:
   validate_outline(points);self.assertAlmostEqual(signed_distance(2,2,points),math.sqrt(2))
   self.assertLess(signed_distance(.2,0,points),0)
 def test_invalid_polygon_rejected(self):
  for p in [[[0,0],[1,1],[2,2]],[[0,0],[2,2],[0,2],[2,0]],[[0,0],[0,0],[1,1]],[[0,0],[2,0],[1,.2],[2,2],[0,2]]]:
   with self.assertRaises(ValueError):validate_outline(p)
