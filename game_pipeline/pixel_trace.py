"""Trace a metric capture pixel back into the scene for evidence-based repair."""
import numpy as np


def unproject(meta,pixel,depth_m):
    x,y=map(float,pixel);w,h=meta['width'],meta['height'];z=float(depth_m)
    if not (np.isfinite([x,y,z]).all() and 0<=x<w and 0<=y<h and z>0):
        raise ValueError('A valid in-frame pixel and positive metric camera depth are required')
    m=np.asarray(meta['world_to_clip'],float).reshape(4,4)
    cv=np.asarray(meta['world_to_camera_cv_m'],float).reshape(4,4)
    nx=(x+.5)/w*2-1;ny=1-(y+.5)/h*2
    # UE clip matrices multiply row vectors in centimetres. The exported CV
    # transform multiplies column vectors in metres. The third equation fixes
    # camera Z, so this also works for orthographic views without a fake pinhole.
    a=np.array([100*(m[:3,0]-nx*m[:3,3]),100*(m[:3,1]-ny*m[:3,3]),cv[2,:3]])
    b=np.array([nx*m[3,3]-m[3,0],ny*m[3,3]-m[3,1],z-cv[2,3]])
    return np.linalg.solve(a,b).tolist()


def candidates(world_m,class_id,audit,tolerance_m=.05):
    p=np.asarray(world_m,float);rows=[]
    for item in audit.get('components',[]):
        # Old rock-only audits did not store semantic_id. Do not infer identity
        # from those records; retain only explicitly compatible categories.
        if item.get('semantic_id')!=class_id:continue
        lo=np.asarray(item['bounds_m']['min']);hi=np.asarray(item['bounds_m']['max'])
        distance=float(np.linalg.norm(np.maximum(np.maximum(lo-p,p-hi),0)))
        if distance<=tolerance_m:
            rows.append({k:item[k] for k in ['environment','component','material','semantic_id'] if k in item} | {'aabb_distance_m':distance})
    return sorted(rows,key=lambda r:r['aabb_distance_m'])
