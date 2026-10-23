"""Terrain-backed retaining walls, protecting routes and actual foundations."""
import math

def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3.-2.*t)

def validate(config):
    for w in config.get('walls',[])+config.get('terrain_banks',[]):
        if 'bank_height' not in w:continue
        if w.get('bank_side') not in (-1,1):raise ValueError('Wall bank needs an explicit side')
        if not .1<=w['bank_height']<=3 or not 1.5<=w.get('bank_width',4)<=8:raise ValueError('Invalid wall bank dimensions')
    return config

def offset(config,field,x,y):
    total=0.
    for w in config.get('walls',[])+config.get('terrain_banks',[]):
        if not w.get('bank_height'):continue
        width=w.get('bank_width',4.)
        for a,b in zip(w['points'],w['points'][1:]):
            dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy)
            along=((x-a[0])*dx+(y-a[1])*dy)/length
            if along < -2 or along > length+2:continue
            side=((x-a[0])*(-dy)+(y-a[1])*dx)/length*w['bank_side']
            if side<=0 or side>=width:continue
            shape=smooth(side/.7)*(1-smooth((side-1.)/(width-1.)))
            cap=smooth((along+2)/2)*smooth((length+2-along)/2)
            total=max(total,w['bank_height']*shape*cap)
    if not total:return 0.
    distance,_,width,_=field.query(x,y)
    protection=smooth((distance-width*.5-.85)/1.25)
    if not protection:return 0.
    try:from .planting_footprint import signed_distance
    except ImportError:from planting_footprint import signed_distance
    for p in config.get('places',[])+config.get('foundation_pads',[]):
        if p.get('flatten',True) is False:continue
        d=signed_distance(x,y,p['outline']) if p.get('outline') else math.hypot(x-p['center'][0],y-p['center'][1])-p['radius']
        protection=min(protection,smooth(d/.8))
    return total*protection
