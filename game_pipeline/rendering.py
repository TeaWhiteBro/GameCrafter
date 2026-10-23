"""Shared runtime rendering policy for play, QA, and paired capture."""

def profile():
    # Refresh shadows of coarse Nanite pages when finer geometry streams in.
    # Dense area-preserving foliage shares residency with buildings. The 1 GiB
    # pool was verified on an 8 GiB GPU; it is not a universal performance target.
    # UE's 10 cm default visibly slices melee hands close to a first-person eye.
    # Use a 1 cm perspective near plane in play and capture alike. Calibration
    # and the near-field screen still use each actual recorded projection.
    return {'version': 4, 'perspective_near_clip_cm': 1, 'orthographic_short_range_ao': 'disabled_per_view_gameplay_and_capture', 'console_variables': {
        'r.SetNearClipPlane': 1,
        'r.Nanite.VSMInvalidateOnLODDelta': 1,
        'r.Nanite.Streaming.StreamingPoolSize': 1024,
    }}


def launch_args():
    variables = profile()['console_variables']
    return ['-ExecCmds=' + ','.join(f'{key} {value}' for key, value in variables.items())]
