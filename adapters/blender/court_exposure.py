"""Detect a paved gameplay court hidden beneath the actual terrain surface."""
import math

def evaluate(cfg,terrain,paving):
    cx,cy=cfg.get('court_center',[0,0]);rx,ry=cfg['court_radii'];rows=[]
    shape=None
    if cfg.get('court_outline') is not None:
        try:from .court_outline import outline,contains
        except ImportError:from court_outline import outline,contains
        shape=outline(cfg)
    for j in range(9):
        for i in range(9):
            dx=(i-4+.13)*.16;dy=(j-4+.07)*.16
            if cfg.get('paving_style')!='modular' and math.hypot(dx,dy)>.72:continue
            if cfg.get('paving_style')=='modular':dx*=1.34;dy*=1.34
            x,y=cx+dx*rx,cy+dy*ry
            if shape and not contains(shape,(x,y)):continue
            t=terrain(x,y);p=paving(x,y)
            rows.append({'xy_m':[x,y],'terrain_z_m':t,'paving_z_m':p,'exposed':p is not None and t is not None and p>t+.002})
    hits=[r for r in rows if r['paving_z_m'] is not None]
    missing_terrain=sum(r['terrain_z_m'] is None for r in rows)
    exposed=sum(r['exposed'] for r in hits)
    return {'method':'Independent vertical rays against actual separate terrain and paving meshes; inner court only.',
        'samples':len(rows),'paving_hits':len(hits),'exposed_hits':exposed,'missing_terrain':missing_terrain,
        'passed':len(rows)>=9 and not missing_terrain and len(hits)>=len(rows)*.70 and exposed>=len(hits)*.98,
        'rows':rows}
