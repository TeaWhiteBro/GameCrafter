"""Authored ground regions blend continuously before walkable-route overrides."""
import math

def weights(regions,x,y,current):
    result=tuple(current)
    for region in regions:
        cx,cy=region['center'];rx,ry=region['radii'];yaw=math.radians(region.get('yaw_deg',0))
        dx=x-cx;dy=y-cy;u=dx*math.cos(yaw)+dy*math.sin(yaw);v=-dx*math.sin(yaw)+dy*math.cos(yaw)
        distance=math.hypot(u/rx,v/ry)
        fade=max(.02,min(.9,region.get('edge_fraction',.25)))
        t=max(0,min(1,(1-distance)/fade));t=t*t*(3-2*t)
        result=tuple(a*(1-t)+b*t for a,b in zip(result,region['weights']))
    return result
