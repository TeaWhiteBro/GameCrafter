"""Opaque ice shading retains a defined surface for metric and semantic capture."""
import math

def validate(settings):
    if not isinstance(settings,dict):raise ValueError('Frozen surface settings must be an object')
    for name,default,low,high in [('fracture_scale_m',2.4,.5,8),('frost_strength',.46,0,1),('crack_strength',.32,0,1)]:
        value=settings.get(name,default)
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Invalid frozen surface '+name)
    return settings

def shader(settings):
    validate(settings)
    scale=float(settings.get('fracture_scale_m',2.4))*100
    return '''
struct IceNoise {
float hash(float2 p) {return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453);}
float noise(float2 p) {
float2 i=floor(p),f=frac(p);f=f*f*(3.-2.*f);
return lerp(lerp(hash(i),hash(i+float2(1,0)),f.x),lerp(hash(i+float2(0,1)),hash(i+1),f.x),f.y);
}
float fbm(float2 p) {return .57*noise(p)+.28*noise(p*2.07+11.3)+.15*noise(p*4.13-9.2);}
};
IceNoise n;
float2 q=P.xy/SCALE;
float2 warp=float2(n.fbm(q*.37),n.fbm(q*.41+17.))*1.4;
float upper=n.fbm(q+warp);
// A shallow sub-surface layer gives optical depth without transparent IDs.
float lower=n.fbm(q*.61+warp-V.xy*.28/max(abs(V.z),.25));
float frost=smoothstep(.30,.72,.66*upper+.34*lower);
float line=abs(sin(q.x*4.7+q.y*1.8+9.*n.fbm(q*.7)));
float fracture=(1.-smoothstep(.004,.022,line))*smoothstep(.56,.78,n.fbm(q*1.7+8.));
return float3(frost,fracture,lower);
'''.replace('SCALE',str(scale))
