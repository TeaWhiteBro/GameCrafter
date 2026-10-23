import pathlib,random,sys,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'adapters/blender'))
from exploration import RouteField
from landscape_routes import build_paving

class RaisedPathTests(unittest.TestCase):
    def test_modular_route_uses_the_same_raised_foot_elevation(self):
        config={'paving_material':'stone','paving_style':'modular','routes':[{'id':'crossing','width':3,
            'points':[[0,0,.4],[0,7,.4]],'surface':'stone','raised_surface':True}], 'places':[]}
        crowns=[]
        def mesh(name,vertices,faces,material,**kw):
            if name=='Intact modular paving slab':crowns.append(max(v[2] for v in vertices))
        build_paving({'cfg':{},'route_field':RouteField(config),'height':lambda x,y:-.5,
            'mesh':mesh,'finish_stone':lambda ob,w:ob,'rng':random.Random(17)})
        self.assertGreater(len(crowns),25)
        self.assertTrue(all(abs(z-.445)<1e-6 for z in crowns))

    def test_excavated_bed_does_not_pull_authored_raised_paving_under_water(self):
        config={'paving_material':'stone','routes':[{'id':'crossing','width':3,
            'points':[[0,0,.4],[0,7,.4]],'surface':'stone','raised_surface':True}],
            'places':[]}
        emitted=[]
        def mesh(name,vertices,faces,material,**kw):
            emitted.append((name,np.asarray(vertices),faces,kw))
        api={'route_field':RouteField(config),'height':lambda x,y:-.5,
            'mesh':mesh,'finish_stone':lambda ob,w:ob,'rng':random.Random(17)}
        build_paving(api)
        crowns=[v[-1,2] for name,v,faces,kw in emitted if name=='Embedded paving']
        self.assertGreater(len(crowns),30)
        self.assertTrue(all(abs(z-.422)<1e-6 for z in crowns))
        beds=[(v,faces,kw) for name,v,faces,kw in emitted if 'bedding' in name]
        self.assertEqual(len(beds),1)
        for v,faces,kw in beds:
            self.assertTrue(kw.get('preserve_winding'))
            for face in faces:
                a,b,c=v[list(face)]
                self.assertGreater(np.cross(b-a,c-a)[2],0)
            center=v[np.linalg.norm(v[:,:2]-[0,3],axis=1).argmin()]
            self.assertAlmostEqual(center[2],.406,places=6)

if __name__=='__main__':unittest.main()
