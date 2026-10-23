import unittest,sys,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from curved_wall import build_wall

def triangles(item,proxy=False):
    result=[]
    def emit(name,vs,fs,mat):
        v=np.asarray(vs)
        for f in fs:
            for i in range(1,len(f)-1):result.append(v[[f[0],f[i],f[i+1]]])
    build_wall(item,emit,'stone',proxy)
    return np.asarray(result)

def ray_hit(tris,o,d):
    # Independent triangle intersection, not a call back into the wall generator.
    a=tris[:,0];e1=tris[:,1]-a;e2=tris[:,2]-a;p=np.cross(d,e2);det=np.sum(e1*p,axis=1)
    valid=np.abs(det)>1e-9;inv=np.zeros_like(det);inv[valid]=1/det[valid]
    t=o-a;u=np.sum(t*p,axis=1)*inv;q=np.cross(t,e1);v=np.sum(d*q,axis=1)*inv;distance=np.sum(e2*q,axis=1)*inv
    return bool(np.any(valid&(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)&(distance>0)&(distance<1.5)))

class CurvedWallTests(unittest.TestCase):
    def test_mortar_seams_are_solid_and_arch_apertures_remain_open(self):
        for rotation in [0,180]:
            item={'center':[3,-7],'radius':4.3,'height':6.5,'base_z':.08,'rotation_deg':rotation,'opening_degrees':112}
            for proxy in [False,True]:
                tris=triangles(item,proxy);rot=math.radians(rotation)
                for window in [math.pi,1.5*math.pi,2*math.pi]:
                    for offset,z,expected in [(0,2.8,False),(.29,5.5,False),(0,5.9,True),(.68,2.8,True),(.68,6.5/18*7,True),(0,1.9,True)]:
                        a=rot+window+offset/4.3;d=np.array([math.cos(a),math.sin(a),0]);o=np.array([3,-7,.08+z])+d*(4.3-.75)
                        self.assertEqual(ray_hit(tris,o,d),expected,(rotation,proxy,window,offset,z))
    def test_wall_has_a_coarser_companion_and_rejects_degenerate_dimensions(self):
        item={'center':[0,0],'radius':5,'height':6}
        self.assertLess(len(triangles(item,True)),len(triangles(item)))
        for change in [{'radius':0},{'height':2},{'opening_degrees':360},{'height':float('nan')}]:
            with self.assertRaises(ValueError):triangles({**item,**change})
