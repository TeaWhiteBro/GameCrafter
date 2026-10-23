import copy
import unittest
from adapters.blender.authored_planting import validate, build
from adapters.blender.exploration import RouteField


class AuthoredPlantingTests(unittest.TestCase):
    def setUp(self):
        self.field=RouteField({'routes':[{'id':'walk','width':3,'points':[[0,0,0],[0,10,0]]}],
                              'places':[{'center':[4,4,0],'radius':8,'clear_radius':8}]})
        self.region={'center':[4,4],'radii':[2,2],'count':1,
                     'palette':[{'asset':'new_fern','collision':False,'grounding':'base'}],
                     'authored_points':[[4,4,1.5,.8,60]]}

    def test_authored_gap_survives_broad_preallocation(self):
        self.assertTrue(self.field.clear(4,4))
        calls=[]
        count=build(self.region,dict(route_field=self.field,height=lambda x,y:1.3,
                                     instance=lambda *a,**kw:calls.append((a,kw))))
        self.assertEqual(count,1)
        self.assertEqual(calls[0][0][1],(4,4,1.3))
        self.assertFalse(calls[0][0][5])
        self.assertEqual(calls[0][1]['ground'],'base')

    def test_walk_clearance_is_never_waived(self):
        r=copy.deepcopy(self.region);r['authored_points'][0][:2]=[2.1,4]
        r['radii']=[3,3]
        with self.assertRaisesRegex(ValueError,'corridor'):validate(r,self.field)

    def test_large_or_colliding_foliage_rejected(self):
        for key,value in [('collision',True),('grounding',False)]:
            r=copy.deepcopy(self.region);r['palette'][0][key]=value
            with self.assertRaisesRegex(ValueError,'non-colliding'):validate(r,self.field)
        r=copy.deepcopy(self.region);r['authored_points'][0][2]=5
        with self.assertRaisesRegex(ValueError,'understory'):validate(r,self.field)

    def test_outside_region_and_nonfinite_rejected(self):
        for value in [20,float('nan')]:
            r=copy.deepcopy(self.region);r['authored_points'][0][0]=value
            with self.assertRaises(ValueError):validate(r,self.field)

    def test_counts_cannot_silently_lose_plants(self):
        r=copy.deepcopy(self.region);r['count']=10
        with self.assertRaisesRegex(ValueError,'count'):validate(r,self.field)
