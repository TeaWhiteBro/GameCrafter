"""Shallow authored deposits on terrain, including after foundation flattening.

The detailed terrain and its structural companion use the same final height.
Deposits are bounded, non-additive and independent of scene/asset identity.
"""
import math


def validate(items):
    if not isinstance(items, list) or len(items) > 32:
        raise ValueError('Surface deposits require at most 32 bands')
    for item in items:
        if set(item) != {'points', 'height', 'width'}:
            raise ValueError('Unknown surface deposit field')
        points = item['points']
        if not isinstance(points, list) or not 2 <= len(points) <= 16:
            raise ValueError('Deposit needs 2-16 XY points')
        if any(not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points):
            raise ValueError('Deposit coordinates must be finite')
        if any(math.dist(a, b) < .25 for a, b in zip(points, points[1:])):
            raise ValueError('Deposit segments are degenerate')
        for key, low, high in [('height', .01, .25), ('width', .75, 5.)]:
            v = item[key]
            if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
                raise ValueError('Invalid deposit ' + key)
    return items


def offset(items, x, y):
    result = 0.
    for item in items:
        d = float('inf')
        for a, b in zip(item['points'], item['points'][1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            t = max(0., min(1., ((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
            d = min(d, math.hypot(x-a[0]-t*dx, y-a[1]-t*dy))
        # Small variation breaks a ruler-straight snow lip, without moving bases.
        width = item['width'] * (1 + .12*math.sin(x*.53+y*.39))
        t = max(0., 1-d/width)
        result = max(result, item['height']*t*t*(3-2*t))
    return result
