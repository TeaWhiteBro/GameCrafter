import unittest,tempfile,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_pipeline.core import Engine,Node,StageError
from game_pipeline.contracts import validate_scene_resources,validate_rig,SEMANTIC_BONES,ContractError
from game_pipeline.catalog import mount

class QualityExtensions(unittest.TestCase):
    def test_missing_declared_source_fails_before_provider(self):
        with tempfile.TemporaryDirectory() as td:
            called=[]
            e=Engine(Path(td)/'run',{}, {'test.provider':lambda c,s:called.append(True)})
            with self.assertRaises(StageError):e.execute([Node('source','test.provider',{'_source_files':[str(Path(td)/'missing.glb')]})])
            self.assertFalse(called)
            e.db.close()
    def test_pbr_rejects_missing_normal_channel(self):
        scene={'materials':{'roof':{'surface':'pbr','texture_set':'roof'}},'objects':[]}
        with self.assertRaises(ContractError):validate_scene_resources(scene,{'texture_library':{'roof':{'base':'a','roughness':'b'}}})
    def test_material_scale_guard(self):
        scene={'materials':{'wall':{'surface':'pbr','texture_set':'wall','scale_cm':10000}},'objects':[]}
        with self.assertRaises(ContractError):validate_scene_resources(scene,{'texture_library':{'wall':{'base':'a','roughness':'b','normal':'c'}}})
    def test_ground_scan_is_not_a_scatter_boulder(self):
        scene={'materials':{},'objects':[],'composition':{'scatter':{'rock_asset':'patch'}}}
        with self.assertRaisesRegex(ContractError,'ground patches'):validate_scene_resources(scene,{'mesh_library':{'patch':{'placement':'ground_patch'}}})
    def test_invalid_plant_palette_fails_before_blender(self):
        scene={'materials':{},'objects':[],'composition':{'plant_palette':[{'asset':'nonexistent'}]}}
        with self.assertRaises(ContractError):validate_scene_resources(scene,{})
    def test_no_catalog_keeps_custom_machine_unchanged(self):
        original={'texture_library':{'custom':{'base':'x'}}};result=mount(original)
        result['texture_library']['custom']['base']='y';self.assertEqual(original['texture_library']['custom']['base'],'x')
    def test_existing_rig_without_pose_evidence_is_rejected(self):
        report={'ok':True,'bone_map':dict.fromkeys(SEMANTIC_BONES,'bone'),'unweighted_vertices':0,'triangles':100,'skeleton_provider':'existing_skin'}
        with self.assertRaisesRegex(ContractError,'deformation suite'):validate_rig(report)
    def test_static_mesh_cannot_pass_existing_rig_pose_suite(self):
        report={'ok':True,'bone_map':dict.fromkeys(SEMANTIC_BONES,'bone'),'unweighted_vertices':0,'triangles':100,'skeleton_provider':'existing_skin',
                'deformation':{'passed':True,'pose_tests':[{'pose':p,'max_vertex_motion_fraction':0} for p in ['rest','reach','stride','crouch','strike']]}}
        with self.assertRaisesRegex(ContractError,'actually move'):validate_rig(report)

if __name__=='__main__':unittest.main()
