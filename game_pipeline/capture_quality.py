"""Screen sustained first-person foreground against the actual near plane."""
import json
from pathlib import Path
import numpy as np
from .core import StageError, write_json

def near_field_fraction(meta,depth,ids):
    projection=np.asarray(meta.get('projection',[]),dtype=float)
    if (meta.get('orthographic') or meta.get('camera_mode')!='first'
        or projection.shape!=(16,) or not np.isfinite(projection).all()
        or abs(projection[11]-1)>1e-5 or projection[14]<=0):
        raise StageError('Near-field check requires the actual first-person perspective projection')
    if depth.shape!=ids.shape or depth.size==0:raise StageError('Near-field raster dimensions disagree')
    near_m=float(projection[14])*.01
    return float(np.mean((ids==11)&np.isfinite(depth)&(depth>0)&(depth<=near_m+.02)))

def near_field_report(fractions):
    values=np.asarray(fractions,dtype=float)
    if values.ndim!=1 or not values.size or not np.isfinite(values).all() or np.any((values<0)|(values>1)):
        raise StageError('Missing finite first-person near-field evidence')
    close=values>.02
    return {'passed':bool(np.count_nonzero(close)<=len(values)*.05),'frames':len(values),
            'near_field_frames':int(np.count_nonzero(close)),
            'maximum_frame_fraction':float(np.max(values)),
            'maximum_near_field_frame_fraction':.05,'foreground_pixel_fraction_threshold':.02,
            'near_plane_band_m':.02,'opening_six_fractions':values[:6].tolist(),
            'scope':'Screen sustained Boss surfaces within 2 cm of the actual near plane; brief close strikes are allowed. This does not prove all mesh intersections absent or replace visual review.'}

def require_near_field(fractions):
    report=near_field_report(fractions)
    if not report['passed']:raise StageError('Sustained first-person near-plane foreground: '+json.dumps(report))
    return report

def check_sequence(folder,job):
    if job['calibration'] or job['activity']!='combat' or job['camera']!='first':return None
    from .dataset import load_frame
    folder=Path(folder);fractions=[]
    for index in range(job['frames']):
        meta,_,depth,ids=load_frame(folder/'raw'/f'{index:06d}.json')
        fractions.append(near_field_fraction(meta,depth,ids))
    report=near_field_report(fractions);write_json(folder/'near_field_validation.json',report)
    return require_near_field(fractions)
