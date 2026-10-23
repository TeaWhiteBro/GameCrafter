import unittest,numpy as np
from adapters.blender.organic_paths import geometry,validate

class OrganicPathTests(unittest.TestCase):
    def test_closed_root_and_proxy_preserve_centerline_endpoints(self):
        item=dict(points=[[0,0,0],[1,1,1],[2,3,1],[4,3,.2]],radii=[.6,.4,.2,.04],material='bark')
        validate([item])
        sizes=[]
        for proxy,n in [(False,20),(True,8)]:
            vs,faces=geometry(item,proxy);vs=np.array(vs);sizes.append(len(vs))
            self.assertTrue(np.isfinite(vs).all());self.assertLess(np.linalg.norm(vs[:n].mean(0)),.02)
            self.assertLess(np.linalg.norm(vs[-n:].mean(0)-item['points'][-1]),.002)
            edges={}
            for face in faces:
                for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted((a,b)))]=edges.get(tuple(sorted((a,b))),0)+1
            self.assertTrue(all(v==2 for v in edges.values()))
        self.assertLess(sizes[1],sizes[0])
    def test_reject_invalid_paths(self):
        for item in [dict(points=[[0,0,0]]*3,radii=[.2]*3,material='bark'),dict(points=[[0,0,0],[1,1,1],[2,2,2]],radii=[.2,-.1,.1],material='bark')]:
            with self.assertRaises(ValueError):validate([item])
