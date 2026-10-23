"""Continuous curved masonry with explicit arched apertures.

Window boundaries are geometric cuts, independent of staggered texture courses.
The structural companion uses the same openings at a coarser angular resolution.
"""
import math

FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def build_wall(item,emit,material,proxy=False):
    cx,cy=item['center'];r=float(item['radius']);h=float(item['height'])
    if not all(math.isfinite(v) for v in [cx,cy,r,h]) or r<=1 or h<=2.8:
        raise ValueError('Curved wall requires a finite radius > 1 m and height > 2.8 m')
    base=item.get('base_z',.08);rot=math.radians(item.get('rotation_deg',0))
    opening=math.radians(item.get('opening_degrees',100))
    if not 0<opening<math.tau:raise ValueError('Invalid curved wall opening')
    a0=math.pi/2+opening/2+rot;a1=math.pi/2+math.tau-opening/2+rot
    windows=[rot+math.pi,rot+1.5*math.pi,rot+2*math.pi]
    half=.45;sill=2.;spring=h-1.10
    step=.30 if proxy else .13
    n=max(12,math.ceil((a1-a0)*r/step))
    cuts={a0+(a1-a0)*i/n for i in range(n+1)}
    for w in windows:
        for i in range(25):
            # Cosine sampling resolves the curved crown at its spring points.
            a=w+half*math.cos(math.pi*i/24)/r
            if a0<a<a1:cuts.add(a)
    cuts=sorted(cuts)
    vertices=[];faces=[]
    def span(a,b,low_a,low_b,high_a,high_b):
        vs=[(cx+rad*math.cos(t),cy+rad*math.sin(t),base+z)
            for rad in [r-.30,r+.30]
            for t,z in [(a,low_a),(b,low_b),(b,high_b),(a,high_a)]]
        k=len(vertices);vertices.extend(vs);faces.extend(tuple(k+i for i in f) for f in FACES)
    for a,b in zip(cuts,cuts[1:]):
        if b-a<1e-9:continue
        mid=(a+b)/2;w=min(windows,key=lambda w:abs(mid-w))
        if abs(mid-w)*r<half:
            top=lambda t:spring+math.sqrt(max(0,half*half-((t-w)*r)**2))
            span(a,b,0,0,sill,sill);span(a,b,top(a),top(b),h,h)
        else:span(a,b,0,0,h,h)
    emit('Continuous curved wall',vertices,faces,material)
    return {'segments':len(cuts)-1,'windows':3,'sill_m':sill,'spring_m':spring,'half_width_m':half}
