from collections import Counter
import unittest
from adapters.blender.masonry_destinations import build,validate

class VaultTests(unittest.TestCase):
    def test_detailed_and_proxy_roofs_are_closed_and_share_outer_extent(self):
        item={'kind':'masonry_gallery','center':[6,9],'size':[9,15],'height':5.8,'bays':3,
              'material':'stone','roof_material':'stone','roof_profile':'barrel','roof_rise':2.1,'yaw_deg':90}
        extents=[]
        for proxy in [False,True]:
            geometry=[]
            build(item,{'height':lambda x,y:0},proxy,lambda *a,**k:None,lambda *a,**k:None,lambda *a,**k:None,
                  lambda name,vs,fs,*a,**k:geometry.append((vs,fs)))
            self.assertEqual(len(geometry),1)
            vs,fs=geometry[0];edges=Counter()
            for f in fs:
                for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted([a,b]))]+=1
            self.assertEqual(set(edges.values()),{2})
            extents.append([(min(p[k] for p in vs),max(p[k] for p in vs)) for k in range(3)])
        self.assertEqual(extents[0],extents[1])
    def test_lintel_portals_preserve_structural_proxy_and_openings(self):
        item={'kind':'masonry_gallery','center':[0,0],'size':[6.4,6],'height':4.5,'bays':2,
              'material':'stone','roof_profile':'flat','portal_profile':'lintel'}
        structural=[]
        for proxy in [False,True]:
            boxes=[];arches=[]
            build(item,{'height':lambda x,y:0},proxy,
                  lambda *a,**k:boxes.append(a),lambda *a,**k:None,lambda *a,**k:arches.append(a))
            self.assertEqual(arches,[])
            beams=[q for q in boxes if q[0]=='Gallery stone lintel']
            self.assertEqual(len(beams),4)
            self.assertTrue(all(q[1][2]-q[2][2]/2>3 for q in beams))
            structural.append(beams)
        self.assertEqual(structural[0],structural[1])
    def test_unknown_portal_profile_rejected(self):
        with self.assertRaisesRegex(ValueError,'portal profile'):
            validate({'kind':'masonry_gallery','center':[0,0],'size':[6,6],
                      'material':'stone','portal_profile':'unsupported'})
