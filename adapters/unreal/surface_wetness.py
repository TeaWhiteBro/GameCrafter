"""Bounded world-space drainage masks shared by validation and shader generation."""
import math
UE_TO_AUTHORED_XY=(.01,.01)

def validate(zones):
    if not isinstance(zones,list) or len(zones)>24:raise ValueError('wetness_zones must contain at most 24 ellipses')
    for zone in zones:
        for key in ['center','radii']:
            values=zone.get(key)
            if not isinstance(values,list) or len(values)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('wetness_zones '+key+' needs two finite metre values')
        if any(not .05<=v<=100 for v in zone['radii']):raise ValueError('wetness_zones radii outside 0.05-100m')
        for key,lo,hi,default in [('strength',0,1,.9),('yaw_deg',-360,360,0),('edge_softness',.05,.95,.25)]:
            v=zone.get(key,default)
            if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('wetness_zones invalid '+key)
    return zones

def evaluate(zones,x,y):
    result=0
    for z in validate(zones):
        angle=math.radians(z.get('yaw_deg',0));co,si=math.cos(angle),math.sin(angle)
        dx,dy=x-z['center'][0],y-z['center'][1]
        radius=math.hypot((dx*co+dy*si)/z['radii'][0],(-dx*si+dy*co)/z['radii'][1])
        t=max(0,min(1,(radius-(1-z.get('edge_softness',.25)))/z.get('edge_softness',.25)))
        result=max(result,z.get('strength',.9)*(1-t*t*(3-2*t)))
    return result

def shader(zones):
    # The Blender pre-export Y reflection is cancelled by FBX static import.
    # Final UE world XY equals authored XY * 100; do not reflect a second time.
    sx,sy=UE_TO_AUTHORED_XY
    code=[f'float2 p=P.xy*float2({sx},{sy});float w=Base;']
    for z in validate(zones):
        co,si=math.cos(math.radians(z.get('yaw_deg',0))),math.sin(math.radians(z.get('yaw_deg',0)))
        x,y=z['center'];rx,ry=z['radii'];edge=z.get('edge_softness',.25);strength=z.get('strength',.9)
        code.append(f'{{float2 d=p-float2({float(x)},{float(y)});float2 q=float2(dot(d,float2({co},{si}))/{float(rx)},dot(d,float2({-si},{co}))/{float(ry)});w=max(w,{strength}*(1.-smoothstep({1-edge},1.,length(q))));}}')
    code.append('return saturate(w)*smoothstep(.72,.96,N.z);')
    return ''.join(code)

def evaluate_unreal(zones,x_cm,y_cm):
    return evaluate(zones,x_cm*UE_TO_AUTHORED_XY[0],y_cm*UE_TO_AUTHORED_XY[1])
