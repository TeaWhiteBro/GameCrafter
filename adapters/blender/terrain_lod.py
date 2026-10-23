"""Bounded terrain resampling; the caller supplies independent surface probes."""
import math

def grid(extent,step,height):
    n=math.ceil(extent/step)
    vs=[((i/n-.5)*extent,(j/n-.5)*extent,height((i/n-.5)*extent,(j/n-.5)*extent)) for j in range(n+1) for i in range(n+1)]
    fs=[(j*(n+1)+i,j*(n+1)+i+1,(j+1)*(n+1)+i+1,(j+1)*(n+1)+i) for j in range(n) for i in range(n)]
    return vs,fs,extent/n

def probe_regions(extent,config):
    """Cover the authored play envelope and each local bank independently."""
    exploration=config.get('exploration',{});regions={};limit=extent/2-.001
    bounds=exploration.get('play_bounds')
    if bounds:
        lo,hi=bounds['min'],bounds['max']
        regions['playable_extent']=[(lo[0]+(hi[0]-lo[0])*(i+.37)/31,
                                     lo[1]+(hi[1]-lo[1])*(j+.61)/31) for i in range(31) for j in range(31)]
    for index,bank in enumerate(exploration.get('route_banks',[])):
        cx,cy=bank['center'];rx,ry=bank['radii']
        step=max(.5,config.get('terrain_grid_m',.5),math.sqrt(4*rx*ry/6000))
        nx,ny=math.ceil(2*rx/step),math.ceil(2*ry/step)
        points=[]
        for i in range(nx):
            x=cx-rx+2*rx*(i+.37)/nx
            for j in range(ny):
                y=cy-ry+2*ry*(j+.61)/ny
                if ((x-cx)/rx)**2+((y-cy)/ry)**2<1:points.append((x,y))
        regions['route_bank_'+str(index)]=points
        # A second independent lattice catches steep lips that fall between the
        # offset probes. Each phase is a separate gate, not diluted in an average.
        lattice=[]
        for i in range(nx):
            x=cx-rx+2*rx*i/nx
            for j in range(ny):
                y=cy-ry+2*ry*j/ny
                if ((x-cx)/rx)**2+((y-cy)/ry)**2<=1:lattice.append((x,y))
        regions['route_bank_'+str(index)+'_lattice']=lattice
    for name,points in regions.items():
        if not points or any(not math.isfinite(v) or abs(v)>limit for p in points for v in p):
            raise ValueError('Terrain validation region lies outside the detailed surface: '+name)
    return regions


def refine(extent,initial_step,min_step,height,evaluate,tolerance=.18,evaluate_regions=None):
    if not 0<min_step<=initial_step<=extent:raise ValueError('Invalid bounded terrain sampling resolution')
    attempts=[];step=initial_step
    for _ in range(8):
        vs,fs,effective=grid(extent,step,height)
        errors=sorted(evaluate(vs,fs))
        if not errors or any(not math.isfinite(v) or v<0 for v in errors):raise ValueError('Terrain probes need complete finite surface measurements')
        p95=errors[min(len(errors)-1,int(len(errors)*.95))]
        regions={}
        if evaluate_regions is not None:
            values=evaluate_regions(vs,fs)
            if not isinstance(values,dict):raise ValueError('Regional terrain probes must be named groups')
            for name,samples in values.items():
                samples=sorted(samples)
                if not samples or any(not math.isfinite(v) or v<0 for v in samples):raise ValueError('Regional terrain probes need complete finite measurements: '+name)
                regions[name]={'samples':len(samples),'p95_error_m':samples[min(len(samples)-1,int(len(samples)*.95))],'max_error_m':samples[-1]}
        attempts.append({'step_m':effective,'vertices':len(vs),'samples':len(errors),'p95_error_m':p95,'max_error_m':errors[-1],'regions':regions})
        if p95<=tolerance and all(r['p95_error_m']<=tolerance for r in regions.values()):return vs,fs,{'passed':True,'attempts':attempts,'p95_error_m':p95,'grid_m':effective,'regions':regions}
        if step<=min_step+1e-9:break
        step=max(min_step,step*.65)
    return vs,fs,{'passed':False,'attempts':attempts,'p95_error_m':p95,'grid_m':effective,'regions':regions}
