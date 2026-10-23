import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from game_pipeline import workflow, production_capture as capture
from game_pipeline.cli import graph
from game_pipeline.core import ROOT, StageError, read_json, write_json


class ConditionCoverageTests(unittest.TestCase):
    def test_new_policy_cannot_disable_exploration_visibility(self):
        spec=workflow.configure({})
        del spec['dataset']['visibility_policy']
        with self.assertRaisesRegex(ValueError,'subject visibility'):workflow.validate(spec)

    def test_all_requested_conditions_are_mandatory(self):
        base=read_json(ROOT/'examples/local_assets.spec.json')
        base.update(full_playtest=True,review_agent=True)
        spec=workflow.configure(base,source_policy='provided')
        self.assertEqual(next(n for n in graph(spec,{}) if n.name=='capture_probe').config['probe_scope'],'all_requested')
        del spec['dataset']['visibility_policy']
        with self.assertRaisesRegex(ValueError,'subject visibility'):graph(spec,{})

    def test_every_condition_is_checked_and_partial_failure_is_not_passed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);report=root/'assemble.json'
            write_json(report,{'whitebox':{'available':True},'exploration':{'route_length_m':260}})
            cfg={**workflow.configure({})['dataset'],'probe_scope':'all_requested'}
            ctx=SimpleNamespace(directory=root,inputs={'ue_assemble':{'project':'game.uproject','report':str(report)}})
            jobs=capture.plan_jobs(read_json(report),cfg)['sequences']
            def collect(ctx,project,job):return root/job['key']
            with patch.object(capture,'capture_job',side_effect=collect),patch.object(capture,'validate_sequence',return_value={'passed':True}) as check:
                result=capture.capture_probe(ctx,cfg)
                self.assertEqual(check.call_count,6)
                self.assertEqual([v['job'] for v in read_json(result['probe'])['sequences'].values()],jobs)
            (root/'probe.json').unlink()
            with patch.object(capture,'capture_job',side_effect=collect),patch.object(capture,'validate_sequence',side_effect=[{'passed':True}]*5+[StageError('Canopy occlusion')]):
                with self.assertRaisesRegex(StageError,'Canopy'):capture.capture_probe(ctx,cfg)
            self.assertFalse((root/'probe.json').exists())

    def test_multijob_receipt_reuses_only_matching_immutable_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=capture.plan_jobs({'whitebox':{'available':True}},workflow.configure({},'arena_demo')['dataset'])['sequences'][1]
            probe=root/'probe.json'
            write_json(probe,{'passed':True,'sequences':{job['key']:{'directory':str(root/'old'),'job':job}}})
            ctx=SimpleNamespace(inputs={'capture_probe':{'passed':True,'probe':str(probe)}})
            with patch.object(capture,'committed',return_value=True) as committed,patch.object(capture,'validate_sequence',return_value={'passed':True}):
                self.assertEqual(capture.reusable_probe(ctx,'game.uproject',job),root/'old')
                self.assertTrue(committed.call_args.kwargs['require_exporter'])
                changed=copy.deepcopy(job);changed['camera']='isometric'
                self.assertIsNone(capture.reusable_probe(ctx,'game.uproject',changed))

    def test_occlusion_sentinel_allows_brief_crossings_but_rejects_canopy(self):
        check=capture.validate_exploration_visibility
        check([600]*20+[0]*8+[600]*72,640*360)
        for counts in ([600]*20+[0]*13+[600]*327,[0]*82+[26]*278,[0]*6+[600]*354,[1]*360):
            with self.subTest(counts=counts[:8]),self.assertRaisesRegex(StageError,'occluded'):check(counts,640*360)

    def test_render_hidden_and_missing_identity_are_rejected(self):
        ids=np.full((10,10),10,dtype=np.uint8)
        player={'role':'player','class_id':10,'camera_hidden':False}
        self.assertEqual(capture.exploration_player_pixels([player],ids),100)
        for actors in ([],[dict(player,camera_hidden=True)],[dict(player,class_id=11)],[player,player]):
            with self.assertRaises(StageError):capture.exploration_player_pixels(actors,ids)

    def test_first_person_owner_and_calibration_are_exempt(self):
        job={'visibility_policy':'all_activities_v1','activity':'exploration','camera':'third','calibration':False}
        self.assertTrue(capture.exploration_visibility_required(job))
        for changes in ({'camera':'first'},{'calibration':True},{'activity':'combat'},{'visibility_policy':'legacy'}):
            self.assertFalse(capture.exploration_visibility_required({**job,**changes}))
