"""One metric footprint for intact paving, its structural proxy and probes."""
import math


def cross(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def outline(cfg):
    cx, cy = cfg.get('court_center', [0, 0])
    rx, ry = cfg.get('court_radii', [7, 8])
    default = [[cx-rx, cy-ry], [cx+rx, cy-ry], [cx+rx, cy+ry], [cx-rx, cy+ry]]
    shape = cfg.get('court_outline', default)
    if not isinstance(shape, (list, tuple)) or not 3 <= len(shape) <= 32:
        raise ValueError('court_outline needs 3-32 convex world-XY vertices')
    if any(not isinstance(p, (list, tuple)) or len(p) != 2 or
           any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in shape):
        raise ValueError('court_outline vertices must be finite world-XY metres')
    area2 = sum(a[0]*shape[(i+1)%len(shape)][1]-a[1]*shape[(i+1)%len(shape)][0] for i, a in enumerate(shape))
    if area2 < 0:
        shape = list(reversed(shape))
    for i, a in enumerate(shape):
        b = shape[(i+1)%len(shape)]
        others = [p for j, p in enumerate(shape) if j not in (i, (i+1)%len(shape))]
        if any(cross(a, b, p) <= 1e-7 for p in others):
            raise ValueError('court_outline must be strictly convex, without repeated or crossing edges')
        if cross(a, b, (cx, cy)) <= 1e-7:
            raise ValueError('court_outline must contain court_center in its interior')
    if any(abs(p[0]-cx) > rx+1e-7 or abs(p[1]-cy) > ry+1e-7 for p in shape):
        raise ValueError('court_outline must stay within court_radii to retain terrain support')
    return [tuple(p) for p in shape]


def contains(shape, point):
    return all(cross(a, shape[(i+1)%len(shape)], point) >= -1e-7 for i, a in enumerate(shape))


def prism(cfg):
    shape = outline(cfg)
    n = len(shape)
    top = cfg.get('court_base_z', 0)+.135
    vertices = [(x, y, z) for z in [top-.14, top] for x, y in shape]
    faces = [tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    return vertices, faces
