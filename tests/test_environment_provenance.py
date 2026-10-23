import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from game_pipeline.core import Engine, Node, Context, StageError, write_json
from game_pipeline.environment_assets import build_assets


class EnvironmentProvenanceTests(unittest.TestCase):
    def test_buried_court_cannot_pass_even_when_geometry_exists(self):
        from adapters.blender.court_exposure import evaluate
        cfg={'court_center':[0,8],'court_radii':[8,8]}
        self.assertFalse(evaluate(cfg,lambda x,y:.14,lambda x,y:.135)['passed'])
        self.assertTrue(evaluate(cfg,lambda x,y:.14,lambda x,y:.24)['passed'])
        self.assertFalse(evaluate(cfg,lambda x,y:.14,lambda x,y:None)['passed'])
    def test_explicit_layout_cannot_bypass_intent_validation(self):
        from types import SimpleNamespace
        from game_pipeline.services import scene_layout
        ctx=SimpleNamespace(machine={},inputs={})
        cfg={'validation_spec':{},'agent_review':False,'production_requirements':{'exploration_required':True},'scene':{},'lighting':{},'spawns':{}}
        with patch('game_pipeline.contracts.validate_scene_resources'),patch('game_pipeline.services.validate_spec'),patch('game_pipeline.scene_intent.validate',side_effect=ValueError('blocked fixture')):
            with self.assertRaisesRegex(ValueError,'blocked fixture'):scene_layout(ctx,cfg)

    def test_authored_route_weights_do_not_force_every_ground_to_brown(self):
        from adapters.blender.landscape_routes import terrain_mask
        from types import SimpleNamespace
        field=SimpleNamespace(query=lambda x,y:(0,0,3,0),routes=[({'surface':'earth','terrain_weights':[1,0,.02]},[])])
        self.assertEqual(terrain_mask(field,0,0,.1,.8,.3),(1,0,.02))

    def test_solid_wall_crossing_route_is_rejected_before_blender(self):
        from game_pipeline.scene_intent import validate
        mats={n:{'semantic_class':n} for n in ['terrain','paving']}
        ex={'paving_material':'paving','routes':[{'id':'path','points':[[-3,0,0],[3,0,0]],'width':2.5}]}
        module={'kind':'capped_wall','center':[0,0],'size':[4,.5],'yaw_deg':90,'base_z':0,'height':2}
        data={'scene':{'materials':mats,'objects':[],'floor_material':'terrain','path_material':'paving','composition':{'exploration':ex,'modular_architecture':[module]}}}
        with self.assertRaisesRegex(ValueError,'Solid modular'):validate(data)
        module['center']=[0,5];validate(data)
        module.update(kind='beam_gate',center=[0,0]);validate(data)

    def test_generated_landmark_rejects_multiplier_disguised_as_metres(self):
        from game_pipeline.contracts import validate_scene_resources
        material={'color':[.3,.3,.3],'roughness':.7,'metallic':0}
        scene={'materials':{'floor':material},'objects':[{'kind':'asset','asset':'tall_tree','position':[0,0,0],'scale':[1,1,1],'material':'floor'}]}
        machine={'mesh_library':{'tall_tree':{}},'asset_descriptors':{'tall_tree':{'height_m':8,'provenance':'generated'}}}
        with self.assertRaisesRegex(ValueError,'metre bounding box'):validate_scene_resources(scene,machine)
        scene['objects'][0]['scale']=[9,9,8];validate_scene_resources(scene,machine)
        scene['objects'][0].update(scale=[1,1,1],miniature=True);validate_scene_resources(scene,machine)

    def test_structured_base_does_not_bury_a_building_like_a_rock(self):
        from adapters.blender.landscape_routes import base_origin,rock_origin
        points=[(x,y,z) for z in [0,.03,.4,1] for x,y in [(-.5,-.5),(-.5,.5),(.5,-.5),(.5,.5)]]
        base,_=base_origin(points,[0,0,0],[8,8,8],.3,lambda x,y:0)
        rock,_=rock_origin(points,[0,0,0],[8,8,8],.3,lambda x,y:0)
        self.assertGreater(base,-.4);self.assertLess(rock,-3)

    def test_recipe_never_submits_tripo_and_texture_change_reprepares(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);texture=root/'color.png';texture.write_bytes(b'first scan')
            machine={'blender':'fixture','texture_library':{'granite':{'base':str(texture)}}}
            engine=Engine(root,machine,{})
            plan={'visual_identity':{'palette':'granite'},'blender_construction':[{'system':'path'}],
                  'generated_assets':[{'id':'authored_lantern','category':'prop','height_m':1.8,'use':'prop',
                    'prompt':'One complete carefully carved lantern with a connected cap, open firebox and pedestal.',
                    'purpose':'route accent','acceptance':['complete support'],
                    'construction':{'recipe':'carved_lantern','texture_set':'granite'}}]}
            prepared=[]
            def fake_blender(ctx,args,**kwargs):
                prepared.append(str(ctx.directory));out=ctx.directory/'asset';out.mkdir(exist_ok=True)
                model=out/'model.glb';model.write_bytes(texture.read_bytes())
                write_json(out/'report.json',{'ok':True,'binding':{'file':str(model),'materials':{}},
                    'geometry':{},'views':[],'files':[str(model)]})
            try:
                with patch('game_pipeline.environment_assets.mesh') as mesh, patch.object(Context,'run',fake_blender), patch('game_pipeline.environment_assets.chat',return_value={'approved':True}):
                    for revision in range(2):
                        ctx=Context(root,machine,engine.db,Node('environment_assets','fixture',{}),{},str(revision))
                        result=build_assets(ctx,{'plan':plan})
                        texture.write_bytes(b'replacement scan')
                    mesh.assert_not_called()
                self.assertEqual(len(prepared),2)
                self.assertNotEqual(prepared[0],prepared[1])
            finally:engine.db.close()

    def test_mid_stage_implementation_change_cannot_commit_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);dependency=root/'adapter.py';dependency.write_text('VERSION=1')
            def mutate(ctx,cfg):
                output=ctx.directory/'output.txt';output.write_text('completed under old implementation')
                dependency.write_text('VERSION=2')
                return {'_files':[output]}
            engine=Engine(root,{}, {'fixture':mutate})
            try:
                with self.assertRaisesRegex(StageError,'changed while running'):
                    engine.execute([Node('fixture','fixture',{'_implementation_files':[str(dependency)]})])
                self.assertEqual(engine.db.execute('select status from nodes').fetchone()[0],'failed')
                self.assertTrue(list(root.glob('stages/fixture/*/output.txt')))
                self.assertFalse(list(root.glob('stages/fixture/*/receipt.json')))
            finally:engine.db.close()
