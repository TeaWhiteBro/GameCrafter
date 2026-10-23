import unittest
from adapters.blender.terrain_modifiers import apply
from adapters.blender.exploration import RouteField


class TerrainModifierTests(unittest.TestCase):
    def test_deposit_survives_route_flattening_but_cannot_bury_stair_or_channel(self):
        field=RouteField({})
        deposit={'points':[[-8,0],[8,0]],'height':.2,'width':2}
        cfg={'surface_deposits':[deposit]}
        self.assertAlmostEqual(apply(cfg,field,0,0,0),.2)
        cfg['destination_details']=[{'kind':'terraced_foundation','center':[0,0],'size':[4,4],'base_z':0,'rise':1,'stair_run':2}]
        # The raised structure owns the final support envelope even when
        # terrain and deposited material start well above it.
        self.assertLessEqual(apply(cfg,field,0,0,10),.84+1e-8)
        cfg['terrain_channels']=[{'points':[[-8,0],[8,0]],'width':3,'bank_width':2,'surface_z':0,'bed_depth':1}]
        self.assertLessEqual(apply(cfg,field,0,0,10),-1)
        self.assertEqual(apply(cfg,field,30,30,2),2)

    def test_earth_ruts_remain_with_surface_deposits(self):
        route={'id':'earth','points':[[-10,0,0],[10,0,0]],'width':4,'surface':'earth',
               'wheel_ruts':{'spacing_m':1.6,'width_m':.4,'depth_m':.04}}
        cfg={'exploration':{'routes':[route]}}
        field=RouteField(cfg['exploration'])
        self.assertLess(apply(cfg,field,0,.8,0),-.03)
