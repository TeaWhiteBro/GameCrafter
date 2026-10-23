import unittest
import numpy as np
from game_pipeline.capture_quality import near_field_fraction,near_field_report,require_near_field
from game_pipeline.core import StageError

class CaptureQualityTests(unittest.TestCase):
    def test_sustained_close_foreground_is_rejected(self):
        # Actual failed episode had 38 of 360 frames above the screen-area threshold.
        with self.assertRaises(StageError):require_near_field([.03]*38+[0.]*322)
    def test_brief_strike_remains_allowed(self):
        self.assertTrue(require_near_field([.03]*4+[0.]*356)['passed'])
    def test_actual_projection_and_subject_label_define_band(self):
        projection=[0.]*16;projection[11]=1;projection[14]=10
        meta={'projection':projection,'orthographic':False,'camera_mode':'first'}
        depths=np.array([[.11,.5],[.11,.5]]);ids=np.array([[11,11],[3,11]])
        self.assertEqual(near_field_fraction(meta,depths,ids),.25)
        projection[14]=1
        self.assertEqual(near_field_fraction(meta,depths,ids),0)
    def test_missing_or_invalid_evidence_fails(self):
        for values in [[],[float('nan')],[-.1],[1.1]]:
            with self.subTest(values=values),self.assertRaises(StageError):near_field_report(values)
        with self.assertRaises(StageError):near_field_fraction({},np.ones((2,2)),np.ones((2,2)))
