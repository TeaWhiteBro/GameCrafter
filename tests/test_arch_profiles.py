import math,unittest
from adapters.blender.arch_profiles import parameters,ordinate
class ArchProfileTests(unittest.TestCase):
 def test_both_profiles_preserve_width_spring_and_total_height(self):
  for profile in ['round','pointed']:
   spring,rise=parameters(2.5,6,profile)
   self.assertAlmostEqual(ordinate(0,2.5,2.5,rise,profile),0)
   self.assertAlmostEqual(ordinate(math.pi,2.5,2.5,rise,profile),0)
   self.assertAlmostEqual(spring+ordinate(math.pi/2,2.5,2.5,rise,profile),6)
   self.assertGreater(spring,2)
 def test_pointed_profile_has_finite_thickness_and_apex_slope(self):
  spring,rise=parameters(2.5,6,'pointed')
  for i in range(101):
   a=math.pi*i/100
   self.assertGreaterEqual(ordinate(a,2.5,2.5,rise,'pointed'),ordinate(a,2.1,2.5,rise,'pointed'))
  apex=ordinate(math.pi/2,2.5,2.5,rise,'pointed')
  self.assertGreater((apex-ordinate(math.pi/2-.001,2.5,2.5,rise,'pointed'))/.001,.5)
