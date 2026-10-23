import unittest
from game_pipeline.performance import evaluate


class RealtimePerformanceTests(unittest.TestCase):
    def test_fixed_step_or_missing_metrics_cannot_pass(self):
        for data in [{}, {'simulation_fps': 60, 'fps': 60},
                     {'real_average_fps': float('nan'), 'frame_time_p99_ms': 16},
                     {'real_average_fps': True, 'frame_time_p99_ms': 16}]:
            self.assertFalse(evaluate(data)['passed'])

    def test_actual_dense_foliage_failure_is_rejected(self):
        self.assertFalse(evaluate({'real_average_fps': 33.4324, 'frame_time_p99_ms': 32.0546})['passed'])

    def test_high_average_cannot_hide_long_tail_stalls(self):
        self.assertFalse(evaluate({'real_average_fps': 60, 'frame_time_p99_ms': 80})['passed'])

    def test_measured_corrected_probe_meets_explicit_budget(self):
        self.assertTrue(evaluate({'real_average_fps': 59.3999, 'frame_time_p99_ms': 26.2176})['passed'])
