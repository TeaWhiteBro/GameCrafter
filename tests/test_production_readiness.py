import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from game_pipeline.core import StageError,implementation_inventory,ROOT,read_json
from game_pipeline.production_readiness import usage_errors,require_ready,lessons
from game_pipeline.environment_assets import validate_demands
from game_pipeline.workflow import configure


class ProductionReadinessTests(unittest.TestCase):
    def test_rules_are_role_scoped_and_nonempty(self):
        for role in ['asset_spec','art_plan','scene_layout']:self.assertGreaterEqual(len(lessons(role)),3)
    def test_strip_rejection_uses_metadata_not_hardcoded_asset_names(self):
        machine={'asset_descriptors':{'any_new_source':{'usage_guidance':{'placement_contract':{'scatter_allowed':False},'preferred_alternative':'prepared_specimen'}}}}
        scene={'composition':{'exploration':{'planting_regions':[{'palette':[{'asset':'any_new_source'}]}]}}}
        self.assertEqual(usage_errors(scene,machine)[0]['code'],'unsuitable_scatter_representation')
        machine['asset_descriptors']['any_new_source']['usage_guidance']['placement_contract']['scatter_allowed']=True
        self.assertEqual(usage_errors(scene,machine),[])
    def test_explicit_assembled_row_is_not_mistaken_for_scatter(self):
        machine={'asset_descriptors':{'row':{'usage_guidance':{'placement_contract':{'scatter_allowed':False}}}}}
        self.assertFalse(usage_errors({'objects':[{'asset':'row'}]},machine))
    def test_retired_route_defaults_and_disabled_scatter_do_not_trigger_false_repair(self):
        machine={'asset_descriptors':{'row':{'usage_guidance':{'placement_contract':{'scatter_allowed':False}}}}}
        scene={'composition':{'scatter':{'plant_asset':'row','plant_count':0},
                              'exploration':{'composition_version':2,'plant_asset':'row','planting_regions':[]}}}
        self.assertFalse(usage_errors(scene,machine))
        scene['composition']['exploration']['planting_regions']=[{'palette':[{'asset':'row'}]}]
        self.assertEqual(len(usage_errors(scene,machine)),1)
    def test_generated_building_cannot_be_declared_traversable_or_plant(self):
        plan={'visual_identity':{'architecture':'from brief'},'blender_construction':[{'system':'terrain'}],
              'generated_assets':[{'id':'new_building','category':'architecture','use':'plant','height_m':4,
                'prompt':'One complete free-standing exterior building with a connected roof and base.','purpose':'landmark','acceptance':['intact']}]}
        with self.assertRaises(StageError):validate_demands(plan,{})
        plan['generated_assets'][0]['use']='solid_landmark';validate_demands(plan,{})
        plan['generated_assets'][0]['traversable']=True
        with self.assertRaises(StageError):validate_demands(plan,{})
    def test_missing_generated_asset_and_file_fail_together_before_blender(self):
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/'readiness.json'
            scene={'materials':{},'objects':[{'asset':'present'}]}
            machine={'mesh_library':{'present':{'file':str(Path(t)/'missing.glb'),'material':{'semantic_class':'prop'}}}}
            with patch('game_pipeline.contracts.validate_scene_resources'):
                with self.assertRaises(StageError):require_ready({'scene':scene},machine,output,['unplaced'])
            codes={item['code'] for item in read_json(output)['errors']}
            self.assertIn('generated_asset_unused',codes);self.assertIn('missing_source_file',codes)
    def test_fresh_world_keeps_all_gates_without_private_finish_images(self):
        spec=configure({})
        self.assertEqual(set(spec['dataset']['cameras']),{'first','third','isometric'})
        self.assertEqual(len(spec['dataset']['channels']),5)
        self.assertEqual(spec['dataset']['activities'],['combat','exploration'])
        self.assertEqual(spec['quality_benchmarks'],[])
        self.assertTrue(all(Path(p).is_file() for p in spec['quality_benchmarks']))
    def test_default_scene_adapter_rejects_bad_source_before_launching_blender(self):
        from game_pipeline.local_adapters import scene
        from game_pipeline.core import write_json
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'scene.json';write_json(source,{'scene':{'materials':{},'objects':[{'asset':'missing'}]}})
            ctx=SimpleNamespace(machine={'mesh_library':{}},inputs={'scene_layout':{'scene_spec':str(source)}},directory=root,run=Mock())
            with self.assertRaises(StageError):scene(ctx,{})
            ctx.run.assert_not_called()
            self.assertFalse(read_json(root/'production_readiness.json')['passed'])
    def test_source_demand_agent_receives_persistent_lessons_on_a_new_case(self):
        from game_pipeline.environment_assets import demand_plan
        with tempfile.TemporaryDirectory() as t:
            ctx=SimpleNamespace(machine={},inputs={'concept':{'image':'concept.png'}},directory=Path(t))
            plan={'visual_identity':{'architecture':'fresh brief'},'blender_construction':[{'system':'terrain'}],'generated_assets':[]}
            with patch('game_pipeline.environment_assets.chat',return_value=plan) as chat:
                demand_plan(ctx,{'brief':'A new urban world'})
            import json
            supplied=json.loads(chat.call_args.args[2])
            self.assertEqual(supplied['production_rules'],lessons('asset_spec'))
    def test_code_inventory_prunes_runs_and_preserves_all_source_types(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for name in ['a.py','src/b.cpp','src/c.h','src/d.cs','runs/million_files/x.py',
                         'src/__pycache__/bad.py','.venv/Lib/vendor.py','builds/GameDemo/runtime.cpp',
                         '.git/hooks/tool.py','inputs/untrusted.py','reports/diagnostic.py']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
            result=implementation_inventory(root)
            self.assertEqual(set(result),{str(Path(p)) for p in ['a.py','src/b.cpp','src/c.h','src/d.cs']})
