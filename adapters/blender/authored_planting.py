"""Bounded low-planting pockets outside measured walking corridors.

Authored points describe deliberately placed non-colliding understory in gaps
between constructed edges. They do not redefine broad foundation clearances.
Detailed source support and current visual inspection remain required.
"""
import math


def validate(region, field):
    points = region.get('authored_points')
    if points is None:
        return
    if not isinstance(points, list) or not 1 <= len(points) <= 512:
        raise ValueError('Authored planting requires 1..512 points')
    if region.get('count') != len(points) or len(region.get('palette', [])) != 1:
        raise ValueError('Authored planting count and single palette must match')
    palette = region['palette'][0]
    if palette.get('collision', False) or palette.get('grounding') != 'base':
        raise ValueError('Authored pockets require non-colliding base-grounded plants')
    cx, cy = region['center']; rx, ry = region['radii']
    for point in points:
        if not isinstance(point, list) or len(point) != 5 or not all(type(v) in (int, float) and math.isfinite(v) for v in point):
            raise ValueError('Authored point requires finite x, y, size, height ratio, yaw')
        x, y, size, ratio, yaw = point
        if not .15 <= size <= 3.5 or not .3 <= ratio <= 1.2:
            raise ValueError('Authored pocket plants must remain bounded understory')
        if ((x-cx)/rx)**2 + ((y-cy)/ry)**2 > 1.000001:
            raise ValueError('Authored planting point lies outside its declared region')
        distance, _, width = field.nearest(x, y)
        if distance < width*.5 + size*.5 + .5:
            raise ValueError('Authored planting encroaches on a walking corridor')


def build(region, api):
    validate(region, api['route_field'])
    asset = region['palette'][0]['asset']
    for i, (x, y, size, ratio, yaw) in enumerate(region['authored_points']):
        api['instance'](asset, (x, y, api['height'](x, y)),
                        (size, size, size*ratio), math.radians(yaw), i, False,
                        choose_palette=False, ground='base')
    return len(region['authored_points'])
