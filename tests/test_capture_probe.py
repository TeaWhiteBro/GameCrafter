import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from game_pipeline import workflow,production_capture as capture
from game_pipeline.cli import graph
from game_pipeline.core import ROOT,StageError,read_json,write_json,digest
from game_pipeline.rendering import profile
from game_pipeline.local_adapters import deliver


class CaptureProbeTests(unittest.TestCase):
    def test_release_cannot_omit_probe_even_with_other_passed_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);review=root/'review.json';write_json(review,{'approved':True})
            inputs={name:{'passed':True} for name in ['playtest','scene_preflight','camera_validation','calibration','dataset','pair_validation']}
            inputs['review']={'review':str(review)}
            with self.assertRaisesRegex(StageError,'capture_probe'):
                deliver(SimpleNamespace(inputs=inputs),{'production':{'version':workflow.__version__}})

    def test_new_gate_precedes_gameplay_and_remains_on_release_path(self):
        base=read_json(ROOT/'examples/local_assets.spec.json')
        base.update(full_playtest=True,review_agent=True)
        spec=workflow.configure(base,source_policy='provided')
        nodes=graph(spec,{})
        by_name={n.name:n for n in nodes};names=list(by_name)
        self.assertLess(names.index('scene_preflight'),names.index('capture_probe'))
        self.assertLess(names.index('capture_probe'),names.index('playtest'))
        for stage in ['playtest','dataset','delivery']:self.assertIn('capture_probe',by_name[stage].deps)
        spec['production']['version']='unsupported'
        with self.assertRaises(ValueError):graph(spec,{})

    def test_probe_uses_exact_final_job_and_failure_blocks_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);report=root/'assemble.json'
            write_json(report,{'whitebox':{'available':True},'exploration':{'route_length_m':260}})
            cfg=workflow.configure({})['dataset']
            ctx=SimpleNamespace(directory=root,inputs={'ue_assemble':{'project':'game.uproject','report':str(report)}})
            job=next(j for j in capture.plan_jobs(read_json(report),cfg)['sequences'] if j['key']=='combat_first')
            with patch.object(capture,'capture_job',return_value=root/'sequence') as collect,patch.object(capture,'validate_sequence',side_effect=StageError('Near plane')):
                with self.assertRaisesRegex(StageError,'Near plane'):capture.capture_probe(ctx,cfg)
                self.assertEqual(collect.call_args.args[2],job)
            self.assertFalse((root/'probe.json').exists())

    def test_reuse_is_exact_read_only_and_invalidates_exporter_source_or_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);project=root/'game.uproject';project.write_text('{}')
            old=root/'old';old.mkdir();new=root/'new';new.mkdir()
            job=capture.plan_jobs({'whitebox':{'available':True}},workflow.configure({},'arena_demo')['dataset'])['sequences'][0]
            write_json(old/'source.json',{'project':str(project.resolve()),'rendering_profile':profile(),'files':{project.name:digest(project)}})
            write_json(old/'validation.json',{'passed':True})
            commit={'job':job,'exporter':capture.export_fingerprint(),'files':{p.name:digest(p) for p in old.iterdir()}}
            write_json(old/'commit.json',commit)
            probe=root/'probe.json';write_json(probe,{'passed':True,'directory':str(old),'job':job})
            plan=root/'plan.json';write_json(plan,{'cameras':['first'],'sequences':[job]})
            ctx=SimpleNamespace(directory=new,inputs={'ue_assemble':{'project':str(project)},'capture_probe':{'passed':True,'probe':str(probe)},'calibration':{'passed':True},'capture_plan':{'plan':str(plan)}})
            before={p.name:(digest(p),p.stat().st_mtime_ns) for p in old.iterdir()}
            with patch.object(capture,'validate_sequence',return_value={'passed':True}) as validate,patch.object(capture,'capture_job') as launch:
                result=capture.collect(ctx,False)
                launch.assert_not_called();validate.assert_called_once()
                self.assertTrue(read_json(result['collections'])['sequences'][job['key']]['reused_early_probe'])
                self.assertIn(old/'commit.json',result['_files'])
                self.assertEqual(before,{p.name:(digest(p),p.stat().st_mtime_ns) for p in old.iterdir()})
                changed=copy.deepcopy(job);changed['frames']+=1
                self.assertIsNone(capture.reusable_probe(ctx,str(project),changed))
                commit['exporter']='old-exporter';write_json(old/'commit.json',commit)
                self.assertIsNone(capture.reusable_probe(ctx,str(project),job))
                self.assertTrue(capture.committed(old,str(project),job)) # raw can be re-exported
                project.write_text('{"changed":true}')
                self.assertIsNone(capture.reusable_probe(ctx,str(project),job))
