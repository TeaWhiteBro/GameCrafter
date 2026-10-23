"""Bounded opaque reflective water for single-surface metric capture."""
import math


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('water_surface must be an object')
    for key, low, high, default in [
        ('ripple_scale_m', .15, 8, 1.4), ('normal_amplitude', .005, .2, .055),
        ('speed', 0, 3, .45), ('roughness', .06, .4, .16), ('bed_visibility', 0, .65, .2)
    ]:
        value = data.get(key, default)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Invalid water_surface.' + key)
    tint = data.get('tint', [.035, .10, .075])
    if not isinstance(tint, list) or len(tint) != 3 or any(type(v) not in (int, float) or not 0 <= v <= 1 for v in tint):
        raise ValueError('Water tint requires three linear values in [0,1]')
    return data


def normal_shader(data):
    validate(data)
    scale = data.get('ripple_scale_m', 1.4) * 100
    speed = data.get('speed', .45)
    amplitude = data.get('normal_amplitude', .055)
    return f'''float3 baseNormal=normalize(N);
float3 tangent=abs(baseNormal.z)>.85?float3(1.,0.,0.):normalize(cross(float3(0.,0.,1.),baseNormal));
float3 bitangent=normalize(cross(baseNormal,tangent));
float2 q=float2(dot(P,tangent),dot(P,bitangent))/{scale:.8f};
float vertical=1.-abs(baseNormal.z); float t=T*{speed:.8f};
q.y+=vertical*t*.17;
float a=6.2831853*(q.x*.87+q.y*.49)+t;
float b=6.2831853*(-q.x*.31+q.y*.95)*1.73-t*1.21;
float c=6.2831853*(q.x*.64-q.y*.77)*3.1+t*.73;
float2 slope={amplitude:.8f}*(float2(.87,.49)*cos(a)+.45*float2(-.31,.95)*cos(b)+.18*float2(.64,-.77)*cos(c));
return normalize(baseNormal-tangent*slope.x-bitangent*slope.y);'''


def variation_shader(data):
    """Bounded bed-color variation; this is not simulated subsurface depth."""
    validate(data)
    scale=data.get('ripple_scale_m',1.4)*100
    speed=data.get('speed',.45)
    return f'''float2 q=P.xy/{scale:.8f};
float broad=.5+.22*sin(q.x*.29+1.15*sin(q.y*.23))+.18*sin(q.y*.47+q.x*.17);
float drift=.5+.5*sin(q.x*2.1+q.y*.67+T*{speed:.8f}*.19);
return saturate(.82*broad+.18*drift);'''
