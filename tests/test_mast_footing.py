import unittest
import numpy as np
from adapters.blender.mast_footing import build

class MastFootingTests(unittest.TestCase):
    def test_contact_and_proxy_consistency_on_sloped_terrain(self):
        item={'center':[3,-2],'base_z':5.25,'radius':1.3,'height':3.2,'material':'stone','metal_material':'iron'}
        terrain=lambda x,y:5.25+.08*(x-3)-.04*(y+2)
        captures=[]
        for proxy in [False,True]:
            emitted=[]
            build(item,terrain,lambda n,v,f,m,*a:emitted.append((n,np.asarray(v),f,m)),proxy)
            self.assertEqual(len(emitted),5)
            vertices=emitted[0][1]
            for x,y,z in vertices[:8]:self.assertLessEqual(z,terrain(x,y)-.179)
            for _,vs,_,_ in emitted:self.assertTrue(np.isfinite(vs).all())
            captures.append(emitted)
        for a,b in zip(*captures):np.testing.assert_array_equal(a[1],b[1])

if __name__=='__main__':unittest.main()
