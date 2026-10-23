import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_pipeline.contracts import validate_scene_resources,ContractError

class ExplorationContract(unittest.TestCase):
    def setUp(self):
        self.scene={'materials':{'soil':{},'stone':{}},'floor_material':'soil','path_material':'stone','objects':[],
          'composition':{'terrain_extent_m':120,'exploration':{'paving_material':'stone','wall_material':'stone','rock_asset':'rock','plant_asset':'plant',
          'play_bounds':{'min':[-40,-40],'max':[40,40]},'encounter_radius_m':12,'routes':[{'width':3,'points':[[0,0,0],[0,20,2]]}]}}}
        self.machine={'mesh_library':{'rock':{},'plant':{}}}
    def test_walkable_route_accepted(self):validate_scene_resources(self.scene,self.machine)
    def test_invalid_paving_zone_semantics_rejected(self):
        self.scene['composition']['exploration']['places']=[{'center':[0,0,0],'radius':4,'material_zones':[{'outline':[[-2,-2],[2,-2],[2,2],[-2,2]],'material':'stone'}]}]
        with self.assertRaisesRegex(ContractError,'paving semantics'):validate_scene_resources(self.scene,self.machine)
        self.scene['materials']['stone']['semantic_class']='paving'
        validate_scene_resources(self.scene,self.machine)
        self.scene['composition']['exploration']['places'][0]['material_zones'][0]['outline']=[[0,0],[1,1],[2,2]]
        with self.assertRaisesRegex(ContractError,'nondegenerate'):validate_scene_resources(self.scene,self.machine)
    def test_zoned_paving_preserves_geometry_without_overlay(self):
        import random
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from landscape_routes import fitted_patch
        captures=[]
        def make(zones):
            result=[]
            def mesh(name,verts,faces,mat,**kwargs):result.append((verts,faces,mat));return verts
            api={'rng':random.Random(3),'height':lambda x,y:.15*x,'mesh':mesh,'finish_stone':lambda ob,w:ob}
            fitted_patch(api,[[-3,-3],[3,-3],[3,3],[-3,3]],'stone',material_zones=zones)
            return result
        before=make([]);after=make([{'outline':[[0,-4],[4,-4],[4,4],[0,4]],'material':'brick'}])
        self.assertEqual([(v,f) for v,f,m in before],[(v,f) for v,f,m in after])
        self.assertEqual({m for v,f,m in after},{'brick','stone'})
        for verts,faces,mat in after:self.assertEqual(mat,'brick' if verts[-1][0]>=0 else 'stone')
    def test_cliff_cannot_be_labeled_as_path(self):
        self.scene['composition']['exploration']['routes'][0]['points'][1][2]=18
        with self.assertRaisesRegex(ContractError,'steep'):validate_scene_resources(self.scene,self.machine)
    def test_route_outside_collision_bounds_fails(self):
        self.scene['composition']['exploration']['routes'][0]['points'][1][1]=45
        with self.assertRaisesRegex(ContractError,'outside'):validate_scene_resources(self.scene,self.machine)
    def test_disconnected_itinerary_rejected(self):
        self.scene['composition']['exploration']['routes'].append({'width':3,'points':[[20,20,2],[30,30,2]]})
        with self.assertRaisesRegex(ContractError,'connected'):validate_scene_resources(self.scene,self.machine)

    def network(self):
        ex=self.scene['composition']['exploration']
        ex['routes']=[{'id':'entry','width':3,'points':[[0,0,0],[0,20,2]]},
                      {'id':'spur','width':3,'points':[[0,20,2],[12,22,3]]}]
        ex['itinerary']=[{'route':'entry'},{'route':'spur'},{'route':'spur','reverse':True},{'route':'entry','reverse':True}]
        return ex

    def test_spur_retrace_is_valid_without_duplicate_geometry(self):
        ex=self.network();validate_scene_resources(self.scene,self.machine)
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from exploration import RouteField
        from landscape_routes import itinerary
        field=RouteField(ex);walk=itinerary(field)
        self.assertEqual(len(field.routes),2)
        self.assertEqual(walk[0],walk[-1])
        self.assertIn([12.,22.,3.],walk)

    def test_incorrect_spur_direction_cannot_teleport(self):
        ex=self.network();ex['itinerary'][2]['reverse']=False
        with self.assertRaisesRegex(ContractError,'connected'):validate_scene_resources(self.scene,self.machine)

    def test_unvisited_branch_cannot_pass(self):
        ex=self.network();ex['itinerary']=[{'route':'entry'}]
        with self.assertRaisesRegex(ContractError,'every route'):validate_scene_resources(self.scene,self.machine)

    def test_width_profile_cannot_escape_bounds(self):
        ex=self.network();ex['routes'][0]['width_profile']=[3,12,3]
        with self.assertRaisesRegex(ContractError,'width profile'):validate_scene_resources(self.scene,self.machine)

    def test_paving_follows_sloping_ground_instead_of_floating(self):
        import random
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from landscape_routes import fitted_patch
        captured=[]
        def mesh(name,verts,faces,mat,**kwargs):captured.append(verts);return verts
        ground=lambda x,y:x*.23+y*.10
        api={'rng':random.Random(8),'height':ground,'mesh':mesh,'finish_stone':lambda ob,w:ob}
        fitted_patch(api,[[0,0],[5,0],[5,3],[0,3]],'stone')
        self.assertGreater(len(captured),10)
        for verts in captured:
            n=(len(verts)-1)//2
            for x,y,z in verts[:n]:self.assertLess(z,ground(x,y))
            # The upper stones clear continuous bedding, remain under 4 cm
            # above terrain and keep their underside buried.
            for x,y,z in verts[n:]:self.assertGreaterEqual(z-ground(x,y),.0159);self.assertLessEqual(z-ground(x,y),.0401)

    def test_authored_enclosure_keeps_wall_but_reserves_actual_route(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from exploration import RouteField
        from landscape_routes import wall_segments
        cfg={'routes':[{'width':2,'points':[[0,-8,0],[0,8,0]]}],
             'places':[{'center':[0,0,0],'radius':6}],
             'walls':[{'points':[[-5,3],[5,3]],'height':1,'enclosure':True}]}
        api={'route_field':RouteField(cfg),'height':lambda x,y:0}
        pieces=list(wall_segments(api))
        self.assertGreater(len(pieces),4)
        self.assertTrue(all(abs(p[1][0])>=1.8 for p in pieces))
        cfg['walls'][0]['enclosure']=False
        self.assertEqual(list(wall_segments(api)),[])

    def test_paver_top_is_planar_with_hard_side_normals(self):
        import random,numpy as np
        from landscape_routes import fitted_patch
        captured=[]
        def mesh(name,verts,faces,mat,**kw):captured.append((np.array(verts),kw));return verts
        fitted_patch({'rng':random.Random(8),'height':lambda x,y:.12*x+.04*y,'mesh':mesh,'finish_stone':lambda ob,w:ob},[[0,0],[3,0],[3,2],[0,2]],'stone')
        for vs,kw in captured:
            n=(len(vs)-1)//2;top=vs[n:]
            self.assertFalse(kw['smooth_faces'])
            residual=top[:,2]-(.12*top[:,0]+.04*top[:,1]+.022)
            self.assertLess(np.abs(residual).max(),1e-10)

    def test_scan_underside_settles_across_slope_not_just_at_center(self):
        import numpy as np
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from landscape_routes import rock_origin
        verts=[[x,y,0] for x in np.linspace(-.5,.5,9) for y in [-.5,0,.5]]+[[0,0,1]]
        z,audit=rock_origin(verts,[0,0,1],[6,4,3],.8,lambda x,y:x*.4-y*.2)
        self.assertLess(z,0)
        self.assertEqual(audit['buried_support_fraction'],1.)
        self.assertGreater(audit['support_samples'],20)

    def test_bent_paving_sections_share_the_same_join(self):
        import numpy as np
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from landscape_routes import paving_strips
        points=np.array([[0,0,0],[1,0,0],[2,.2,0],[3,.7,0],[3.6,1.4,0],[4,2.2,0],[4.1,3.2,0]],float)
        patches=list(paving_strips(points,np.array([3,3,3.1,3.2,3.2,3,2.8])))
        self.assertEqual(len(patches),2)
        np.testing.assert_allclose(patches[0][3][1],patches[1][3][0],atol=1e-10)
        np.testing.assert_allclose(patches[0][3][2],patches[1][3][3],atol=1e-10)

    def test_rock_tip_contact_does_not_excuse_a_suspended_lower_flank(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from landscape_routes import rock_origin
        # A narrow low tip alone passes the former 18% band, but a broad
        # bevel at 40% remains above the falling ground on its downhill side.
        vertices=[[0,0,0],[-1,0,.4],[1,0,.4],[0,-1,.4],[0,1,.4],[0,0,1]]
        z,audit=rock_origin(vertices,[0,0,0],[1,1,1],0,lambda x,y:-.2*x)
        self.assertLessEqual(z+.4,-.2)
        self.assertEqual(audit['contact_band_height_fraction'],.45)
        self.assertEqual(audit['buried_support_fraction'],1.)

    def test_bedding_unites_branch_and_destination_without_floating_shoulder(self):
        import numpy as np
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
        from exploration import RouteField
        from surface_bedding import build
        cfg={'paving_material':'stone','routes':[{'width':3,'points':[[0,0,0],[0,10,1]]},{'width':3,'points':[[0,6,.6],[5,6,1]]}],
             'places':[{'center':[0,10,1],'radius':3}]}
        saved=[]
        ground=lambda x,y:.1*y+.03*x
        def mesh(name,vs,fs,mat,**kw):saved.append((np.array(vs),fs))
        build({'route_field':RouteField(cfg),'height':ground,'mesh':mesh})
        self.assertEqual(len(saved),1)
        vs,fs=saved[0];adj=[set() for _ in vs]
        for f in fs:
            for a,b in zip(f,f[1:]+f[:1]):adj[a].add(b);adj[b].add(a)
        todo=[0];seen={0}
        while todo:
            for n in adj[todo.pop()]-seen:seen.add(n);todo.append(n)
        self.assertEqual(len(seen),len(vs))
        gaps=vs[:,2]-(vs[:,1]*.1+vs[:,0]*.03)
        self.assertLessEqual(gaps.max(),.00601)
        self.assertLess(gaps.min(),-.07)
        for xy in [[0,1],[0,6],[0,9],[0,11],[4,6]]:
            nearest=np.linalg.norm(vs[:,:2]-xy,axis=1).argmin()
            self.assertGreater(gaps[nearest],.005)
        cfg['bedding_grid_m']=0
        with self.assertRaisesRegex(ValueError,'bedding_grid_m'):build({'route_field':RouteField(cfg),'height':ground,'mesh':mesh})

    def test_invalid_enclosure_and_fade_are_rejected_before_build(self):
        ex=self.scene['composition']['exploration']
        ex['walls']=[{'points':[[0,0],[5,0]],'enclosure':'false'}]
        with self.assertRaisesRegex(ContractError,'enclosure'):validate_scene_resources(self.scene,self.machine)
        ex['walls'][0]['enclosure']=False
        ex['routes'][0]['edge_fade_m']=-1
        with self.assertRaisesRegex(ContractError,'edge fade'):validate_scene_resources(self.scene,self.machine)

if __name__=='__main__':unittest.main()
