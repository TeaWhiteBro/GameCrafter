import tempfile,unittest
from pathlib import Path
from game_pipeline.review_cycle import previous_decision,record_decision,worklist
from game_pipeline.core import StageError,PendingExternal


class ReviewCycleTests(unittest.TestCase):
    def issue(self,**changes):
        return dict({'id':'ground_transition','severity':'blocker','category':'geometry','current_images':[1],
                     'problem':'Visible gap','repair':'Extend actual support','verification':'Inspect ground and elevated views'},**changes)
    def test_reference_or_diagnostic_only_citation_cannot_force_rebuild(self):
        labels=['CURRENT runtime','REFERENCE accepted','CURRENT supplementary geometry']
        for i in [2,3,0,True]:
            with self.assertRaises(StageError):worklist({'approved':False,'issues':[self.issue(current_images=[i])]},labels,0)
    def test_approval_cannot_hide_blocker_or_diagnostic(self):
        for severity in ['blocker','diagnostic']:
            with self.assertRaises(StageError):worklist({'approved':True,'issues':[self.issue(severity=severity)]},['CURRENT runtime'],0)
    def test_optional_polish_cannot_be_only_reason_for_refusal(self):
        with self.assertRaises(StageError):worklist({'approved':False,'issues':[self.issue(severity='polish')]},['CURRENT runtime'],0)
    def test_third_failed_review_requires_diagnosis_without_waiving_defect(self):
        result=worklist({'approved':False,'issues':[self.issue()]},['CURRENT runtime'],2)
        self.assertEqual(result['next_action'],'diagnose_root_cause_before_another_full_rebuild')
        self.assertEqual(len(result['blocking']),1)
    def test_same_evidence_keeps_refusal_and_does_not_call_model(self):
        with tempfile.TemporaryDirectory() as t:
            first=Path(t)/'first';first.mkdir();second=Path(t)/'second';second.mkdir()
            record_decision(first,'same',{'approved':False,'issues':[self.issue()]})
            value,path=previous_decision(second,'same')
            self.assertFalse(value['approved']);self.assertTrue(path)
            self.assertEqual(previous_decision(second,'new geometry evidence'),(None,None))
    def test_uncertain_request_is_not_blindly_repeated(self):
        with tempfile.TemporaryDirectory() as t:
            first=Path(t)/'first';first.mkdir();second=Path(t)/'second';second.mkdir()
            record_decision(first,'same')
            with self.assertRaises(PendingExternal):previous_decision(second,'same')

