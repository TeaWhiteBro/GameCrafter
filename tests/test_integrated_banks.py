import math,unittest
from adapters.blender.terrain_channels import bank_outline,integrated_bank_meshes

class IntegratedBanksTests(unittest.TestCase):
    def setUp(self):
        self.channel={'points':[[0,0],[10,0]],'width':4,'bank_width':1,'surface_z':.06,'bed_depth':.5,
            'material':'water','integrated_banks':True,'coping_material':'stone'}

    def test_round_caps_cover_excavation_and_preserve_upward_sheet(self):
        shape=bank_outline(self.channel,1)
        self.assertAlmostEqual(min(p[0] for p in shape),-3)
        self.assertAlmostEqual(max(p[0] for p in shape),13)
        area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(shape,shape[1:]+shape[:1]))/2
        self.assertAlmostEqual(area,60+9*math.pi,delta=.2)
        meshes=[]
        class Field:
            def clear(self,x,y,margin):return False
        integrated_bank_meshes({'mesh':lambda name,v,f,m,**kw:meshes.append((name,v,f,kw)),
            'route_field':Field(),'height':lambda x,y:.2},self.channel)
        self.assertTrue(meshes[0][3]['preserve_winding'])
        self.assertTrue(all(abs(v[2]-.06)<1e-8 for v in meshes[0][1]))

    def test_coping_leaves_actual_route_open_and_extends_to_pool_bed(self):
        meshes=[]
        class Field:
            def clear(self,x,y,margin):return 3<x<7
        integrated_bank_meshes({'mesh':lambda name,v,f,m,**kw:meshes.append((name,v,f)),
            'route_field':Field(),'height':lambda x,y:.2},self.channel)
        walls=[v for name,v,f in meshes if name=='Pool retaining wall']
        self.assertGreater(len(walls),20)
        for vertices in walls:
            self.assertLess(min(v[2] for v in vertices),-.5)
            center_x=sum(v[0] for v in vertices)/len(vertices)
            self.assertFalse(3<center_x<7)

if __name__=='__main__':unittest.main()
