"""A constructed stair/floor owns its terrain envelope, independently of road splines."""
import math

def below_structures(items,x,y,terrain):
    result=terrain
    for item in items:
        if item.get('kind')!='terraced_foundation' or 'base_z' not in item:continue
        cx,cy=item['center'];width,length=item['size'];base=item['base_z'];rise=item['rise']
        run=item.get('stair_run',2.0);start=cy-length*.5-run;end=cy+length*.5
        dx=max(0,abs(x-cx)-width*.5);dy=max(0,start-y,y-end)
        distance=math.hypot(dx,dy)
        if distance>=.8:continue
        t=max(0,min(1,(y-start)/run))
        # Below the *lower* edge of each tread, including the full road width.
        ceiling=base+rise*t-.16
        weight=1-distance/.8;weight=weight*weight*(3-2*weight)
        result-=max(0,result-ceiling)*weight
    return result
