"""Continuous terrain-fitted road/arrival bedding from a union of footprints.

One shared grid prevents construction joints and overlapping destination pads.
The outer shoulder sinks below terrain; individual stones remain the top layer.
"""
import math
import numpy as np


def build(api):
    field=api['route_field'];cfg=field.config
    enabled=cfg.get('continuous_bedding',True)
    if type(enabled) is not bool:raise ValueError('continuous_bedding must be boolean')
    if not enabled:return 0
    segments=[];bounds=[]
    for ri,(route,points) in enumerate(field.routes):
        if route.get('surface','stone')=='earth':continue
        widths=field.route_widths[ri]
        for i,(a,b) in enumerate(zip(points,points[1:])):
            segments.append((a[:2],b[:2],(widths[i]+widths[i+1])*.25))
        bounds.extend([points[:,:2].min(0)-max(widths),points[:,:2].max(0)+max(widths)])
    from landscape_routes import footprint
    places=[np.asarray(footprint(p),float) for p in cfg.get('places',[]) if p.get('surface','stone')!='none']
    for outline in places:bounds.extend([outline.min(0)-1,outline.max(0)+1])
    if not bounds:return 0
    lo=np.min(bounds,axis=0);hi=np.max(bounds,axis=0);step=cfg.get('bedding_grid_m',.30)
    if type(step) not in (float,int) or not math.isfinite(step) or not .15<=step<=1.:raise ValueError('bedding_grid_m must be between 0.15 and 1 metre')
    nx,ny=np.ceil((hi-lo)/step).astype(int)+1
    if nx*ny>2000000:raise ValueError('Bedding grid exceeds two million samples; split the scene or increase grid spacing')
    xy=np.array([(lo[0]+i*step,lo[1]+j*step) for j in range(ny) for i in range(nx)])
    signed=np.full(len(xy),-1e6)
    for a,b,r in segments:
        d=b-a;t=np.clip(((xy-a)*d).sum(1)/max(.0001,np.dot(d,d)),0,1)
        signed=np.maximum(signed,r+.18-np.linalg.norm(xy-a-t[:,None]*d,axis=1))
    for outline in places:
        # Convex authored courts, accepting either winding.
        area=sum(np.cross(outline[(i+1)%len(outline)]-p,outline[(i+2)%len(outline)]-outline[(i+1)%len(outline)]) for i,p in enumerate(outline))
        if area<0:outline=outline[::-1]
        interior=np.full(len(xy),1e6)
        for i,p in enumerate(outline):
            d=outline[(i+1)%len(outline)]-p
            interior=np.minimum(interior,(d[0]*(xy[:,1]-p[1])-d[1]*(xy[:,0]-p[0]))/max(.001,np.linalg.norm(d)))
        signed=np.maximum(signed,interior+.18)
    faces=[];used=set()
    for j in range(ny-1):
        for i in range(nx-1):
            ids=(j*nx+i,j*nx+i+1,(j+1)*nx+i+1,(j+1)*nx+i)
            if max(signed[list(ids)])>-.15:
                faces.extend([(ids[0],ids[1],ids[2]),(ids[0],ids[2],ids[3])]);used.update(ids)
    ids=sorted(used);remap={v:i for i,v in enumerate(ids)};verts=[];colors=[]
    raised=[r['id'] for r,p in field.routes if r.get('raised_surface',False)]
    for i in ids:
        x,y=xy[i];t=np.clip((signed[i]+.12)/.56,0,1);t=t*t*(3-2*t)
        z=api['height'](x,y)
        if raised:
            distance,route_z,width,_=field.query(x,y,raised)
            if distance<=width*.5+.18:z=max(z,route_z)
        verts.append((x,y,z-.09+.096*t))
        colors.append((.44+.22*t,.55-.32*t,0,1))
    api['mesh']('Continuous buried road bedding',verts,[tuple(remap[i] for i in f) for f in faces],cfg['paving_material'],colors=colors,preserve_winding=True)
    return len(faces)
