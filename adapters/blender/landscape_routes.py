"""Authored route networks, embedded paving and spatially distinct planting.

All geometry and resource choices come from the scene contract. The itinerary is
separate from the physical edges: retracing a branch never duplicates its mesh.
"""
import math
import numpy as np
try:
    from .ground_support import footing_bottom
except ImportError:
    from ground_support import footing_bottom


def base_origin(vertices,position,scale,yaw,height):
    """Seat structured assets by their actual feet/roots, not the lower rock flank."""
    points=np.asarray(vertices,dtype=float)*np.asarray(scale,dtype=float)
    low=points[points[:,2]<=points[:,2].min()+max(.025,np.ptp(points[:,2])*.03)]
    low=low[np.linspace(0,len(low)-1,min(96,len(low)),dtype=int)]
    ca,sa=math.cos(yaw),math.sin(yaw)
    xy=np.column_stack([low[:,0]*ca-low[:,1]*sa,low[:,0]*sa+low[:,1]*ca])+np.asarray(position[:2])
    heights=np.array([height(float(x),float(y)) for x,y in xy])
    z=float(np.min(heights-low[:,2])-min(.10,.015*np.ptp(points[:,2])))
    return z,{'support_samples':len(low),'method':'feet_or_roots','contact_band_height_fraction':.03,
        'vertical_adjustment_m':z-float(position[2])}


def rock_origin(vertices,position,scale,yaw,height):
    """Settle a rotated scan using its actual underside across sloping terrain."""
    points=np.asarray(vertices,dtype=float)*np.asarray(scale,dtype=float)
    # The lowest tip can be buried while the wider lower flank still overhangs
    # the slope. Embed the lower body, rather than proving only tip contact.
    low=points[points[:,2]<=points[:,2].min()+np.ptp(points[:,2])*.45]
    low=low[np.linspace(0,len(low)-1,min(96,len(low)),dtype=int)]
    ca,sa=math.cos(yaw),math.sin(yaw)
    xy=np.column_stack([low[:,0]*ca-low[:,1]*sa,low[:,0]*sa+low[:,1]*ca])+np.asarray(position[:2])
    heights=np.array([height(float(x),float(y)) for x,y in xy])
    target=float(np.min(heights-low[:,2])-.035*np.ptp(points[:,2]))
    z=min(float(position[2]),target)
    return z,{'support_samples':len(low),'contact_band_height_fraction':.45,'buried_support_fraction':float(np.mean(low[:,2]+z<=heights+.001)),
              'vertical_adjustment_m':z-float(position[2])}


def itinerary(field):
    named={r.get('id',str(i)):(r,p) for i,(r,p) in enumerate(field.routes)}
    walk=field.config.get('itinerary',[{'route':k} for k in named])
    result=[]
    for step in walk:
        points=named[step['route']][1]
        if step.get('reverse'):points=points[::-1]
        for p in list(points[::3])+[points[-1]]:
            if not result or np.linalg.norm(p-np.array(result[-1]))>.1:result.append(list(map(float,p)))
    return result


def clip(poly,normal,mid):
    result=[]
    for i,p in enumerate(poly):
        q=poly[(i+1)%len(poly)];dp=float(np.dot(p-mid,normal));dq=float(np.dot(q-mid,normal))
        if dp<=1e-7:result.append(p)
        if (dp<=0)!=(dq<=0):result.append(p+(q-p)*dp/(dp-dq))
    return result


def zone_material(point,default,zones):
    """Assign each physical paver to one functional zone, without overlays."""
    for zone in reversed(zones):
        poly=np.asarray(zone['outline'],dtype=float)
        turns=[np.cross(poly[(i+1)%len(poly)]-p,np.asarray(point)-p) for i,p in enumerate(poly)]
        if all(v>=-1e-7 for v in turns) or all(v<=1e-7 for v in turns):return zone['material']
    return default


def fitted_patch(api,outline,material,spacing=.66,coverage=1.,wear=.3,edge_fade=0.,fade_edges=None,material_zones=None):
    """Clipped cellular stone, buried and individually fitted to actual ground."""
    rng=api['rng'];outline=np.array(outline,dtype=float)
    # Counter-clockwise convex outlines keep adjacent pavers inside the footprint.
    area=sum(np.cross(outline[(i+1)%len(outline)]-outline[i],outline[(i+2)%len(outline)]-outline[(i+1)%len(outline)]) for i in range(len(outline)))
    if area<0:outline=outline[::-1]
    lo=outline.min(0);hi=outline.max(0);seeds=[]
    for y in np.arange(lo[1]-spacing,hi[1]+spacing,spacing):
        for x in np.arange(lo[0]-spacing,hi[0]+spacing,spacing):
            seeds.append([x+rng.uniform(-.31,.31)*spacing,y+rng.uniform(-.31,.31)*spacing])
    seeds=np.array(seeds);count=0
    for i,seed in enumerate(seeds):
        if rng.random()>coverage:continue
        if any(np.cross(outline[(j+1)%len(outline)]-p,seed-p)<-.2*spacing for j,p in enumerate(outline)):continue
        if edge_fade:
            edges=range(len(outline)) if fade_edges is None else fade_edges
            distance=min(abs(float(np.cross(outline[(j+1)%len(outline)]-outline[j],seed-outline[j])))/max(.001,float(np.linalg.norm(outline[(j+1)%len(outline)]-outline[j]))) for j in edges)
            # Fade only the two shoulders of a path, never the joins between
            # construction patches. Courts fade around their complete perimeter.
            t=max(0,min(1,distance/edge_fade));probability=.12+.88*t*t*(3-2*t)
            if rng.random()>probability:continue
        poly=[p.copy() for p in outline]
        for k in np.argsort(((seeds-seed)**2).sum(1))[1:18]:
            poly=clip(poly,seeds[k]-seed,(seeds[k]+seed)*.5)
            if len(poly)<3:break
        if len(poly)<3:continue
        center=np.mean(poly,axis=0);gap=rng.uniform(.965,.986)
        poly=[center+(p-center)*gap for p in poly];N=len(poly)
        # A stone has a planar crown. Smooth interpolation around its vertical
        # sides can make a 2 cm proud paver look like a buckled plate in UE.
        fit=np.array([[p[0]-center[0],p[1]-center[1],1] for p in poly])
        plane=np.linalg.lstsq(fit,np.array([api['height'](*p) for p in poly]),rcond=None)[0]
        heights=fit@plane+.022
        verts=[(float(p[0]),float(p[1]),h-.16) for p,h in zip(poly,heights)]+[(float(p[0]),float(p[1]),h) for p,h in zip(poly,heights)]
        verts.append((float(center[0]),float(center[1]),float(plane[2]+.022)))
        faces=[tuple(range(N-1,-1,-1))]+[(N+j,N+(j+1)%N,2*N) for j in range(N)]+[(j,(j+1)%N,(j+1)%N+N,j+N) for j in range(N)]
        value=rng.uniform(.78,1.06);moss=wear*rng.uniform(.12,.8)
        colors=[(value,moss,0,1)]*(2*N+1)
        chosen=zone_material(center,material,material_zones or [])
        api['finish_stone'](api['mesh']('Embedded paving',verts,faces,chosen,colors=colors,smooth_faces=False),.012);count+=1
    return count


def footprint(place):
    if 'outline' in place:return place['outline']
    x,y,_=place['center'];r=place['radius']
    return [[x+math.cos(a)*r,y+math.sin(a)*r] for a in np.linspace(0,math.tau,24,endpoint=False)]


def terrain_mask(field,x,y,rock,moss,wet):
    """Wear lives in the terrain vertices, avoiding floating decal ribbons."""
    d,z,w,ri=field.query(x,y)
    if ri<0:return rock,moss,wet
    route=field.routes[ri][0];style=route.get('surface','stone')
    if style=='authored':return rock,moss,wet
    edge=w*.5*(.91+.07*math.sin(x*.9+y*.6)+.04*math.sin(y*1.9-x*.4))
    weight=max(0,min(1,(edge+.65-d)/.85));weight=weight*weight*(3-2*weight)
    if style=='earth':target=(.10,.018,.25)
    elif style=='broken':target=(.31,.06,.15)
    else:target=(.22,.035,.12)
    target=route.get('terrain_weights',target)
    if route.get('wheel_ruts'):
        from cart_tracks import profile
        strength,_=profile(route,d)
        target=(target[0],target[1],target[2]*strength)
    return tuple(a*(1-weight)+b*weight for a,b in zip((rock,moss,wet),target))


def wall_segments(api):
    field=api['route_field']
    for wall in field.config.get('walls',[]):
        total_length=sum(math.dist(a[:2],b[:2]) for a,b in zip(wall['points'],wall['points'][1:]))
        walked=0.
        for a,b in zip(wall['points'],wall['points'][1:]):
            a=np.array(a[:2]);b=np.array(b[:2]);d=b-a;length=float(np.linalg.norm(d));n=max(1,math.ceil(length/.85));yaw=math.atan2(d[1],d[0])
            for i in range(n):
                p=a+d*((i+.5)/n)
                if wall.get('enclosure',False):
                    distance,_,width=field.nearest(*p)
                    if distance<width*.5+.8:continue
                elif field.clear(*p,.8):continue
                old_base=api['height'](*p)-.12;h=wall.get('height',.9)
                if wall.get('taper_gap_m'):
                    distance,_,width=field.nearest(*p)
                    t=max(0,min(1,(distance-width*.5-.8)/wall['taper_gap_m']))
                    h*=t*t*(3-2*t)
                if wall.get('taper_end_m'):
                    along=walked+length*(i+.5)/n
                    t=max(0.,min(1.,min(along,total_length-along)/wall['taper_end_m']))
                    h*=t*t*(3-2*t)
                if h<.045:continue
                # Broad, authored damage along a run, not random floating blocks.
                h*=1-.35*max(0,math.sin(i*.63+wall.get('phase',0))) if wall.get('broken') else 1
                base=min(old_base,footing_bottom(api['height'],p,(length/n+.08,wall.get('thickness',.56)+.16),yaw))
                h+=old_base-base  # Keep the authored crown; extend only the foundation.
                yield wall,p,base,h,length/n,yaw
            walked+=length


def paving_strips(points,widths):
    """Share the exact cross-section at construction joins, including bends."""
    sides=[]
    for i,p in enumerate(points):
        tangent=points[min(i+1,len(points)-1)][:2]-points[max(0,i-1)][:2]
        tangent=tangent/max(.001,np.linalg.norm(tangent))
        sides.append(np.array([-tangent[1],tangent[0]])*widths[i]*.5)
    for start in range(0,len(points)-1,3):
        end=min(start+3,len(points)-1);a,b=points[start],points[end]
        yield start,a,b,[a[:2]-sides[start],b[:2]-sides[end],b[:2]+sides[end],a[:2]+sides[start]]


def build_paving(api):
    field=api['route_field'];cfg=field.config;count=0
    if cfg.get('paving_style')=='modular':
        from modular_paving import routes
        return routes(api)
    from surface_bedding import build as bedding
    bedding(api)
    for ri,(route,points) in enumerate(field.routes):
        style=route.get('surface','stone');widths=field.route_widths[ri]
        paving_api=api
        if route.get('raised_surface',False):
            paving_api=dict(api)
            paving_api['height']=lambda x,y,rid=route['id']:max(api['height'](x,y),field.query(x,y,[rid])[1])
        # Keep a legible connected spine; wear occurs at the shoulders. Earth
        # paths use the terrain itself, without scattered decorative slab stamps.
        density={'stone':.995,'broken':.98,'earth':0.,'authored':0.}[style]
        if not density:continue
        for start,a,b,outline in paving_strips(points,widths):
            if any(np.linalg.norm(((a+b)*.5-p['center'])[:2])<p['radius']*.88 and p.get('surface','stone')!='none' for p in cfg.get('places',[])):continue
            count+=fitted_patch(paving_api,outline,route.get('material',cfg['paving_material']),route.get('stone_spacing',.65),density,.58 if style!='stone' else .24,route.get('edge_fade_m',.55),[0,2])
    for p in cfg.get('places',[]):
        if p.get('surface','stone')!='none':count+=fitted_patch(api,footprint(p),p.get('material',cfg['paving_material']),p.get('stone_spacing',.72),p.get('coverage',.94),.35,p.get('edge_fade_m',.65),material_zones=p.get('material_zones',[]))
    return count


def build(api):
    field=api['route_field'];cfg=field.config;rng=api['rng'];count=build_paving(api)
    for p in cfg.get('places',[]):
        if p.get('well'):
            x,y=p['well'];z=api['height'](x,y)
            for row in range(3):
                for i in range(16):
                    a=i*math.tau/16+(row%2)*.1
                    api['wedge'](x,y,z+.14+row*.24,.68,1.12,a+.007,a+math.tau/16-.007,.23,cfg['wall_material'])
            api['cylinder']((x,y,z+.03),.70,.12,api['spec']['floor_material'])
    for w,p,z,h,length,yaw in wall_segments(api):
        rows=max(1,round(h/.29));thickness=w.get('thickness',.56);material=w.get('material',cfg['wall_material'])
        for row in range(rows):api['block']((p[0],p[1],z+(row+.5)*h/rows),(length-.015,thickness,h/rows-.012),material,yaw,.015)
        api['block']((p[0],p[1],z+h+.045),(length-.014,thickness+.08,.10),material,yaw,.012)
    # Irregular regions define separate ecological compositions. No repeated
    # rock/fern pair at a fixed distance along both sides of every road.
    placements={}
    occupied=[o['position'][:2] for o in api['spec'].get('objects',[]) if o.get('kind')=='asset' and o.get('collision',True)]
    for region in cfg.get('planting_regions',[]):
        if 'authored_points' in region:
            from authored_planting import build as build_authored_planting
            asset=region['palette'][0]['asset']
            placements[asset]=placements.get(asset,0)+build_authored_planting(region,api)
            continue
        cx,cy=region['center'];rx,ry=region['radii'];assets=region['palette'];placed=0
        yaw=math.radians(region.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
        for trial in range(region['count']*9):
            u,v=rng.uniform(-rx,rx),rng.uniform(-ry,ry);x=cx+u*ca-v*sa;y=cy+u*sa+v*ca
            radius=(u/rx)**2+(v/ry)**2
            if radius>1:continue
            if api['n'](x,y,.3,region.get('noise_seed',7))<region.get('patch_threshold',-.35):continue
            chosen=rng.choices(assets,weights=[s.get('weight',1) for s in assets])[0]
            size=rng.uniform(*chosen.get('size',[.4,.9]));asset=chosen['asset']
            margin=max(region.get('route_margin',-.12),size*.7 if chosen.get('collision') else -.12)
            if field.clear(x,y,margin):continue
            spacing=region.get('minimum_spacing_m',0)
            if spacing and any(math.hypot(x-p[0],y-p[1])<spacing for p in occupied):continue
            api['instance'](asset,(x,y,api['height'](x,y)-chosen.get('embed_m',.025)),(size,size,size*chosen.get('height_ratio',1)),rng.uniform(0,math.tau),trial,chosen.get('collision',False),choose_palette=False,ground=chosen.get('grounding',False))
            if chosen.get('collision',False):occupied.append((x,y))
            placements[asset]=placements.get(asset,0)+1;placed+=1
            if placed>=region['count']:break
    for group in cfg.get('rock_clusters',[]):
        cx,cy=group['center'];rx,ry=group['radii'];assets=group['assets'];placed=0
        for trial in range(group.get('count',5)*15):
            x=cx+rng.uniform(-rx,rx);y=cy+rng.uniform(-ry,ry);size=rng.uniform(*group.get('size',[.6,2.]))
            if ((x-cx)/rx)**2+((y-cy)/ry)**2>1 or field.clear(x,y,size*.75):continue
            h=size*rng.uniform(.36,.7);asset=rng.choice(assets)
            api['instance'](asset,(x,y,api['height'](x,y)-h*.28),(size,size*rng.uniform(.7,1.1),h),rng.uniform(0,math.tau),trial,True,ground=True)
            placements[asset]=placements.get(asset,0)+1;placed+=1
            if placed>=group.get('count',5):break
    grade=max(abs(d[2])/max(.01,np.linalg.norm(d[:2])) for d in field.d)
    if grade>.30:raise ValueError('Walking route exceeds 30 percent grade')
    return {'route_length_m':float(sum(np.sqrt(field.lengths))),'paving_slabs':count,'max_grade':float(grade),'waypoints_m':itinerary(field),
            'places':cfg['places'],'encounter_radius_m':cfg.get('encounter_radius_m',12),'play_bounds':cfg['play_bounds'],
            'composition_version':2,'surface_types':sorted({r.get('surface','stone') for r,p in field.routes}),
            'route_edges':len(field.routes),'regional_scan_counts':placements,'planting_regions':len(cfg.get('planting_regions',[]))}


def whitebox(api,helpers):
    field=api['route_field'];mesh=helpers['mesh'];wedge=helpers['wedge']
    exclusions=field.config.get('paving_exclusions',[])
    from modular_paving import uncovered
    for ri,(route,points) in enumerate(field.routes):
        if route.get('surface') in ['earth','authored']:continue # Terrain or independently authored deck owns support.
        if exclusions:
            for _,a,b,outline in paving_strips(points,field.route_widths[ri]):
                for poly in uncovered(outline,exclusions):
                    vs=[]
                    for x,y in poly:
                        z=api['height'](x,y)
                        if route.get('raised_surface',False):z=max(z,field.query(x,y,[route['id']])[1])
                        vs.append((float(x),float(y),z+.035))
                    mesh('owned route surface',vs,[tuple(range(len(vs)))])
            continue
        verts=[]
        for i,p in enumerate(points):
            delta=points[min(len(points)-1,i+1)]-points[max(0,i-1)]
            side=np.array([-delta[1],delta[0],0]);side/=max(.001,np.linalg.norm(side))
            for sign in [-1,1]:
                q=p+side*sign*field.route_widths[ri][i]*.5
                z=api['height'](*q[:2])
                if route.get('raised_surface',False):z=max(z,q[2])
                verts.append((q[0],q[1],z+.035))
        mesh('fitted route',verts,[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(points)-1)])
    for p in field.config.get('places',[]):
        if p.get('surface','stone')!='none':
            for outline in uncovered(footprint(p),exclusions):
                verts=[(x,y,api['height'](x,y)+.035) for x,y in outline];mesh('landmark pavement',verts,[tuple(range(len(verts)))])
        if p.get('well'):
            x,y=p['well'];wedge('well',x,y,api['height'](x,y)+.38,.68,1.12,0,math.tau,.74)
    for w,p,z,h,length,yaw in wall_segments(api):
        ca,sa=math.cos(yaw),math.sin(yaw);d=w.get('thickness',.56)+.08
        vs=[(p[0]+x*ca-y*sa,p[1]+x*sa+y*ca,zz) for zz in [z,z+h+.095] for x,y in [(-length/2,-d/2),(length/2,-d/2),(length/2,d/2),(-length/2,d/2)]]
        mesh('garden wall',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
