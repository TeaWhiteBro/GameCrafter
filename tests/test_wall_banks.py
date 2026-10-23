import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from exploration import RouteField
from wall_banks import offset,validate

class WallBankTests(unittest.TestCase):
 def config(self):
  return {'routes':[{'id':'walk','points':[[-20,-5,0],[20,-5,0]],'width':3}], 'walls':[{'points':[[-10,0],[10,0]],'bank_side':1,'bank_height':1.2,'bank_width':4}]}
 def test_backfill_leaves_wall_center_and_other_side_unchanged(self):
  c=self.config();f=RouteField(c)
  self.assertEqual(offset(c,f,0,0),0);self.assertEqual(offset(c,f,0,-1),0)
  self.assertGreater(offset(c,f,0,1),1.1);self.assertEqual(offset(c,f,0,4),0)
 def test_foundation_and_crossing_stay_clear(self):
  c=self.config();c['routes'].append({'id':'cross','points':[[0,-10,0],[0,10,0]],'width':3});f=RouteField(c)
  self.assertEqual(offset(c,f,0,1),0)
  c['foundation_pads']=[{'center':[7,1,0],'radius':2}];f=RouteField(c)
  self.assertEqual(offset(c,f,7,1),0)
 def test_invalid_side_rejected(self):
  c=self.config();c['walls'][0]['bank_side']=0
  with self.assertRaises(ValueError):validate(c)
 def test_terrain_only_bank_preserves_same_grade_without_wall(self):
  c=self.config();f=RouteField(c);expected=offset(c,f,0,1)
  c['terrain_banks']=c.pop('walls');validate(c)
  self.assertAlmostEqual(offset(c,RouteField(c),0,1),expected)
