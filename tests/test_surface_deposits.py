import copy
import math
import unittest
from adapters.blender.surface_deposits import validate, offset


class SurfaceDepositTests(unittest.TestCase):
    def setUp(self):
        self.items = [{'points': [[-21, 8], [-7, 8]], 'height': .14, 'width': 1.5}]

    def test_local_and_non_additive(self):
        validate(self.items)
        self.assertAlmostEqual(offset(self.items, -13, 8), .14)
        self.assertEqual(offset(self.items, 13, 8), 0.)
        self.assertEqual(offset(self.items, -13, -8), 0.)
        self.assertEqual(offset(self.items*2, -13, 8), offset(self.items, -13, 8))
        self.assertLess(offset(self.items, -21.8, 8), .14)

    def test_height_and_grade_stay_bounded(self):
        samples = [offset(self.items, -13, y/100) for y in range(400, 1201)]
        self.assertLessEqual(max(samples), .14)
        self.assertLess(max(abs(a-b)/.01 for a,b in zip(samples,samples[1:])), .2)

    def test_invalid_geometry_rejected(self):
        for key, value in [('height', math.nan), ('width', .1), ('points', [[0,0],[0,0]])]:
            bad = copy.deepcopy(self.items); bad[0][key] = value
            with self.assertRaises(ValueError): validate(bad)


if __name__ == '__main__':
    unittest.main()
