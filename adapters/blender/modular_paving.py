"""Intact modular paving, separate from intentionally worn cellular masonry.

Clipped running-bond slabs have millimetre joints over a continuous support.
All outlines are metric, and the support follows the same terrain as the slabs.
"""
import math
import numpy as np

FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def clean_polygon(points):
    result=[]
    for point in points:
        if not result or np.linalg.norm(point-result[-1])>1e-8:result.append(np.asarray(point,float))
    if len(result)>1 and np.linalg.norm(result[0]-result[-1])<1e-8:result.pop()
    area=abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(result,result[1:]+result[:1])))/2
    return result if len(result)>=3 and area>1e-10 else []

def difference(subject,excluded):
    """Partition a convex subject outside a convex footprint, without overlap."""
    from landscape_routes import clip
    shape=np.asarray(excluded,float);inside=[np.asarray(p,float) for p in subject];outside=[]
    signed=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(shape,np.roll(shape,-1,axis=0)))
    if signed<0:shape=shape[::-1]
    for a,b in zip(shape,np.roll(shape,-1,axis=0)):
        delta=b-a;normal=np.array([delta[1],-delta[0]])
        fragment=clean_polygon(clip(inside,-normal,a))
        if fragment:outside.append(fragment)
        inside=clean_polygon(clip(inside,normal,a))
        if len(inside)<3:break
    return outside

def uncovered(outline,exclusions):
    pieces=[outline]
    for excluded in exclusions:
        elo=np.min(excluded,axis=0);ehi=np.max(excluded,axis=0);remaining=[]
        for poly in pieces:
            lo=np.min(poly,axis=0);hi=np.max(poly,axis=0)
            if np.any(hi<elo) or np.any(lo>ehi):remaining.append(poly)
            else:remaining.extend(difference(poly,excluded))
        pieces=remaining
    return pieces

def cells(outline,size=(1.2,.6),joint=.008):
    from landscape_routes import clip
    shape=np.asarray(outline,float)
    if sum(np.cross(shape[(i+1)%len(shape)],p) for i,p in enumerate(shape))>0:shape=shape[::-1]
    lo=shape.min(0);hi=shape.max(0);sx,sy=size
    for row in range(math.floor(lo[1]/sy),math.ceil(hi[1]/sy)):
        shift=(row%2)*sx*.5
        for col in range(math.floor((lo[0]-shift)/sx),math.ceil((hi[0]-shift)/sx)):
            x=col*sx+shift;y=row*sy
            poly=[np.array(p) for p in [(x+joint/2,y+joint/2),(x+sx-joint/2,y+joint/2),(x+sx-joint/2,y+sy-joint/2),(x+joint/2,y+sy-joint/2)]]
            for i,a in enumerate(shape):
                b=shape[(i+1)%len(shape)];d=b-a
                poly=clip(poly,np.array([d[1],-d[0]]),a)
                if len(poly)<3:break
            if len(poly)>=3:
                area=abs(sum(np.cross(poly[i],poly[(i+1)%len(poly)]) for i in range(len(poly))))/2
                if area>.0001:yield np.asarray(poly)

def patch(api,outline,material,size=(1.2,.6),top=None,offset=.045,zones=(),joint=.008,tone_range=(.93,1.03)):
    from landscape_routes import zone_material
    def ground(p):return api['height'](*p)+offset if top is None else top
    # Tessellated mortar support avoids exposed undersides and terrain holes.
    for poly in cells(outline,(.45,.45),0):
        # Single-sided bedding has an authored upper face. Closed-volume
        # normal recalculation can arbitrarily flip disconnected sheet cells.
        if sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,np.roll(poly,-1,axis=0)))<0:poly=poly[::-1]
        n=len(poly);vs=[(float(p[0]),float(p[1]),ground(p)-.008) for p in poly]
        api['mesh']('Intact paving continuous support',vs,[tuple(range(n))],material,colors=[(.84,0,0,1)]*n,smooth_faces=False,preserve_winding=True)
    count=0
    for poly in cells(outline,size,joint):
        center=poly.mean(0);fit=np.c_[poly-center,np.ones(len(poly))]
        plane=np.linalg.lstsq(fit,np.array([ground(p) for p in poly]),rcond=None)[0]
        heights=fit@plane;n=len(poly)
        vs=[(float(p[0]),float(p[1]),float(z+dz)) for dz in [-.12,0] for p,z in zip(poly,heights)]
        fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        value=api['rng'].uniform(*tone_range)
        chosen=zone_material(center,material,zones)
        ob=api['mesh']('Intact modular paving slab',vs,fs,chosen,colors=[(value,0,0,1)]*len(vs),smooth_faces=False)
        api['finish_stone'](ob,.002);count+=1
    return count

def court(api):
    from court_outline import outline
    cfg=api['cfg']
    return patch(api,outline(cfg),api['spec']['path_material'],cfg.get('paver_size',[1.2,.6]),cfg.get('court_base_z',0)+.135,
                 zones=cfg.get('court_material_zones',[]),joint=cfg.get('paver_joint_m',.008),tone_range=cfg.get('paver_tone_range',[.93,1.03]))

def routes(api):
    from landscape_routes import paving_strips,footprint,fitted_patch
    from court_outline import outline as court_outline
    field=api['route_field'];cfg=field.config;count=0
    # One owner per surface region. Previously every path and place independently
    # filled their overlap, producing coincident slab faces at city junctions.
    exclusions=cfg.get('paving_exclusions',[])
    occupied=list(exclusions)+[footprint(p) for p in cfg.get('places',[]) if p.get('surface','stone')!='none']
    if api['cfg'].get('paving_style')=='modular':occupied.append(court_outline(api['cfg']))
    for ri,(route,points) in enumerate(field.routes):
        if route.get('surface')=='earth':continue
        paving_api=api
        if route.get('raised_surface',False):
            paving_api=dict(api)
            paving_api['height']=lambda x,y,rid=route['id']:max(api['height'](x,y),field.query(x,y,[rid])[1])
        for _,a,b,outline in paving_strips(points,field.route_widths[ri]):
            for piece in uncovered(outline,occupied):
                if route.get('paving_style')=='cellular':
                    if route.get('raised_surface',False):
                        raise ValueError('Cellular route gaps require terrain-supported paving')
                    # Only actual road shoulders fade. A clipped court/deck
                    # boundary or construction join must not gain a bare band.
                    edges=[]
                    for i,p in enumerate(piece):
                        q=piece[(i+1)%len(piece)]
                        for side in (0,2):
                            u=np.asarray(outline[side]);v=np.asarray(outline[(side+1)%4]);d=v-u
                            if all(abs(float(np.cross(d,np.asarray(t)-u)))<1e-6 for t in (p,q)):
                                edges.append(i);break
                    count+=fitted_patch(paving_api,piece,route.get('material',cfg['paving_material']),
                        route.get('stone_spacing',.65),route.get('coverage',.97),.58,
                        route.get('edge_fade_m',.55) if edges else 0.,edges,
                        material_zones=route.get('material_zones',[]))
                else:
                    count+=patch(paving_api,piece,route.get('material',cfg['paving_material']),route.get('paver_size',[1.2,.6]),
                                 zones=route.get('material_zones',[]),joint=route.get('joint_m',.008),tone_range=route.get('tone_range',[.93,1.03]))
            occupied.append(outline)
    occupied=list(exclusions)+([court_outline(api['cfg'])] if api['cfg'].get('paving_style')=='modular' else [])
    for place in cfg.get('places',[]):
        if place.get('surface','stone')!='none':
            shape=footprint(place)
            for piece in uncovered(shape,occupied):
                count+=patch(api,piece,place.get('material',cfg['paving_material']),place.get('paver_size',[1.2,.6]),offset=.049,
                             zones=place.get('material_zones',[]),joint=place.get('joint_m',.008),tone_range=place.get('tone_range',[.93,1.03]))
            occupied.append(shape)
    return count
