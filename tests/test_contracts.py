import json,sys,unittest,tempfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game_pipeline.contracts import validate_spec,ContractError,load_spec,validate_rig,SEMANTIC_BONES,validate_scene_resources,normalize_design,validate_landmarks
from game_pipeline.cli import graph
from game_pipeline.local_adapters import review,normalize_texture_library
from game_pipeline.services import scene_layout
from game_pipeline.core import StageError

class ContractTests(unittest.TestCase):
    def setUp(self):self.spec=json.loads((ROOT/'examples/local_assets.spec.json').read_text())
    def test_content_neutral_spec_is_accepted(self):validate_spec(self.spec)
    def test_regional_routes_do_not_require_unused_legacy_scans(self):
        scene=self.spec['scene'];mat=scene['floor_material']
        ex={'composition_version':2,'paving_material':mat,'wall_material':mat,
            'play_bounds':{'min':[-20,-20],'max':[20,20]},'encounter_radius_m':12,
            'routes':[{'points':[[0,0,0],[5,0,0]],'width':3}]}
        scene['composition']={'terrain_extent_m':100,'exploration':ex}
        machine={'texture_library':{m.get('texture_set'):{} for m in scene['materials'].values()}}
        validate_scene_resources(scene,machine)
        ex['planting_regions']=[{'center':[10,10],'radii':[2,2],'count':1,'palette':[{'asset':'missing'}]}]
        with self.assertRaisesRegex(ContractError,'Unknown planting resource'):validate_scene_resources(scene,machine)
        ex.pop('planting_regions');ex['composition_version']=1
        with self.assertRaisesRegex(ContractError,'Exploration scan resources missing'):validate_scene_resources(scene,machine)
    def test_destination_container_error_reaches_bounded_scene_repair(self):
        scene=self.spec['scene'];scene['composition']={'destination_details':{'bell_tower':{'center':[0,0]}}}
        machine={'texture_library':{m.get('texture_set'):{} for m in scene['materials'].values()}}
        with self.assertRaisesRegex(ContractError,'array of objects'):validate_scene_resources(scene,machine)
    def test_spline_grade_is_checked_before_scene_construction(self):
        scene=self.spec['scene'];mat=scene['floor_material']
        ex={'composition_version':2,'paving_material':mat,'wall_material':mat,
            'play_bounds':{'min':[-40,-40],'max':[40,40]},'encounter_radius_m':12,
            'routes':[{'points':[[0,0,.135],[-13,-4,.135],[-25,0,.135],[-25,12,3.335],[-25,21,3.335]],'width':4.5}]}
        scene['composition']={'terrain_extent_m':120,'exploration':ex}
        machine={'texture_library':{m.get('texture_set'):{} for m in scene['materials'].values()}}
        with self.assertRaisesRegex(ContractError,'Smoothed exploration route'):validate_scene_resources(scene,machine)
        ex['routes'][0]['points'][2][1]=-2
        validate_scene_resources(scene,machine)
    def test_rooted_scan_footprint_mode_is_explicit(self):
        self.spec['scene']['objects']=[{'kind':'asset','asset':'rooted_scan','position':[0,0,0],'scale':[1,1,1],'material':self.spec['scene']['floor_material'],'snap_to_terrain':True,'grounding':'footprint'}]
        machine={'mesh_library':{'rooted_scan':{}},'texture_library':{m.get('texture_set'):{} for m in self.spec['scene']['materials'].values()}}
        validate_spec(self.spec);validate_scene_resources(self.spec['scene'],machine)
        self.spec['scene']['objects'][0]['grounding']='invented_mode'
        with self.assertRaisesRegex(ContractError,'Unknown scan grounding'):validate_scene_resources(self.spec['scene'],machine)
    def test_misnested_design_recovers_without_inventing_or_mutating(self):
        for key in ['spawns','lighting','gameplay']:self.spec['scene'][key]=self.spec.pop(key)
        result,repairs=normalize_design(self.spec);validate_spec(result)
        self.assertEqual(len(repairs),3);self.assertIn('spawns',self.spec['scene'])
        self.assertNotIn('spawns',self.spec)
    def test_conflicting_design_locations_fail(self):
        self.spec['scene']['spawns']={'player':[0,0,0],'boss':[0,0,0]}
        with self.assertRaisesRegex(ContractError,'Conflicting'):normalize_design(self.spec)
    def test_landmark_scale_drift_cannot_bind_hands_outside_mesh(self):
        names=['Hip','Waist','Spine01','Spine02','NeckTwist01','Head']+[p+n for p in ['L_','R_'] for n in ['Clavicle','Upperarm','Forearm','Hand','Thigh','Calf','Foot']]
        landmarks={name:[[0,0,.4],[0,0,.5]] for name in names}
        landmarks['L_Hand']=[[.58,-.01,.73],[.72,-.04,.71]]
        with self.assertRaisesRegex(ContractError,'outside source geometry'):
            validate_landmarks({'source_forward':'+X','landmarks':landmarks},[[-.131,-.485,-.5],[.131,.485,.5]])
    def test_front_camera_cannot_be_confused_with_optical_view_direction(self):
        with self.assertRaisesRegex(ContractError,'contradicts'):
            validate_landmarks({'source_forward':'-X','front_view':'+X'},[[-.2,-.25,-.5],[.2,.25,.5]])
    def test_arcade_zero_length_and_missing_roof_material_rejected(self):
        scene=self.spec['scene'];scene['composition']={'arcades':[{'start':[0,0],'end':[0,0]}]}
        machine={'texture_library':{m.get('texture_set'):{} for m in scene['materials'].values()}}
        with self.assertRaisesRegex(ContractError,'length'):validate_scene_resources(scene,machine)
        scene['composition']['arcades'][0].update(end=[9,0],bays=3,roof_material='missing')
        with self.assertRaisesRegex(ContractError,'roof_material'):validate_scene_resources(scene,machine)
    def test_nested_surface_resources_fail_before_blender(self):
        scene=self.spec['scene'];scene['materials']={'floor':{'surface':'layered_ground','layers':[{'texture_set':k} for k in ['soil','stone','missing']]}}
        with self.assertRaisesRegex(ContractError,'missing'):validate_scene_resources(scene,{'texture_library':{'soil':{},'stone':{}}})
    def test_height_resource_requires_real_height_channel(self):
        scene=self.spec['scene'];scene['materials']={};scene['composition']={'terrain_shape':{'height_texture_set':'stone'}}
        with self.assertRaisesRegex(ContractError,'height channel'):validate_scene_resources(scene,{'texture_library':{'stone':{'base':'stone.png'}}})
    def test_16_bit_roughness_keeps_range_and_height_keeps_precision(self):
        from PIL import Image
        import struct
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'data.png'
            Image.frombytes('I;16',(3,1),struct.pack('<HHH',0,32768,65535)).save(source)
            result,files=normalize_texture_library({'stone':{'roughness':str(source),'height':str(source)}},root/'normalized')
            self.assertEqual(list(Image.open(result['stone']['roughness']).getdata()),[0,128,255])
            self.assertEqual(result['stone']['height'],str(source));self.assertEqual(len(files),1)
    def test_incomplete_gameplay_fails_before_tools(self):
        del self.spec['gameplay']['boss_health']
        with self.assertRaises(ContractError):validate_spec(self.spec)
    def test_unsupported_morphology_needs_explicit_providers(self):
        self.spec['characters']['boss']['morphology']='quadruped'
        with self.assertRaises(ContractError):validate_spec(self.spec)
    def test_partial_multiview_is_rejected(self):
        self.spec['characters']['player']['source']={'provider':'tripo','mode':'multiview','front':'front.png'}
        with self.assertRaises(ContractError):validate_spec(self.spec)
    def test_mesh_swap_does_not_change_scene_or_boss_config(self):
        machine={'texture_library':{}}
        before={n.name:n.config for n in graph(self.spec,machine)}
        self.spec['characters']['player']['source']['path']='new/player.glb'
        after={n.name:n.config for n in graph(self.spec,machine)}
        self.assertNotEqual(before['mesh_player'],after['mesh_player'])
        for stage in ['mesh_boss','rig_boss','concept','scene','scene_layout']:self.assertEqual(before[stage],after[stage])
    def test_multiview_paths_resolve_relative_to_spec(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'game_spec.json'
            self.spec['characters']['player']['source']={'provider':'tripo','mode':'multiview',**{v:v+'.png' for v in ['front','left','back','right']}}
            path.write_text(json.dumps(self.spec));result=load_spec(path)
            self.assertEqual(result['characters']['player']['source']['left'],str((Path(folder)/'left.png').resolve()))
    def test_weighted_mesh_alone_is_not_a_valid_generated_rig(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'test.fbx';file.write_bytes(b'evidence')
            report={'ok':True,'skeleton_provider':'blender_baseline_humanoid','bone_map':dict.fromkeys(SEMANTIC_BONES,'bone'),'unweighted_vertices':0,'triangles':100,'fbx':str(file)}
            with self.assertRaisesRegex(ContractError,'completeness'):validate_rig(report)
            report.update(asset_review={'complete_body':True,'evidence':['front.png']},orientation={'source_forward':'+X'},deformation={'passed':False,'pose_tests':[{}]*5})
            with self.assertRaisesRegex(ContractError,'deformation'):validate_rig(report)
            report['deformation']['passed']=True;validate_rig(report)
    def test_continuous_terrain_cannot_end_at_play_boundary(self):
        self.spec['scene']['composition']={'terrain_extent_m':self.spec['scene']['size_m'],'court_radii':[7,8],'grass_material':self.spec['scene']['floor_material']}
        with self.assertRaisesRegex(ContractError,'extend beyond'):validate_spec(self.spec)
    def test_playable_whitebox_cannot_pass_release_art_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,data in [('test',{'passed':True}),('scene',{'quality':{}}),('rig',{'skeleton_provider':'existing_skin'})]:
                (root/(name+'.json')).write_text(json.dumps(data))
            ctx=SimpleNamespace(directory=root,inputs={'playtest':{'validation':str(root/'test.json')},'scene':{'report':str(root/'scene.json')},'rig_player':{'report':str(root/'rig.json')},'rig_boss':{'report':str(root/'rig.json')}})
            result=review(ctx,{'visual_agent':False})
            self.assertFalse(result['approved'])
    def test_scene_agent_raised_floor_updates_spawns_and_rejects_buried_spawns(self):
        scene=self.spec['scene']
        scene['composition']={'terrain_extent_m':100,'court_radii':[8,8],'grass_material':scene['floor_material'],
            'terrace':{'radius':8,'height':1.35,'steps':8}}
        spawns={'player':[0,-3,1.43],'boss':[0,3,1.43]}
        result={'scene':scene,'lighting':self.spec['lighting'],'spawns':spawns}
        with tempfile.TemporaryDirectory() as folder:
            ctx=SimpleNamespace(directory=Path(folder),inputs={'concept':{'image':'concept.png'}},
                machine={'texture_library':{m.get('texture_set'):{} for m in scene['materials'].values()}})
            cfg={'scene':scene,'lighting':self.spec['lighting'],'spawns':self.spec['spawns'],'validation_spec':self.spec}
            with patch('game_pipeline.services.chat',return_value=result):
                output=scene_layout(ctx,cfg)
                self.assertEqual(json.loads(Path(output['scene_spec']).read_text())['spawns'],spawns)
                result['spawns']['player'][2]=0
                with self.assertRaisesRegex(StageError,'below the raised terrace'):scene_layout(ctx,cfg)

if __name__=='__main__':unittest.main()
