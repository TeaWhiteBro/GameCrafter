import unittest
from adapters.blender.horizon_terrain import geometry

class HorizonTests(unittest.TestCase):
    def test_boundary_is_exact_and_interior_remains_open(self):
        height=lambda x,y:x*.03+y*.01
        v,f=geometry(100,1,height,{'ring_offsets_m':[0,10,40,120,500]})
        self.assertEqual(len(v),2000)
        for x,y,z in v[:400]:
            self.assertEqual(max(abs(x),abs(y)),50)
            self.assertEqual(z,height(x,y))
        for face in f:
            xyz=[v[i] for i in face];cx=sum(p[0] for p in xyz)/4;cy=sum(p[1] for p in xyz)/4
            self.assertGreaterEqual(max(abs(cx),abs(cy)),50)
            area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(xyz,xyz[1:]+xyz[:1]))
            self.assertGreater(area,0)
    def test_reversed_or_unbounded_ring_rejected(self):
        for offsets in ([1,120],[0,30,20,200],[0,5000]):
            with self.assertRaises(ValueError):geometry(100,1,lambda x,y:0,{'ring_offsets_m':offsets})
    def test_outer_blend_samples_its_actual_world_position(self):
        height=lambda x,y:x*.03+y*.01
        v,_=geometry(100,1,height,{'ring_offsets_m':[0,40,500],'height_m':0})
        x,y,z=v[400];t=.4*.4*(3-2*.4)
        self.assertAlmostEqual(z,height(x,y)*(1-t)+18*(40/500)**2*t)
