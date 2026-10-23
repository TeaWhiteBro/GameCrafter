import unittest
from adapters.blender.route_banks import offset


class Field:
    def query(self,x,y,ids=None):return 4.,0.,2.,0


class BankFoundationTests(unittest.TestCase):
    def config(self):
        return {'route_banks':[{'center':[0,0],'radii':[20,20],'height':1.,'bank_width':5.,'corridor_margin':1.,'route_ids':['r']}]}

    def test_keeps_natural_court_flat(self):
        c=self.config();self.assertGreater(offset(c,Field(),4,0),.2)
        c['places']=[{'center':[0,0,0],'radius':15,'surface':'none'}]
        self.assertEqual(offset(c,Field(),4,0),0)

    def test_preserves_polygon_foundation(self):
        c=self.config();c['foundation_pads']=[{'center':[0,0,0],'radius':8,'outline':[[-8,-8],[8,-8],[8,8],[-8,8]]}]
        self.assertEqual(offset(c,Field(),4,0),0)
        self.assertGreater(offset(c,Field(),10,0),0)

    def test_unflattened_landmark_retains_natural_bank(self):
        c=self.config();expected=offset(c,Field(),4,0)
        c['places']=[{'center':[0,0,0],'radius':15,'flatten':False}]
        self.assertEqual(offset(c,Field(),4,0),expected)
