"""Check effective engine lighting before starting native assembly."""
import math

def effective_lighting(authored,overrides=None):
    lighting={**authored,**(overrides or {})}
    pitch=lighting.get('sun_pitch')
    if type(pitch) not in (int,float) or not math.isfinite(pitch) or not -90<=pitch<=0:
        raise ValueError('sun_pitch is Unreal rotation, not solar elevation: use -90..0 degrees for a downward key light; positive pitch illuminates the sky from below')
    return lighting
