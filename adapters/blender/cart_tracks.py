"""Bounded paired wheel ruts in an authored earth route, without decal ribbons."""
import math

def profile(route,distance):
    settings=route.get('wheel_ruts')
    if not settings:return 0.,0.
    spacing=settings['spacing_m'];width=settings['width_m'];depth=settings['depth_m']
    if not .8<=spacing<=2.8 or not .2<=width<=.8 or not 0<=depth<=.06:
        raise ValueError('Wheel ruts exceed supported shallow walking profile')
    if route.get('surface')!='earth':raise ValueError('Wheel ruts require an earth route')
    strength=math.exp(-((abs(distance)-spacing*.5)/width)**2)
    return strength,-depth*strength

def offset(field,x,y):
    distance,_,_,index=field.query(x,y)
    return profile(field.routes[index][0],distance)[1] if index>=0 else 0.
