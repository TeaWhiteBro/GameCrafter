import unittest
from adapters.blender.natural_court import evaluate


class NaturalCourtTests(unittest.TestCase):
    cfg = {'court_radii': [15, 13]}

    def test_continuous_gentle_terrain(self):
        result = evaluate(self.cfg, lambda x,y: .14 + .1*x, lambda x,y: .14 + .1*x)
        self.assertTrue(result['passed'])
        self.assertGreater(result['samples'], 40)

    def test_missing_support(self):
        self.assertFalse(evaluate(self.cfg, lambda x,y: None if x>0 else .14, lambda x,y:.14)['passed'])

    def test_steep_mesh_even_if_authoring_agrees(self):
        self.assertFalse(evaluate(self.cfg, lambda x,y:x, lambda x,y:x)['passed'])

    def test_displaced_mesh(self):
        self.assertFalse(evaluate(self.cfg, lambda x,y:.7, lambda x,y:.14)['passed'])

    def test_nonfinite_mesh(self):
        self.assertFalse(evaluate(self.cfg, lambda x,y:float('nan'), lambda x,y:.14)['passed'])
