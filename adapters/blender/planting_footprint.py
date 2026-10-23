"""World-XY planting exclusions, independent of discovery/flattening radius."""
import math

def validate_outline(points):
    if not isinstance(points,list) or not 3<=len(points)<=32 or any(not isinstance(p,(list,tuple)) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('clear_outline requires 3-32 finite XY vertices')
    signs=[]
    for a,b in zip(points,points[1:]+points[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        if math.hypot(dx,dy)<1e-6:raise ValueError('clear_outline has a zero-length edge')
        cross=[dx*(p[1]-a[1])-dy*(p[0]-a[0]) for p in points]
        if min(cross)<-1e-8 and max(cross)>1e-8:raise ValueError('clear_outline must be convex and nonintersecting')
        signs += [c for c in cross if abs(c)>1e-8]
    if not signs or min(signs)<0<max(signs):raise ValueError('clear_outline must be a nondegenerate convex polygon')

def signed_distance(x,y,points):
    distances,cross=[],[]
    for a,b in zip(points,points[1:]+points[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
        distances.append(math.hypot(x-a[0]-t*dx,y-a[1]-t*dy));cross.append(dx*(y-a[1])-dy*(x-a[0]))
    inside=min(cross)>=-1e-9 or max(cross)<=1e-9
    return -min(distances) if inside else min(distances)

def validate_place(place):
    if 'clear_outline' not in place:return
    outline=place['clear_outline'];validate_outline(outline)
    if 'clear_radius' in place:raise ValueError('Choose clear_outline or clear_radius, not both')
    if place.get('surface','stone')!='none':
        if not place.get('outline'):raise ValueError('Paved clear_outline requires an explicit paving outline')
        if any(signed_distance(*p,outline)>1e-6 for p in place['outline']):raise ValueError('clear_outline must contain the complete paved footprint')
