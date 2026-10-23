"""Check a deliberately unpaved combat area against actual terrain geometry."""
import math


def evaluate(cfg, surface, expected):
    cx, cy = cfg.get('court_center', [0, 0])
    rx, ry = cfg['court_radii']
    rows = []
    for j in range(9):
        for i in range(9):
            dx, dy = (i - 4 + .13) * .16, (j - 4 + .07) * .16
            if math.hypot(dx, dy) > .72:
                continue
            x, y = cx + dx * rx, cy + dy * ry
            samples = [surface(x, y), surface(x + .3, y), surface(x, y + .3)]
            finite = all(v is not None and math.isfinite(v) for v in samples)
            reference = expected(x, y)
            error = abs(samples[0] - reference) if finite else None
            grade = math.hypot(samples[1] - samples[0], samples[2] - samples[0]) / .3 if finite else None
            rows.append({'xy_m': [x, y], 'terrain_z_m': samples[0], 'error_m': error,
                         'grade': grade, 'passed': finite and math.isfinite(reference) and error <= .18 and grade <= .45})
    return {'surface_mode': 'terrain', 'method': 'Independent saved terrain rays; no paving required or generated. Maximum grade 0.45 and authoring error 0.18m.',
            'samples': len(rows), 'passed': len(rows) >= 9 and all(r['passed'] for r in rows), 'rows': rows}
