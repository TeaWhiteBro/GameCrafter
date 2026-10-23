"""Timber lodge enclosure with a real portal, shared by detailed and proxy builds."""
import math


def build(item, pt, box, emit, yaw, proxy=False):
    w,l=item['size'];h=item.get('height',4.5);rise=item.get('roof_rise',1.8)
    wood=item.get('cladding_material',item['timber_material'])
    frame=item['timber_material'];glass=item['window_material']
    door=min(3.4,w*.4);door_h=min(3.1,h-.35)
    # Close the rear and side walls. Front faces +Y and retains a generous door.
    def panels(label,axis,fixed,lo,hi,zlo,zhi,material):
        n=1 if proxy else max(1,math.ceil((hi-lo)/.24))
        for i in range(n):
            mid=lo+(i+.5)*(hi-lo)/n;length=(hi-lo)/n-(0 if proxy else .006)
            p=pt(mid,fixed,(zlo+zhi)/2) if axis==0 else pt(fixed,mid,(zlo+zhi)/2)
            dims=(length,.18,zhi-zlo) if axis==0 else (.18,length,zhi-zlo)
            box(label,p,dims,material,yaw,smooth=False)
    for sign in [-1,1]:panels('Lodge vertical side boards',1,sign*w/2,-l/2,l/2,1.22,h,wood)
    panels('Lodge rear enclosure',0,-l/2,-w/2,w/2,.08,h,wood)
    for lo,hi in [(-w/2,-door/2),(door/2,w/2)]:
        panels('Lodge front enclosure',0,l/2,lo,hi,.08,h,wood)
    panels('Lodge doorway lintel panel',0,l/2,-door/2,door/2,door_h,h,wood)
    for xx in [-door/2,door/2]:box('Lodge door jamb',pt(xx,l/2+.08,door_h/2),(.22,.30,door_h),frame,yaw,smooth=False)
    box('Lodge door lintel',pt(0,l/2+.08,door_h),(door+.42,.32,.24),frame,yaw,smooth=False)
    # Thick gable infill prevents a bright slit below the snow roof.
    for yy in [-l/2,l/2]:
        vs=[pt(xx,yy+dy,zz) for dy in [-.10,.10] for xx,zz in [(-w/2,h),(w/2,h),(0,h+rise+.14)]]
        emit('Lodge gable cladding',vs,[(0,2,1),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)],wood,0,smooth=False)
    # Warm opaque panes preserve exact semantic labels. Window frames sit proud
    # of the wood wall, avoiding co-planar flicker in both representations.
    for sign in [-1,1]:
        for yy in [-l*.27,l*.18]:
            x=sign*(w/2+.12);z=2.25;ww=1.35;hh=1.15
            box('Lodge amber window',pt(x,yy,z),(.10,ww,hh),glass,yaw,smooth=False)
            for dy in [-ww/2,0,ww/2]:box('Lodge window upright',pt(x+sign*.07,yy+dy,z),(.12,.085,hh+.16),frame,yaw,smooth=False)
            for dz in [-hh/2,0,hh/2]:box('Lodge window rail',pt(x+sign*.07,yy,z+dz),(.12,ww+.16,.085),frame,yaw,smooth=False)
            box('Lodge window snow sill',pt(x+sign*.10,yy,z-hh/2-.06),(.28,ww+.30,.12),item['roof_material'],yaw,smooth=False)
