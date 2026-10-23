import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/unreal'))
from motion_metrics import stance_speed


class MotionMetricTests(unittest.TestCase):
    def test_shorter_stride_changes_rate_without_using_total_height(self):
        samples=[[[100-i*8,2,0],[105-i*8,-2,0]] for i in range(20)]
        full=stance_speed(samples,.05,(1,0))
        short=stance_speed([[[v*.6 for v in foot] for foot in frame] for frame in samples],.05,(1,0))
        self.assertAlmostEqual(full['stride_speed_cm_s'],160)
        self.assertAlmostEqual(short['stride_speed_cm_s'],96)

    def test_sideways_sway_is_not_forward_stride(self):
        samples=[[[i*20,-i*8,0],[i*20,-i*8,0]] for i in range(20)]
        self.assertAlmostEqual(stance_speed(samples,.05,(0,1))['stride_speed_cm_s'],160)

    def test_static_poses_cannot_calibrate_walk(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            stance_speed([[[0,0,0],[0,0,0]]]*20,.05,(1,0))
