import copy
import unittest
from game_pipeline.core import StageError
from game_pipeline.planning_agents import validate_composition_regions

class CompositionRegionTests(unittest.TestCase):
    def fixture(self):
        modules=[];regions=[]
        for i,purpose in enumerate(['Furnace heat production','Freight loading and storage','Elevated control and instrumentation']):
            modules.extend([{'kind':'street_frontage','center':[i*15,0]}, {'kind':'box_assembly','center':[i*15+2,0]}])
            regions.append({'id':str(i),'purpose':purpose,'center':[i*15,0],'radius_m':8,
                'members':[{'collection':'modular_architecture','index':i*2+j} for j in range(2)]})
        return {'composition':{'modular_architecture':modules,'exploration':{'composition_regions':regions}}}
    def test_distinct_built_regions_pass_without_invented_vegetation(self):
        self.assertEqual(validate_composition_regions(self.fixture()),3)
    def test_empty_or_reused_or_remote_geometry_fails(self):
        for mode in ['empty','reused','remote','missing','same_center','same_purpose']:
            scene=copy.deepcopy(self.fixture());r=scene['composition']['exploration']['composition_regions']
            if mode=='empty':r[0]['members']=[]
            if mode=='reused':r[1]['members'][0]=r[0]['members'][0]
            if mode=='remote':scene['composition']['modular_architecture'][0]['center']=[100,100]
            if mode=='missing':r[0]['members'][0]['index']=999
            if mode=='same_center':r[1]['center']=r[0]['center']
            if mode=='same_purpose':r[1]['purpose']=r[0]['purpose']
            with self.subTest(mode=mode),self.assertRaises(StageError):validate_composition_regions(scene)
