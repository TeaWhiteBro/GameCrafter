import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game_pipeline.core import Engine, StageError, digest, now, read_json, write_json
from game_pipeline.replacement import prepare_replacement,baseline_context
from game_pipeline.local_adapters import review


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.base=self.root/'base';self.base.mkdir()
        self.spec=read_json(ROOT/'examples/local_assets.spec.json')
        self.spec['characters']['boss'].update(landmarks={'old':'measurement'},bone_map={'old':'bone'},source_forward='+X',skinning={'old':True},asset_review={'complete_body':True})
        write_json(self.base/'game_spec.json',self.spec)
        write_json(self.base/'review.json',{'approved':True});write_json(self.base/'validation.json',{'passed':True})
        write_json(self.base/'release.json',{'review':str(self.base/'review.json'),'validation':str(self.base/'validation.json')})
        self.asset=self.root/'boss.png';Image.new('RGB',(64,64)).save(self.asset)
        e=Engine(self.base,{},{});self.oldfile=self.base/'artifact.txt';self.oldfile.write_text('accepted')
        result=json.dumps({'report':str(self.oldfile),'_artifacts':{str(self.oldfile):digest(self.oldfile)}})
        for name in ['concept','mesh_player','rig_player','mesh_boss','rig_boss','scene_layout','scene','ue_project','animations','ue_assemble','playtest','review','delivery']:
            e.db.execute('insert into nodes values(?,?,?,?,?)',(name,'fingerprint','complete',result,now()))
        e.db.commit();e.db.close()

    def test_new_skin_gets_no_old_measurements_and_only_unaffected_receipts(self):
        target=self.root/'variant';spec=prepare_replacement(self.base,target,{},'boss',self.asset,image=True)
        boss=spec['characters']['boss']
        for key in ['landmarks','bone_map','source_forward','skinning','asset_review']:self.assertNotIn(key,boss)
        self.assertEqual(spec['scene'],self.spec['scene'])
        self.assertEqual(Path(boss['source']['image']).read_bytes(),self.asset.read_bytes())
        receipt=read_json(target/'replacement.json')
        self.assertEqual(set(receipt['reused_stages']),{'concept','mesh_player','rig_player','scene_layout','scene','ue_project'})
        self.assertIn('rig_boss',receipt['rebuild_stages']);self.assertIn('delivery',receipt['rebuild_stages'])
        self.assertFalse((target/'release.json').exists())
        self.assertEqual(read_json(self.base/'game_spec.json'),self.spec)

    def test_replacement_cannot_overwrite_or_nest_in_base(self):
        for path in [self.base,self.base/'child',self.root]:
            with self.assertRaises(StageError):prepare_replacement(self.base,path,{},'boss',self.asset,image=True)

    def test_upgrade_replacement_inherits_geometry_without_recalling_old_mesh_provider(self):
        from game_pipeline.cli import graph
        write_json(self.base/'upgrade.json',{'parent':'accepted-parent'})
        spec=prepare_replacement(self.base,self.root/'upgraded_variant',{},'boss',self.asset,image=True)
        nodes={n.name:n for n in graph(spec,{})}
        self.assertEqual(nodes['scene'].adapter,'artifact.inherit')
        self.assertEqual(nodes['rig_player'].adapter,'artifact.inherit')
        self.assertEqual(nodes['scene'].deps,[])
        self.assertNotIn('mesh_player',nodes)
        self.assertIn('mesh_boss',nodes)

    def test_changed_inherited_artifact_stops_before_new_run(self):
        self.oldfile.write_text('corrupt');target=self.root/'variant'
        with self.assertRaisesRegex(StageError,'Base artifact changed'):prepare_replacement(self.base,target,{},'boss',self.asset,image=True)
        self.assertFalse(target.exists())

    def test_environment_changes_cannot_claim_the_accepted_baseline(self):
        target=self.root/'variant';prepare_replacement(self.base,target,{},'boss',self.asset,image=True)
        ctx=SimpleNamespace(root=target,inputs={'scene':{'report':str(self.oldfile)}})
        cfg={'replacement_baseline':str(target/'replacement.json')}
        self.assertTrue(baseline_context(ctx,cfg)['preserved_environment_verified'])
        spec=read_json(target/'game_spec.json');spec['lighting']['sun_intensity']+=1;write_json(target/'game_spec.json',spec)
        with self.assertRaisesRegex(StageError,'Environment changed'):baseline_context(ctx,cfg)

    def review_context(self):
        write_json(self.root/'test.json',{'passed':True,'preview':'current.png'})
        write_json(self.root/'scene.json',{'quality':{'continuous_terrain':True,'layered_ground':True}})
        write_json(self.root/'rig.json',{'skeleton_provider':'existing_skin','deformation':{'passed':True,'pose_tests':[{'pose':p,'image':str(self.asset)} for p in ['rest','reach','stride','crouch','strike']]}})
        return SimpleNamespace(directory=self.root,inputs={'playtest':{'validation':str(self.root/'test.json')},'scene':{'report':str(self.root/'scene.json')},'concept':{'image':str(self.asset)},'rig_player':{'report':str(self.root/'rig.json')},'rig_boss':{'report':str(self.root/'rig.json')}})

    def test_reference_identity_cannot_be_waived_by_gameplay(self):
        ctx=self.review_context()
        for identity in [False,None,True]:
            answer={'anatomy_approved':True,'environment_approved':True,'acceptable_for_prototype':True,'reference_identity_approved':identity}
            with patch('game_pipeline.services.chat',return_value=answer):
                output=review(ctx,{'character_references':{'boss':[str(self.asset)]}})
            self.assertEqual(output['approved'],identity is True)

    def test_review_does_not_waive_existing_skin_deformation(self):
        ctx=self.review_context();write_json(self.root/'rig.json',{'skeleton_provider':'existing_skin'})
        answer={'anatomy_approved':True,'environment_approved':True,'acceptable_for_prototype':True,'reference_identity_approved':True}
        with patch('game_pipeline.services.chat',return_value=answer):output=review(ctx,{'character_references':{'boss':[str(self.asset)]}})
        self.assertFalse(output['approved'])


if __name__=='__main__':unittest.main()
