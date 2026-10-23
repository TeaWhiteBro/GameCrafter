import unittest
import numpy as np
from adapters.blender.route_elevation import interpolate

class RouteElevationTests(unittest.TestCase):
    def test_ramp_does_not_raise_flat_destination(self):
        points=[[-25,-2,.135],[-25,12,3.335],[-25,21,3.335]]
        for t in np.linspace(0,1,101):self.assertAlmostEqual(interpolate(points,1,t),3.335)
    def test_monotone_intervals_do_not_overshoot(self):
        for z in [[0,2,2.2,5],[5,2.2,2,0],[0,3,1,1]]:
            points=[[x,0,h] for x,h in zip([0,1,8,10],z)]
            for i in range(3):
                for t in np.linspace(0,1,101):
                    value=interpolate(points,i,t)
                    self.assertGreaterEqual(value,min(z[i:i+2])-1e-9)
                    self.assertLessEqual(value,max(z[i:i+2])+1e-9)
    def test_two_controls_remain_linear(self):
        self.assertAlmostEqual(interpolate([[0,0,0],[2,0,4]],0,.3),1.2)

if __name__=='__main__':unittest.main()
