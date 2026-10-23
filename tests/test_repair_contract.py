import copy
import os
import tempfile
import unittest
from pathlib import Path
from game_pipeline.core import StageError, digest, read_json, write_json
from game_pipeline.review_cycle import record_decision
from game_pipeline.repair_contract import require_plan, refusal_streak


class RepairContractTests(unittest.TestCase):
    def history(self,root):
        for i in range(3):
            d=root/str(i);d.mkdir()
            record_decision(d,str(i),{'approved':False,'issues':[{'id':'ground','severity':'blocker'}]})
            os.utime(d/'review_state.json',ns=(1_000_000_000+i,1_000_000_000+i))
        current=root/'new';current.mkdir();return current

    def test_third_distinct_refusal_requires_diagnosis_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);current=self.history(root)
            before={str(p):digest(p) for p in root.glob('*/review_state.json')}
            with self.assertRaisesRegex(StageError,'Three distinct'):require_plan(current,{'revision':'new'})
            self.assertTrue((current/'repair_plan_required.json').is_file())
            self.assertEqual(before,{str(p):digest(p) for p in root.glob('*/review_state.json')})

    def test_stale_source_omitted_issue_or_tampered_evidence_cannot_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);current=self.history(root);source={'revision':'new'}
            with self.assertRaises(StageError):require_plan(current,source)
            plan=read_json(current/'repair_plan_required.json');evidence=root/'measured.json'
            write_json(evidence,{'gap_cm':0,'source_revision':'new'})
            item={'path':str(evidence),'sha256':digest(evidence)}
            plan['actions'][0].update(owner_stage='scene',root_cause='Support elevation mismatch',
                changes=[item],evidence=[item],expected_result='No unsupported route',observed_result='Ground probes pass')
            path=root/'plan.json';write_json(path,plan)
            result=require_plan(current,source,path)
            self.assertTrue(result['required'])
            self.assertEqual(set(result['evidence_files']),{str(path),str(evidence)})
            for field,value in [('target_source_sha256','old'),('against_review_sha256','old'),('actions',[])]:
                bad=copy.deepcopy(plan);bad[field]=value;write_json(path,bad)
                with self.subTest(field=field),self.assertRaises(StageError):require_plan(current,source,path)
            write_json(path,plan);evidence.write_text('modified')
            with self.assertRaisesRegex(StageError,'stale'):require_plan(current,source,path)

    def test_identical_refusal_is_not_counted_as_another_design_iteration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);current=self.history(root)
            for d in root.glob('[012]'):record_decision(d,'same',{'approved':False,'issues':[]})
            self.assertEqual(len(refusal_streak(current)),1)
            self.assertFalse(require_plan(current,{'revision':'new'})['required'])

    def test_diagnostic_action_does_not_require_blind_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);current=self.history(root)
            d=root/'diagnostic';d.mkdir()
            record_decision(d,'uncertain',{'approved':False,'issues':[{'id':'roof','severity':'diagnostic'}]})
            with self.assertRaises(StageError):require_plan(current,{'revision':'same'})
            plan=read_json(current/'repair_plan_required.json');evidence=root/'oblique.json'
            write_json(evidence,{'same_source':True,'roof_present':True})
            plan['actions'][0].update(owner_stage='scene_preflight',root_cause='Foreshortening',
                evidence=[{'path':str(evidence),'sha256':digest(evidence)}],
                expected_result='Resolve roof identity',observed_result='Roof visible in oblique view')
            path=root/'plan.json';write_json(path,plan)
            self.assertTrue(require_plan(current,{'revision':'same'},path)['required'])

    def test_acceptance_resets_refusal_streak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);current=self.history(root)
            record_decision(current,'accepted',{'approved':True,'issues':[]})
            self.assertEqual(refusal_streak(current),[])
