import math,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from ground_support import footing_bottom,stair_boxes
from landscape_routes import wall_segments

class GroundSupportTests(unittest.TestCase):
 def test_perimeter_catches_valley_missed_by_corner_and_center_samples(self):
  def height(x,y):return -3*math.exp(-((x-.6)/.3)**2)*math.exp(-((y-.5)/.25)**2)
  bottom=footing_bottom(height,(0,0),(4,1))
  self.assertLess(bottom,-3)
  self.assertTrue(all(bottom<height(x,.5) for x in np.linspace(-2,2,80)))
 def test_yawed_stairs_preserve_tops_while_extending_to_sloped_terrain(self):
  yaw=.7;height=lambda x,y:-2+.5*x-.6*y
  for i,(center,size) in enumerate(stair_boxes([0,0,1],[4,3,.9],yaw,height)):
   self.assertAlmostEqual(center[2]+size[2]/2,1+.9*(i+1)/7)
   for x in [-size[0]/2,size[0]/2]:
    for y in [-size[1]/2,size[1]/2]:
     ground=height(center[0]+x*math.cos(yaw)-y*math.sin(yaw),center[1]+x*math.sin(yaw)+y*math.cos(yaw))
     self.assertLess(center[2]-size[2]/2,ground)
 def test_wall_preserves_crown_and_embeds_full_width_on_cross_slope(self):
  class Field:
   config={'walls':[{'points':[[0,0],[4,0]],'height':2,'thickness':1}]}
   def clear(self,*args):return False
  for wall,p,bottom,h,length,yaw in wall_segments({'route_field':Field(),'height':lambda x,y:2*y}):
   self.assertAlmostEqual(bottom+h,1.88)
   self.assertLess(bottom,-1.16)
 def test_missing_terrain_does_not_create_nan_footing(self):
  with self.assertRaisesRegex(ValueError,'Nonfinite'):footing_bottom(lambda x,y:float('nan'),(0,0),(2,3))
