"""Smooth terrain banks around configured route sections, preserving corridors."""
import math
def validate(config):
    ids={r.get('id') for r in config.get('routes',[])}
    for b in config.get('route_banks',[]):
        for key in ['center','radii']:
            if len(b.get(key,[]))!=2 or any(not isinstance(v,(float,int)) or not math.isfinite(v) for v in b[key]):raise ValueError('Banks require finite XY '+key)
        if any(v<2 or v>40 for v in b['radii']):raise ValueError('Bank radii must be 2-40m')
        if not .1<=b.get('height',0)<=10 or not 1.5<=b.get('bank_width',5.5)<=12:raise ValueError('Bank height or width outside supported range')
        if not .5<=b.get('corridor_margin',.85)<=3:raise ValueError('Bank corridor margin outside supported range')
        if not b.get('route_ids') or not set(b['route_ids'])<=ids:raise ValueError('Bank references unknown routes')
        for key,low,high,default in [('profile_exponent',.65,3,2),('erosion_strength',0,.75,0),('erosion_scale_m',.8,8,2)]:
            value=b.get(key,default)
            if type(value) not in (float,int) or not math.isfinite(value) or not low<=value<=high:
                raise ValueError('Invalid bank '+key)
def offset(config,field,x,y):
    candidates=[]
    for bank in config.get('route_banks',[]):
        cx,cy=bank['center'];rx,ry=bank['radii'];q=((x-cx)/rx)**2+((y-cy)/ry)**2
        if q<1:candidates.append((bank,q))
    if not candidates:return 0.
    # Banks are applied after flattening, so explicitly protect the authored
    # combat courts and structural foundations as well as walking corridors.
    # Otherwise a valid snow-bank preset can bury a floor or slope a duel area.
    protection=1.
    for place in config.get('places',[])+config.get('foundation_pads',[]):
        if place.get('flatten',True) is False:continue
        if place.get('outline'):
            try:from .planting_footprint import signed_distance
            except ImportError:from planting_footprint import signed_distance
            distance=signed_distance(x,y,place['outline'])
        else:distance=math.hypot(x-place['center'][0],y-place['center'][1])-place['radius']
        t=max(0,min(1,distance/max(.5,place.get('edge_fade_m',1.))))
        protection=min(protection,t*t*(3-2*t))
    if protection==0:return 0.
    total=0.
    for bank,q in candidates:
        distance,z,width,index=field.query(x,y,bank['route_ids'])
        if index<0:continue
        clear=width*.5+bank.get('corridor_margin',.85);t=(distance-clear)/bank.get('bank_width',5.5)
        if not 0<t<1:continue
        taper=min(1,(1-q)*3);taper=taper*taper*(3-2*taper)
        # Query the selected route independently. A nearest-route identity
        # switch must not turn a nonzero bank into a vertical construction seam.
        all_distance,_,all_width,_=field.query(x,y)
        safety=max(0,min(1,(all_distance-all_width*.5-bank.get('corridor_margin',.85))/1.5))
        safety=safety*safety*(3-2*safety)
        erosion=bank.get('erosion_strength',0);scale=bank.get('erosion_scale_m',2)
        # Continuous domain-warped gullies vary a bank locally. The shared
        # terrain path still protects every corridor and foundation below.
        u=x/scale+.55*math.sin(y/scale*.71);v=y/scale+.37*math.sin(x/scale*.83)
        detail=.52+.22*math.sin(u*1.73+v*.61)+.17*math.sin(v*2.19-u*.43)+.09*math.sin(u*3.4+v*1.8)
        response=(1-erosion)+erosion*max(.10,min(1,detail))
        total+=bank['height']*math.sin(math.pi*t)**bank.get('profile_exponent',2)*taper*safety*(.90+.10*math.sin(x*.53+y*.71))*response
    return total*protection
