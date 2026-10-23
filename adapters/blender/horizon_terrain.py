"""Continuous coarse terrain apron outside the dense playable square."""
import math

def geometry(extent, step, height, settings):
    distances=settings['ring_offsets_m']
    if not distances or distances[0]!=0 or any(b<=a for a,b in zip(distances,distances[1:])):
        raise ValueError('Horizon rings must start at zero and strictly increase')
    if not 100<=distances[-1]<=3000:raise ValueError('Horizon apron must extend 100-3000 metres')
    n=int(extent/step);half=extent/2
    perimeter=[]
    for i in range(n):perimeter.append((-half+extent*i/n,-half))
    for i in range(n):perimeter.append((half,-half+extent*i/n))
    for i in range(n):perimeter.append((half-extent*i/n,half))
    for i in range(n):perimeter.append((-half,half-extent*i/n))
    vertices=[]
    for distance in distances:
        scale=(half+distance)/half
        for px,py in perimeter:
            x,y=px*scale,py*scale
            t=min(1.,distance/100);t=t*t*(3-2*t)
            far=settings.get('height_m',22)*(1+.42*math.sin(x*.015+y*.004)+.31*math.sin(y*.011-x*.006))
            far+=18*(distance/distances[-1])**2
            z=height(x,y)*(1-t)+far*t
            vertices.append((x,y,z))
    count=len(perimeter);faces=[]
    for ring in range(len(distances)-1):
        for i in range(count):
            j=(i+1)%count;a=ring*count;b=(ring+1)*count
            faces.append((a+i,b+i,b+j,a+j))
    return vertices,faces

def build(api):
    cfg=api['cfg'];settings=cfg.get('horizon_terrain')
    if not settings:return
    vs,fs=geometry(cfg['terrain_extent_m'],cfg['terrain_grid_m'],api['height'],settings)
    api['mesh']('Distant terrain',vs,fs,api['spec']['floor_material'],collision=False,colors=[(0,0,0,1)]*len(vs))
