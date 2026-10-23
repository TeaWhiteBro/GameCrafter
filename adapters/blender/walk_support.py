"""Locate measured walkable support near the route's declared foot elevation.

The search cannot jump onto a roof or arbitrary obstacle. A missing surface,
underside, steep face or elevation error outside the step envelope is a failure.
"""
import math


def point_sample(cast, x, y, expected_z, units=1.0):
    upper=.31; lower=.35
    hit,normal,_,_=cast((x,y,expected_z+upper*units),(0,0,-1),(upper+lower)*units)
    if hit is None:
        raise ValueError('No physical walking support within the declared step envelope')
    if normal is None or not math.isfinite(normal[2]) or normal[2]<.65:
        raise ValueError('Walking support is an underside or excessive slope')
    delta=(hit[2]-expected_z)/units
    if not math.isfinite(delta) or not -lower<=delta<=upper:
        raise ValueError('Physical walking support disagrees with the route elevation')
    return float(hit[2])


def sample(cast, x, y, expected_z, units=1.0):
    try:return point_sample(cast,x,y,expected_z,units)
    except ValueError as center_error:
        # Millimetre plank joints and bevel facets are not holes under a foot.
        # Require a measured small footprint, not an unconstrained height guess.
        values=[]
        for dx,dy in [(-.055,-.055),(-.055,.055),(.055,-.055),(.055,.055)]:
            try:values.append(point_sample(cast,x+dx*units,y+dy*units,expected_z,units))
            except ValueError:pass
        if len(values)<3 or (max(values)-min(values))/units>.18:
            raise center_error
        values.sort()
        return values[len(values)//2]
