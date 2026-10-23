"""Footings reach terrain along their full perimeter, including concave slopes."""
import math

def footing_bottom(height, center, size, yaw=0, embed=.22, spacing=.20):
    w,d=size;ca,sa=math.cos(yaw),math.sin(yaw)
    points=[(0.,0.)]
    for axis,length in [(0,w),(1,d)]:
        n=max(1,math.ceil(length/spacing))
        for i in range(n+1):
            a=(i/n-.5)*length
            points.extend([(a,-d/2),(a,d/2)] if axis==0 else [(-w/2,a),(w/2,a)])
    samples=[height(center[0]+x*ca-y*sa,center[1]+x*sa+y*ca) for x,y in points]
    if not all(math.isfinite(v) for v in samples):raise ValueError('Nonfinite terrain below structural footing')
    return min(samples)-embed

def stair_boxes(position,size,yaw,height,steps=7):
    for i in range(steps):
        yy=(i/steps-.5)*size[1];top=position[2]+size[2]*(i+1)/steps
        xy=(position[0]-yy*math.sin(yaw),position[1]+yy*math.cos(yaw))
        footprint=(size[0],size[1]/steps+.015)
        bottom=min(position[2],footing_bottom(height,xy,footprint,yaw))
        yield (*xy,(bottom+top)/2),(*footprint,top-bottom)
