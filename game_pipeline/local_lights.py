"""Portable contract for bounded, physically sized practical point lights."""
import math

def validate(lighting):
    if lighting.get('weather_profile','clear') not in ('clear','overcast'):raise ValueError('Unknown weather profile')
    if lighting.get('sky_mode','daylight_cubemap') not in ['daylight_cubemap','captured']:raise ValueError('Unknown sky mode')
    for key in ['sky_color','fog_color']:
        if key not in lighting:continue
        v=lighting[key]
        if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in v):raise ValueError(key+' requires RGB within 0-1')
    for name,default,lo,hi in [('sun_angle_deg',2.2,.1,8),('bloom_intensity',.05,0,.5),('fog_start_m',22,0,500),('fog_height_falloff',.2,.001,2),('sky_luminance_factor',1,1,20000)]:
        value=lighting.get(name,default)
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid '+name)
    lights=lighting.get('local_lights',[])
    if not isinstance(lights,list) or len(lights)>12:raise ValueError('local_lights must be an array with at most 12 lights')
    for light in lights:
        if not isinstance(light,dict):raise ValueError('Each local light must be an object')
        for key in ('position','color'):
            if not isinstance(light.get(key),list) or len(light[key])!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in light[key]):raise ValueError('Light '+key+' requires three finite values')
        if any(v<0 or v>1 for v in light['color']):raise ValueError('Light color must be within 0-1')
        for key,lo,hi in [('intensity_lm',10,50000),('range_m',.5,30),('source_radius_m',.01,1)]:
            value=light.get(key,.12 if key=='source_radius_m' else None)
            if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Light '+key+' must be within '+str((lo,hi)))
        if 'intensity' in light:raise ValueError('Use explicit intensity_lm, not unitless local light intensity')
    return lights
