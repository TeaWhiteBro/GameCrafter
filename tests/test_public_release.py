import base64
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import URLError
from PIL import Image
from game_pipeline import __version__, workflow
from game_pipeline.core import ROOT, StageError, PendingExternal, read_json, write_json
from game_pipeline.cli import graph
from game_pipeline.fresh_sources import machine_for_spec, validate
from game_pipeline.image_gateway import generate, multipart, image_bytes
from game_pipeline.public_surfaces import acquire, validate_selection
from game_pipeline.machine import initialize, load, check
from game_pipeline.environment_assets import build_assets, with_resources
from game_pipeline import cli


def spec():
    value=read_json(ROOT/'examples/local_assets.spec.json')
    value['concept']={'provider':'gpt_image'}
    for role in ('player','boss'):
        value['characters'][role]['source']={'provider':'tripo','mode':'text','prompt':'A complete new character with separated limbs'}
    value['full_playtest']=True;value['review_agent']=True
    return workflow.configure(value)


def png():
    buffer=io.BytesIO();Image.new('RGB',(8,8),'red').save(buffer,format='PNG');return buffer.getvalue()


class PublicPolicy(unittest.TestCase):
    def test_new_run_omits_private_catalog_and_preserves_original_config(self):
        machine={'asset_catalog':'private.json','mesh_library':{'old':{}},'texture_library':{'old':{}},'art_kits':{'old':{}},'asset_descriptors':{'old':{}},'blender':'installed'}
        clean=machine_for_spec(machine,spec())
        self.assertNotIn('asset_catalog',clean)
        self.assertEqual(clean['mesh_library'],{});self.assertEqual(clean['texture_library'],{})
        self.assertIn('old',machine['mesh_library']);self.assertEqual(clean['blender'],'installed')
    def test_current_contract_is_accepted_without_mutation(self):
        s=spec();before=copy.deepcopy(s)
        self.assertIsNotNone(workflow.validate(s));self.assertEqual(s,before)
        s['production']['version']='unsupported'
        with self.assertRaises(ValueError):workflow.validate(s)
    def test_fresh_rejects_existing_mesh_resume_and_inheritance(self):
        for source in ({'provider':'local','path':'old.glb'}, {'provider':'tripo','mode':'resume','task_id':'old'}):
            s=spec();s['characters']['boss']['source']=source
            with self.assertRaises(StageError):validate(s)
        s=spec();s['adapters']={'scene':{'adapter':'artifact.inherit','config':{}}}
        with self.assertRaises(StageError):validate(s)
        s['production']['source_policy']='provided';validate(s)
    def test_reference_input_still_generates_new_mesh(self):
        s=spec();s['characters']['boss']['source']={'provider':'tripo','mode':'image','image':'new_reference.png'}
        validate(s)
    def test_public_surfaces_are_on_release_dependency_path(self):
        nodes={n.name:n for n in graph(spec(),{})}
        self.assertIn('surface_assets',nodes['environment_assets'].deps)
        self.assertIn('surface_assets',nodes['delivery'].deps)
        self.assertIn('environment_assets',nodes['art_plan'].deps)
        self.assertEqual(nodes['scene'].config['mesh_library'],{})
        self.assertTrue({'camera_validation','calibration','pair_validation','dataset','scene_preflight'}<=set(nodes['delivery'].deps))


class NativeImages(unittest.TestCase):
    def ctx(self, root):
        return SimpleNamespace(directory=root,machine={'gateway':{'base_url':'https://gateway.example','key_env':'TEST_IMAGE_KEY'}},spend=Mock())
    def test_success_and_resume_submit_only_once(self):
        with tempfile.TemporaryDirectory() as td, patch.dict('os.environ',{'TEST_IMAGE_KEY':'test-key'}):
            ctx=self.ctx(Path(td));response=io.BytesIO(json.dumps({'data':[{'b64_json':base64.b64encode(png()).decode()}]}).encode())
            opener=Mock();opener.open.return_value=response
            with patch('game_pipeline.image_gateway.request.build_opener',return_value=opener):
                out=generate(ctx,{'prompt':'Test'});self.assertTrue(out.is_file());generate(ctx,{'prompt':'Test'})
            self.assertEqual(opener.open.call_count,1);ctx.spend.assert_called_once_with('image_calls')
    def test_uncertain_post_is_not_retried(self):
        with tempfile.TemporaryDirectory() as td, patch.dict('os.environ',{'TEST_IMAGE_KEY':'test-key'}):
            ctx=self.ctx(Path(td));opener=Mock();opener.open.side_effect=URLError('connection lost')
            with patch('game_pipeline.image_gateway.request.build_opener',return_value=opener):
                for _ in range(2):
                    with self.assertRaises(PendingExternal):generate(ctx,{'prompt':'Test'})
            self.assertEqual(opener.open.call_count,1);ctx.spend.assert_called_once()
    def test_saved_response_recovers_without_a_second_post(self):
        with tempfile.TemporaryDirectory() as td, patch.dict('os.environ',{'TEST_IMAGE_KEY':'test-key'}):
            ctx=self.ctx(Path(td));write_json(ctx.directory/'request_state.json',{'status':'submitted_without_remote_id'})
            write_json(ctx.directory/'image_response.json',{'data':[{'b64_json':base64.b64encode(png()).decode()}]})
            with patch('game_pipeline.image_gateway.request.build_opener') as network:
                self.assertTrue(generate(ctx,{'prompt':'Test'}).is_file());network.assert_not_called()
            ctx.spend.assert_not_called()
    def test_multipart_uses_binary_files_and_image_array(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'reference.png';p.write_bytes(png());data,content=multipart({'model':'gpt-image-2','prompt':'Test'},[p])
            self.assertIn(b'name="image[]"',data);self.assertIn(png(),data);self.assertIn('boundary=',content)
    def test_artifact_download_does_not_forward_authorization(self):
        opener=Mock();opener.open.return_value=io.BytesIO(png())
        with patch('game_pipeline.image_gateway.request.build_opener',return_value=opener):
            image_bytes({'data':[{'url':'https://artifact.example/image.png'}]}, {}, 'private-key')
        self.assertNotIn('Authorization',opener.open.call_args.args[0].headers)


class PublicMaterials(unittest.TestCase):
    def test_selection_rejects_missing_and_unsafe_ids(self):
        for ids in ([],['../escape','red_sand'],['red_sand','red_sand'],['unavailable','red_sand'],[{'id':'red_sand'},'grey_plaster'],[['red_sand'],'grey_plaster']):
            with self.assertRaises(StageError):validate_selection({'surface_materials':ids})
    def test_verified_download_recovery_and_combined_resource_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);plan=root/'demands.json';write_json(plan,{'surface_materials':['red_sand','grey_plaster'],'generated_assets':[],
                'visual_identity':{'palette':'test'},'blender_construction':[{'system':'terrain'}]})
            blob=png();item={'url':'https://dl.polyhaven.org/test.png','md5':hashlib.md5(blob).hexdigest()}
            metadata={key:{'1k':{'png':item,'jpg':item}} for key in ('Diffuse','nor_dx','Rough')}
            folder=root/'surface';folder.mkdir()
            ctx=SimpleNamespace(directory=folder,inputs={'asset_demands':{'plan':str(plan)}})
            def fetch(url,*args):return json.dumps(metadata).encode() if 'api.polyhaven.com' in url else blob
            with patch('game_pipeline.public_surfaces.fetch',side_effect=fetch):result=acquire(ctx,{})
            with patch('game_pipeline.public_surfaces.fetch') as network:
                acquire(ctx,{});network.assert_not_called()
            source=root/'environment';source.mkdir()
            env=SimpleNamespace(machine={},directory=source,inputs={'asset_demands':{'plan':str(plan)},'surface_assets':result})
            combined=build_assets(env,{})
            machine=with_resources({}, {'scene':combined})
            self.assertEqual(set(machine['texture_library']),{'red_sand','grey_plaster'})
            target=Path(machine['texture_library']['red_sand']['base']);target.write_bytes(b'corrupt')
            with patch('game_pipeline.public_surfaces.fetch',side_effect=fetch) as network:
                acquire(ctx,{});self.assertEqual(network.call_count,1)
    def test_provider_checksum_failure_does_not_commit_a_map(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);plan=root/'plan.json';write_json(plan,{'surface_materials':['red_sand','grey_plaster']})
            metadata={'Diffuse':{'1k':{'jpg':{'url':'https://dl.polyhaven.org/test.jpg','md5':'a'*32}}}}
            ctx=SimpleNamespace(directory=root,inputs={'asset_demands':{'plan':str(plan)}})
            with patch('game_pipeline.public_surfaces.fetch',side_effect=[json.dumps(metadata).encode(),b'bad']):
                with self.assertRaisesRegex(StageError,'checksum'):acquire(ctx,{})
            self.assertFalse((root/'red_sand/base.jpg').exists())


class MachineSetup(unittest.TestCase):
    def test_planner_placeholder_is_not_ready_for_paid_generation(self):
        for name in ('', 'YOUR_VISION_CAPABLE_CHAT_MODEL', None):
            report=check({'gateway':{'base_url':'https://gateway.example','planner_model':name}})
            self.assertFalse(report['checks']['planner_model'])
        report=check({'gateway':{'base_url':'https://gateway.example','planner_model':'configured-vision-model'}})
        self.assertTrue(report['checks']['planner_model'])
    def test_initialize_uses_engine_templates_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'machine.local.json';initialize(p,Path(td)/'UE',Path(td)/'blender.exe')
            cfg=read_json(p);self.assertIn('TemplateResources',cfg['animation_library'])
            self.assertNotIn('asset_catalog',cfg);self.assertNotIn('imagegen_cli',cfg)
            with self.assertRaises(StageError):initialize(p,Path(td)/'UE',Path(td)/'blender.exe')
    def test_missing_motion_clips_fail_before_paid_work(self):
        report=check({'gateway':{'base_url':'https://gateway.example'}})
        self.assertFalse(report['passed']);self.assertEqual(len(report['missing_animation_assets']),15)
    def test_relative_paths_resolve_against_config_directory(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'machine.json';write_json(p,{'python':'.venv/Scripts/python.exe'})
            self.assertEqual(load(p)['python'],str((p.parent/'.venv/Scripts/python.exe').resolve()))
    def test_missing_reference_fails_before_machine_or_model_access(self):
        with tempfile.TemporaryDirectory() as td:
            argv=['pipeline.py','run','--run-dir',td,'--prompt','New world','--boss-image',str(Path(td)/'absent.png')]
            with patch('sys.argv',argv),patch('game_pipeline.machine.load') as load_machine,patch.object(cli,'Engine') as engine:
                with self.assertRaisesRegex(StageError,'Missing input image'):cli.main()
                load_machine.assert_not_called();engine.assert_not_called()
    def test_failed_toolchain_does_not_create_a_paid_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);machine=root/'machine.json';write_json(machine,{'gateway':{'base_url':'https://gateway.example'}})
            argv=['pipeline.py','--machine',str(machine),'run','--run-dir',str(root/'run'),'--prompt','New world']
            with patch('sys.argv',argv),patch.object(cli,'Engine') as engine:
                with self.assertRaisesRegex(StageError,'before any paid'):cli.main()
                engine.assert_not_called()
            self.assertFalse(read_json(root/'run/machine_preflight.json')['passed'])
    def test_paid_image_source_has_no_implementation_invalidation(self):
        from game_pipeline.implementation import implementation_digest
        self.assertEqual(implementation_digest('image.gpt_image'),'')
    def test_same_run_basename_cannot_share_a_project_between_repositories(self):
        from game_pipeline.local_adapters import clone_project
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);source=folder/'source';source.mkdir();(source/'GameDemo.uproject').write_text('{}')
            paths=[]
            for parent in ('checkout_a','checkout_b'):
                ctx=SimpleNamespace(root=folder/parent/'same_run',directory=folder/'same_revision',machine={'build_root':str(folder/'builds')})
                paths.append(clone_project(ctx,str(source/'GameDemo.uproject'),'assembled',True))
            self.assertNotEqual(*paths);self.assertTrue(all(Path(p).exists() for p in paths))
