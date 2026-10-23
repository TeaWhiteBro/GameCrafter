import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from game_pipeline.core import ROOT,StageError,read_json,write_json,Engine,Node,Context
from game_pipeline.environment_assets import validate_demands,with_resources,build_assets,resource_result
from game_pipeline.cli import graph
from game_pipeline import workflow
from adapters.blender.modular_architecture import build,validate

def demand():
    return {'visual_identity':{'palette':'color areas'},'blender_construction':[{'system':'paths'}],
        'generated_assets':[{'id':'test_landmark','category':'architecture','height_m':4,'use':'solid_landmark',
            'prompt':'One complete isolated exterior landmark, intact roof and connected structural supports, textured.',
            'purpose':'destination silhouette','acceptance':['connected construction']}]}

class AssetDemandTests(unittest.TestCase):
    def test_budget_invalid_identity_and_unsafe_reference_rejected(self):
        for key,value in [('id','../escape'),('height_m',float('nan')),('category','unknown'),('use','walkthrough'),('image','missing.png')]:
            p=demand();p['generated_assets'][0][key]=value
            with self.subTest(key=key),self.assertRaises(StageError):validate_demands(p,{})
        with self.assertRaises(StageError):validate_demands(demand(),{},maximum=0)
    def test_existing_resource_cannot_be_replaced_by_generated_name(self):
        with self.assertRaises(StageError):validate_demands(demand(),{'mesh_library':{'test_landmark':{}}})
    def test_texture_change_survives_intermediate_planning_receipts(self):
        a=resource_result({'source':{'resources':'same.json','_artifacts':{'texture.png':'old'}}})
        b=resource_result({'source':{'resources':'same.json','_artifacts':{'texture.png':'new'}}})
        self.assertNotEqual(a['resource_fingerprint'],b['resource_fingerprint'])
        self.assertEqual(resource_result({'art':a,'layout':a}),a)
        with self.assertRaises(StageError):resource_result({'art':a,'layout':b})
    def test_resource_bundles_do_not_mutate_machine_or_overwrite_sources(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'resources.json';write_json(p,{'mesh_library':{'x':{'file':'a'}}})
            machine={};result=with_resources(machine,{'upstream':{'resources':str(p)}})
            self.assertEqual(machine,{});self.assertEqual(result['mesh_library']['x']['file'],'a')
            with self.assertRaises(StageError):with_resources({'mesh_library':{'x':{'file':'b'}}},{'upstream':{'resources':str(p)}})
    def test_full_graph_includes_new_sources_on_release_path(self):
        spec=read_json(ROOT/'examples/local_assets.spec.json');spec['full_playtest']=True;spec['review_agent']=True
        spec=workflow.configure(spec,source_policy='provided')
        nodes={n.name:n for n in graph(spec,{})}
        self.assertEqual(nodes['environment_assets'].deps,['asset_demands'])
        self.assertIn('environment_assets',nodes['art_plan'].deps)
        self.assertTrue({'environment_assets','asset_demands','pair_validation','camera_validation'}<=set(nodes['delivery'].deps))
    def test_provided_mode_can_explicitly_disable_environment_generation(self):
        spec=read_json(ROOT/'examples/local_assets.spec.json');spec['full_playtest']=True;spec['review_agent']=True
        spec=workflow.configure(spec,source_policy='provided');spec.pop('environment_assets')
        workflow.validate(spec);self.assertNotIn('asset_demands',{n.name for n in graph(spec,{})})
    def test_prepare_revision_reuses_paid_source_with_verified_receipt(self):
        calls=[]
        def fake_source(ctx,cfg):
            calls.append(cfg);p=ctx.directory/'source.glb';p.write_bytes(b'fixture source')
            return {'mesh':str(p),'task_id':'persisted-task','_files':[p]}
        def fake_blender(ctx,args,**kw):
            out=ctx.directory/'asset';out.mkdir(exist_ok=True);model=out/'prepared.glb';model.write_bytes(b'prepared fixture')
            write_json(out/'report.json',{'ok':True,'binding':{'file':str(model),'materials':{}},'views':[],'geometry':{},'files':[str(model)]})
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);engine=Engine(root,{'blender':'fixture-blender','budgets':{'llm_calls':3}}, {'generated':build_assets})
            with patch('game_pipeline.environment_assets.mesh',fake_source),patch.object(Context,'run',fake_blender),patch('game_pipeline.environment_assets.chat',return_value={'approved':True}):
                with patch('game_pipeline.implementation.implementation_digest',return_value='v1'), patch('game_pipeline.implementation.environment_preparation_digest',return_value='prep-v1'):
                    engine.execute([Node('assets','generated',{'plan':demand()})])
                with patch('game_pipeline.implementation.implementation_digest',return_value='v2'), patch('game_pipeline.implementation.environment_preparation_digest',return_value='prep-v2'):
                    engine.execute([Node('assets','generated',{'plan':demand()})])
            self.assertEqual(sum(not c.get('submit_only') for c in calls),1)
            self.assertEqual(len(list(root.glob('stages/environment_test_landmark_prepared/*/asset/report.json'))),2)
            engine.db.close()

    def test_recipe_additional_map_change_invalidates_preparation(self):
        def fake_blender(ctx,args,**kw):
            out=ctx.directory/'asset';out.mkdir(exist_ok=True);model=out/'prepared.glb'
            model.write_bytes(b'prepared fixture')
            write_json(out/'report.json',{'ok':True,'binding':{'file':str(model),'materials':{}},
                'views':[],'geometry':{},'files':[str(model)]})
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=root/'stone.png';base.write_bytes(b'stable stone')
            moss=root/'moss.png';moss.write_bytes(b'first moss')
            plan=demand();plan['generated_assets'][0]['construction']={
                'recipe':'fixture','texture_set':'stone','additional_texture_sets':['moss']}
            machine={'blender':'fixture','budgets':{'llm_calls':3},
                'texture_library':{'stone':{'base':str(base)},'moss':{'base':str(moss)}}}
            engine=Engine(root/'run',machine,{'generated':build_assets})
            with patch('game_pipeline.environment_assets.mesh') as paid,patch.object(Context,'run',fake_blender),patch('game_pipeline.environment_assets.chat',return_value={'approved':True}):
                for revision in ['first','second']:
                    moss.write_bytes((revision+' moss').encode())
                    with patch('game_pipeline.implementation.implementation_digest',return_value=revision):
                        engine.execute([Node('assets','generated',{'plan':plan})])
                paid.assert_not_called()
            self.assertEqual(len(list((root/'run').glob('stages/environment_test_landmark_prepared/*/asset/report.json'))),2)
            self.assertEqual(len(list((root/'run').glob('stages/environment_test_landmark_source/*/source_receipt.json'))),1)
            engine.db.close()

class ModularConstructionTests(unittest.TestCase):
    def generate(self,kind,proxy=False):
        records=[]
        def emit(name,verts,faces,mat):
            records.append((name,verts,faces,mat));return SimpleNamespace(data=SimpleNamespace(polygons=[]))
        item={'kind':kind,'center':[12,7],'size':[8,7] if kind!='capped_wall' else [8,.5],
            'base_z':.14,'height':3.5,'yaw_deg':31,'material':'stone','timber_material':'red','roof_material':'blue'}
        build({'cfg':{'modular_architecture':[item]},'height':lambda x,y:.02*x,'mesh':emit},proxy)
        return records
    def test_open_pavilion_has_continuous_deck_and_thick_roof_in_both_products(self):
        full=self.generate('curved_pavilion');low=self.generate('curved_pavilion',True)
        for records in [full,low]:
            self.assertTrue(any('deck' in name for name,*_ in records))
            roof=next(r for r in records if 'thick curved hip roof' in r[0]);self.assertGreater(len(roof[2]),20)
            self.assertEqual(sum(n.endswith(' post') for n,*_ in records),4)
        self.assertLess(sum(len(r[2]) for r in low),sum(len(r[2]) for r in full)*.5)
    def test_rotated_footings_extend_below_sampled_ground(self):
        for _,vertices,_,_ in [r for r in self.generate('capped_wall') if 'grounded plinth' in r[0]]:
            for x,y,z in vertices[:4]:self.assertLessEqual(z,.02*x-.07)
    def test_nonfinite_and_unknown_construction_rejected(self):
        with self.assertRaises(ValueError):validate([{'kind':'unknown'}])
        with self.assertRaises(ValueError):validate([{'kind':'beam_gate','center':[0,0],'size':[7,float('inf')]}])
    def test_rounded_tile_courses_are_closed_nondegenerate_solids(self):
        import numpy as np
        records=[r for r in self.generate('curved_pavilion') if 'rounded ceramic' in r[0]]
        self.assertGreater(len(records),100)
        for name,vertices,faces,mat in records:
            v=np.array(vertices);self.assertTrue(np.isfinite(v).all());edges={}
            for f in faces:
                area=sum(np.linalg.norm(np.cross(v[f[i]]-v[f[0]],v[f[i+1]]-v[f[0]])) for i in range(1,len(f)-1))
                self.assertGreater(area,1e-9)
                for a,b in zip(f,f[1:]+f[:1]):key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1
            self.assertTrue(all(n==2 for n in edges.values()))
