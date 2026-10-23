"""Content presence for uniform terrain with small resolved character proxies.

Global variance alone confuses an open, level ground plane with an empty target.
The fallback must find raster contrast at multiple projected capsule locations;
it never substitutes for camera/time/pose checks or independent calibration.
"""
import numpy as np


def presence(meta, image):
    coverage=float((image.max(-1)>15).mean())
    std=float(image.std())
    result={'passed':False,'coverage':coverage,'global_std':std,
            'method':'none','resolved_capsules':0}
    if coverage<=.10:return result
    if std>2.:
        return {**result,'passed':True,'method':'global_contrast'}
    h,w=image.shape[:2]
    matrix=np.asarray(meta.get('world_to_clip',[]),dtype=float)
    if (meta.get('width')!=w or meta.get('height')!=h or matrix.size!=16
        or not np.isfinite(matrix).all()):return result
    matrix=matrix.reshape(4,4)
    visible_roles={a['role'] for a in meta.get('actors',[]) if not a.get('camera_hidden',False)}
    luminance=image.astype(float).mean(-1)
    accepted=[]
    for capsule in meta.get('whitebox',{}).get('capsules',[]):
        if capsule['role'] not in visible_roles:continue
        a=np.asarray(capsule['a_cm'],dtype=float);b=np.asarray(capsule['b_cm'],dtype=float)
        radius=float(capsule['radius_cm']);mid=(a+b)/2
        if not np.isfinite(np.r_[a,b,radius]).all() or radius<=0:continue
        points=np.vstack([a,b,mid,mid+np.eye(3)*radius])
        clip=np.c_[points,np.ones(len(points))]@matrix
        if np.any(clip[:,3]<=1e-8):continue
        pixels=(clip[:,:2]/clip[:,3:4]*[.5,-.5]+.5)*[w,h]-.5
        aa,bb,center=pixels[:3]
        rp=float(np.max(np.linalg.norm(pixels[3:]-center,axis=1)))
        if rp<.75 or rp>min(w,h)/4:continue
        lo=np.maximum(np.floor(np.minimum(aa,bb)-rp-4).astype(int),0)
        hi=np.minimum(np.ceil(np.maximum(aa,bb)+rp+4).astype(int),[w-1,h-1])
        if np.any(hi<lo):continue
        yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        xy=np.stack([xx,yy],-1);ab=bb-aa
        t=np.clip(np.sum((xy-aa)*ab,axis=-1)/max(1e-8,np.dot(ab,ab)),0,1)
        distance=np.linalg.norm(xy-(aa+t[...,None]*ab),axis=-1)
        inside=distance<=rp+1
        ring=(distance>=rp+2)&(distance<=rp+4)
        if inside.sum()<8 or ring.sum()<8:continue
        patch=luminance[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        values=patch[inside];background=float(np.median(patch[ring]))
        signal=int(np.count_nonzero(np.abs(values-background)>8))
        if signal<max(8,int(np.ceil(len(values)*.1))) or values.std()<=2:continue
        # Overlapping metadata probes must not count one tiny mark repeatedly.
        if any(np.linalg.norm(center-other)<max(3.,rp+other_radius) for other,other_radius in accepted):continue
        accepted.append((center,rp))
    return {**result,'passed':len(accepted)>=2,
            'method':'capsule_local_contrast','resolved_capsules':len(accepted)}
