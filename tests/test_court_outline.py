import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from adapters.blender.court_outline import outline, prism, contains
from adapters.blender.court_exposure import evaluate


class CourtOutlineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'court_center':[0,8], 'court_radii':[8,8], 'court_base_z':.105,
                    'paving_style':'modular',
                    'court_outline':[[-4.8,0],[8,0],[8,12.4],[4.8,16],[-8,16],[-8,3.2]]}

    def test_rgb_tessellation_and_whitebox_share_complete_footprint(self):
        from adapters.blender.modular_paving import cells
        shape = outline(self.cfg)
        area = lambda p: abs(sum(a[0]*p[(i+1)%len(p)][1]-a[1]*p[(i+1)%len(p)][0] for i,a in enumerate(p)))/2
        self.assertAlmostEqual(sum(area(p) for p in cells(shape, joint=0)), area(shape), places=6)
        vertices, faces = prism(self.cfg)
        self.assertEqual([p[:2] for p in vertices[6:]], shape)
        self.assertAlmostEqual(vertices[-1][2], .24)
        self.assertEqual(len(faces), 8)
        self.assertFalse(contains(shape, [-7.9,.1]))
        self.assertTrue(contains(shape, [0,8]))

    def test_actual_interior_is_probed_and_missing_paving_still_fails(self):
        shape = outline(self.cfg)
        result = evaluate(self.cfg, lambda x,y:.14, lambda x,y:.24)
        self.assertTrue(result['passed'])
        self.assertGreater(result['samples'], 65)
        self.assertTrue(all(contains(shape,r['xy_m']) for r in result['rows']))
        self.assertFalse(evaluate(self.cfg, lambda x,y:.14, lambda x,y:.24 if x<0 else None)['passed'])
        self.assertFalse(evaluate(self.cfg, lambda x,y:.25, lambda x,y:.24)['passed'])

    def test_invalid_outline_is_rejected_before_geometry(self):
        for shape in [[[-8,0],[8,16],[-8,16],[8,0]], [[-8,0],[8,0],[0,8],[8,16],[-8,16]],
                      [[-9,0],[8,0],[8,16],[-9,16]], [[-8,0],[8,0],[8,0],[8,16],[-8,16]],
                      [[-8,0],[float('nan'),0],[8,16],[-8,16]]]:
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                outline(dict(self.cfg,court_outline=shape))

    def test_old_rectangular_content_and_reverse_winding_remain_valid(self):
        cfg = dict(self.cfg)
        del cfg['court_outline']
        self.assertEqual(outline(cfg), [(-8,0),(8,0),(8,16),(-8,16)])
        self.assertEqual(outline(dict(self.cfg,court_outline=self.cfg['court_outline'][::-1])),outline(self.cfg))


if __name__ == '__main__':
    unittest.main()
