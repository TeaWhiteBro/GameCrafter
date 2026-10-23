import unittest
import numpy as np
from adapters.blender.exploration import RouteField

class StraightRamp(unittest.TestCase):
    def test_endpoint_grade_matches_authored_physical_deck(self):
        for reverse in [False,True]:
            points=[[0,0,0],[0,10,2.8]]
            if reverse:points.reverse()
            field=RouteField({'routes':[{'id':'ramp','points':points,'width':3}]})
            grade=np.abs(field.d[:,2])/np.linalg.norm(field.d[:,:2],axis=1)
            np.testing.assert_allclose(grade,.28,rtol=1e-12)
            np.testing.assert_allclose(field.a[:,2],field.a[:,1]*.28,atol=1e-12)
