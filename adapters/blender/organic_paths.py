"""Authored tapered roots/lianas, with a shared structural centerline."""
import math
import numpy as np

def validate(items):
    if not isinstance(items,list) or len(items)>64:raise ValueError('organic_paths must contain at most 64 paths')
    for item in items:
        pts=item.get('points',[]);radii=item.get('radii',[])
        if not 3<=len(pts)<=24 or len(radii)!=len(pts):raise ValueError('Organic paths need 3-24 XYZ controls with matching radii')
        if any(len(p)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>250 for v in p) for p in pts):raise ValueError('Organic path coordinates must be finite bounded metres')
        if any(type(r) not in (int,float) or not math.isfinite(r) or not .015<=r<=2 for r in radii):raise ValueError('Organic path radii must be .015-2m')
        if any(math.dist(a,b)<.05 for a,b in zip(pts,pts[1:])):raise ValueError('Organic path controls must be distinct')
        if not item.get('material'):raise ValueError('Organic path material required')
    return items

def geometry(item,proxy=False):
    controls=np.asarray(item['points'],float);radii=np.asarray(item['radii'],float);centers=[];sizes=[]
    for i in range(len(controls)-1):
        a,b=controls[i:i+2];before=controls[max(0,i-1)];after=controls[min(len(controls)-1,i+2)]
        count=max(3,math.ceil(np.linalg.norm(b-a)/(.4 if proxy else .12)))
        for j in range(count):
            t=j/count;centers.append(.5*((2*a)+(-before+b)*t+(2*before-5*a+4*b-after)*t*t+(-before+3*a-3*b+after)*t*t*t));sizes.append(radii[i]*(1-t)+radii[i+1]*t)
    centers.append(controls[-1]);sizes.append(radii[-1]);centers=np.asarray(centers);n=8 if proxy else 20;vs=[]
    previous=None
    for i,(p,r) in enumerate(zip(centers,sizes)):
        axis=centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)];axis/=max(1e-9,np.linalg.norm(axis))
        reference=np.array([0.,0.,1.]) if abs(axis[2])<.92 else np.array([1.,0.,0.])
        side=np.cross(axis,reference);side/=np.linalg.norm(side)
        if previous is not None and np.dot(side,previous)<0:side=-side
        up=np.cross(axis,side);previous=side
        for j in range(n):
            angle=j*math.tau/n;ridging=1 if proxy else 1+.025*math.sin(3*angle+i*.21)
            vs.append(tuple(p+r*ridging*(side*math.cos(angle)+up*math.sin(angle))))
    faces=[tuple(range(n-1,-1,-1)),tuple(range((len(centers)-1)*n,len(centers)*n))]
    faces.extend((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for i in range(len(centers)-1) for j in range(n))
    return vs,faces

def build(api,proxy=False):
    for item in validate(api['cfg'].get('organic_paths',[])):
        vs,fs=geometry(item,proxy)
        api['mesh']('Rooted organic path',vs,fs,item['material'],smooth_faces=not proxy)
