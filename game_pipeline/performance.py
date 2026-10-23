"""Real-time acceptance; fixed-step sampling and unbounded probes are not FPS evidence."""
import math


def evaluate(hit_report, target_fps=60.):
    values = [hit_report.get('real_average_fps'), hit_report.get('frame_time_p99_ms')]
    valid = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) and v > 0 for v in values)
    minimum_fps = target_fps * .9
    maximum_p99 = 2000. / target_fps
    return {'passed': bool(valid and values[0] >= minimum_fps and values[1] <= maximum_p99),
            'target_fps': target_fps, 'minimum_average_fps': minimum_fps,
            'maximum_p99_ms': maximum_p99, 'measured_average_fps': values[0],
            'measured_p99_ms': values[1], 'source': 'real-time repeated-hit test'}
