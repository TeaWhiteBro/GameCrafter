import copy,unittest
from game_pipeline.scene_intent import grounded_prop_conflicts

class PropClearanceTests(unittest.TestCase):
 def scene(self):
  return {'objects':[{'kind':'asset','asset':'cargo','position':[4,2,0],'scale':[2,2,2],'snap_to_terrain':True,'grounding':'footprint'}],
          'composition':{'exploration':{'routes':[{'id':'walk','points':[[0,0,0],[8,4,1]]}]}}}
 def test_grounded_prop_on_sloping_route_rejected_before_build(self):
  self.assertEqual(len(grounded_prop_conflicts(self.scene())),1)
 def test_rotated_nearby_stock_does_not_block_centerline(self):
  s=self.scene();s['objects'][0].update(position=[4,6,0],yaw_deg=35)
  self.assertEqual(grounded_prop_conflicts(s),[])
 def test_rock_and_overhead_placement_still_require_exact_geometry(self):
  s=self.scene();s['objects'][0]['grounding']='rock';self.assertEqual(grounded_prop_conflicts(s),[])
  s=self.scene();s['objects'][0]['snap_to_terrain']=False;self.assertEqual(grounded_prop_conflicts(s),[])
