import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from exploration import RouteField
from route_banks import offset,validate
class BankTests(unittest.TestCase):
 def setup_field(self):
  cfg={'routes':[{'id':'stream','points':[[-10,0,0],[10,0,0]],'width':3}],'route_banks':[{'center':[0,0],'radii':[12,10],'height':3,'route_ids':['stream'],'bank_width':5.5,'corridor_margin':.85}]}
  return cfg,RouteField(cfg)
 def test_corridor_and_outer_terrain_preserved(self):
  cfg,f=self.setup_field()
  for y in [-2,-1,0,1,2,10]:self.assertEqual(offset(cfg,f,0,y),0)
  self.assertGreater(offset(cfg,f,0,5),2)
 def test_bank_has_smooth_zero_boundary(self):
  cfg,f=self.setup_field();self.assertLess(offset(cfg,f,0,2.351),1e-5);self.assertLess(offset(cfg,f,0,7.849),1e-5)
 def test_invalid_bank_and_unknown_route_are_rejected(self):
  cfg,f=self.setup_field();validate(cfg)
  for key,value in [('radii',[0,10]),('bank_width',0),('route_ids',['missing'])]:
   bad={**cfg,'route_banks':[{**cfg['route_banks'][0],key:value}]}
   with self.assertRaises(ValueError):validate(bad)
 def test_nearest_parallel_route_switch_has_no_height_step(self):
  cfg={'routes':[{'id':'banked','points':[[-20,0,0],[20,0,0]],'width':3},{'id':'return','points':[[-20,10,2],[20,10,2]],'width':3}], 'route_banks':[{'center':[0,4],'radii':[18,15],'height':3,'route_ids':['banked'],'bank_width':7,'corridor_margin':.85}]}
  f=RouteField(cfg);a=offset(cfg,f,0,4.999);b=offset(cfg,f,0,5.001)
  self.assertGreater(min(a,b),1)
  self.assertLess(abs(a-b),.01)
  for y in [9,10,11]:self.assertEqual(offset(cfg,f,0,y),0)
 def test_eroded_profiles_preserve_all_walking_and_foundation_samples(self):
  cfg,f=self.setup_field();cfg['route_banks'][0].update(profile_exponent=.92,erosion_strength=.62,erosion_scale_m=1.45)
  cfg['foundation_pads']=[{'center':[0,5,0],'radius':1.3}];f=RouteField(cfg);validate(cfg)
  for x in range(-9,10):
   for y in [-2,-1,0,1,2]:self.assertEqual(offset(cfg,f,x,y),0)
  for x,y in [(0,5),(.8,5),(0,5.9)]:self.assertEqual(offset(cfg,f,x,y),0)
  values=[offset(cfg,f,x/2,y/2) for x in range(-20,21) for y in range(-20,21)]
  self.assertGreater(max(values),.5);self.assertGreaterEqual(min(values),0);self.assertLessEqual(max(values),3)
 def test_nonfinite_or_extreme_erosion_parameters_fail_validation(self):
  cfg,_=self.setup_field()
  for key,value in [('profile_exponent',.01),('erosion_strength',float('nan')),('erosion_scale_m',0),('erosion_strength',True)]:
   bad={**cfg,'route_banks':[{**cfg['route_banks'][0],key:value}]}
   with self.subTest(key=key),self.assertRaises(ValueError):validate(bad)
