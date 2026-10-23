import unittest
import numpy as np
from adapters.blender.terrain_channels import build,bed,half_width

class ChannelSurfaceTests(unittest.TestCase):
    def test_curved_channel_is_visible_from_above_in_both_directions(self):
        points=[[-36,-32],[-38,-22],[-39,-10],[-41,0],[-39,12],[-42,24]]
        for path in [points,points[::-1]]:
            captured=[]
            channel={'points':path,'width':5,'bank_width':2.5,'bed_depth':.3,'surface_z':-.3,'material':'ice'}
            def mesh(name,vs,fs,mat,**kwargs):captured.append((np.asarray(vs),fs,kwargs))
            build({'cfg':{'terrain_channels':[channel]},'mesh':mesh})
            self.assertEqual(len(captured),1)
            vertices,faces,kw=captured[0]
            self.assertTrue(kw.get('preserve_winding'))
            for face in faces:
                poly=vertices[list(face)]
                normal=sum((np.cross(a,b) for a,b in zip(poly,np.roll(poly,-1,axis=0))),np.zeros(3))
                self.assertGreater(normal[2],0)
            np.testing.assert_allclose(vertices[:,2],-.3)

    def test_irregular_surface_and_excavation_agree(self):
        c={'points':[[0,-20],[0,20]],'width':5,'bank_width':2,'bed_depth':.3,'surface_z':-.3,'material':'ice','edge_variation':.2}
        captured=[]
        build({'cfg':{'terrain_channels':[c]},'mesh':lambda name,vs,fs,mat,**kw:captured.extend(vs)})
        self.assertGreater(len(captured),100)
        for x,y,z in captured:
            self.assertAlmostEqual(abs(x),half_width(c,0,y))
            self.assertAlmostEqual(bed([c],x,y,0),-.6)
        self.assertGreater(np.ptp([abs(p[0]) for p in captured]),.2)

if __name__=='__main__':unittest.main()
