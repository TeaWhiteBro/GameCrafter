"""Reject valid-looking plans whose declared visual intent would be ignored."""
import math
from .contracts import ContractError

def segment_distance(point,a,b):
    delta=[b[i]-a[i] for i in range(2)];den=sum(v*v for v in delta)
    t=max(0,min(1,sum((point[i]-a[i])*delta[i] for i in range(2))/den)) if den else 0
    return math.dist(point,[a[i]+t*delta[i] for i in range(2)])

def grounded_prop_conflicts(scene):
    """Cheap authored-layout guard before expensive exact saved-mesh checks.

    Only ground-set solid scan footprints are covered. Rock silhouettes and
    openings require the downstream actual-mesh BVH and runtime walks.
    """
    result=[]
    for obj in scene.get('objects',[]):
        if obj.get('kind')!='asset' or obj.get('grounding') not in ('footprint','base') or not obj.get('snap_to_terrain'):continue
        x,y,_=obj['position'];w,d,h=obj['scale'];yaw=math.radians(obj.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
        for route in scene.get('composition',{}).get('exploration',{}).get('routes',[]):
            conflict=False
            for a,b in zip(route['points'],route['points'][1:]):
                count=max(1,math.ceil(math.dist(a[:2],b[:2])/.35))
                for i in range(count+1):
                    t=i/count;dx=a[0]+t*(b[0]-a[0])-x;dy=a[1]+t*(b[1]-a[1])-y
                    local_x=dx*ca+dy*sa;local_y=-dx*sa+dy*ca
                    # Require clearance for a body on the actual walking line.
                    distance=math.hypot(max(0,abs(local_x)-w/2),max(0,abs(local_y)-d/2))
                    if distance<.45:conflict=True;break
                if conflict:break
            if conflict:result.append('Grounded solid prop '+str(obj.get('asset'))+' at '+str(obj['position'])+' blocks route '+str(route.get('id'))+' walking line. Move the whole prop clear before building; final mesh/route QA remains required.')
    return result

def validate(data):
    scene=data['scene'];errors=[];materials=scene['materials'];cfg=scene.get('composition',{});ex=cfg.get('exploration',{})
    if cfg.get('surface_deposits'):
        from adapters.blender.surface_deposits import validate as validate_deposits
        validate_deposits(cfg['surface_deposits'])
    errors.extend(grounded_prop_conflicts(scene))
    base=cfg.get('court_base_z',0)
    batch_limit=cfg.get('max_export_batch_triangles',4000000)
    if type(batch_limit) is not int or not 10000<=batch_limit<=8000000:errors.append('max_export_batch_triangles must be an integer in 10,000-8,000,000')
    for owner in [cfg,ex]+ex.get('routes',[])+ex.get('places',[]):
        if 'paver_size' in owner:
            size=owner['paver_size']
            if not isinstance(size,list) or len(size)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not .2<=v<=3 for v in size):errors.append('paver_size requires two finite dimensions in 0.2-3 metres')
    if cfg.get('paving_style')=='modular' and cfg.get('terrace'):errors.append('Modular court and circular raised terrace are different floor systems; choose one')
    if cfg.get('paving_style')=='terrain' and cfg.get('terrace'):errors.append('Natural terrain court cannot also declare a raised paved terrace')
    if 'court_outline' in cfg:
        if cfg.get('paving_style')!='modular':errors.append('court_outline requires modular paving')
        try:
            from adapters.blender.court_outline import outline
            outline(cfg)
        except ValueError as exc:errors.append(str(exc))
    for item in cfg.get('destination_details',[]):
        embed=item.get('plant_embed_m',0)
        if type(embed) not in (int,float) or not math.isfinite(embed) or not 0<=embed<=.5:errors.append('plant_embed_m must be a finite value in 0-0.5m')
    for region in ex.get('planting_regions',[]):
        for item in region.get('palette',[]):
            embed=item.get('embed_m',.025)
            if type(embed) not in (int,float) or not math.isfinite(embed) or not 0<=embed<=.5:errors.append('Plant embed_m must be a finite value in 0-0.5m')
    for key,value in cfg.get('terrain_material_weights',{}).items():
        if key not in ('rock','moss','wet') or type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:errors.append('terrain_material_weights needs rock/moss/wet values in 0-1')
    if type(base) not in (int,float) or not math.isfinite(base):errors.append('court_base_z must be a finite metre elevation')
    for route in ex.get('routes',[]):
        weights=route.get('terrain_weights',[0,0,0])
        if not isinstance(weights,list) or len(weights)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in weights):errors.append('terrain_weights must contain three values in 0-1')
    for module in cfg.get('modular_architecture',[]):
        if module['kind'] not in ('capped_wall','street_frontage'):continue
        cx,cy=module['center'];w,d=module['size'];angle=math.radians(module.get('yaw_deg',0));ca,sa=math.cos(angle),math.sin(angle)
        for route in ex.get('routes',[]):
            blocked=False
            for a,b in zip(route['points'],route['points'][1:]):
                count=max(1,math.ceil(math.dist(a[:2],b[:2])/.3))
                for i in range(count+1):
                    t=i/count;x=a[0]+(b[0]-a[0])*t-cx;y=a[1]+(b[1]-a[1])*t-cy;z=a[2]+(b[2]-a[2])*t
                    dx=x*ca+y*sa;dy=-x*sa+y*ca
                    if module.get('base_z',.14)+module.get('height',3.5)>z+.45 and math.hypot(max(0,abs(dx)-w/2),max(0,abs(dy)-d/2))<.45:
                        blocked=True;break
                if blocked:break
            if blocked:errors.append('Solid modular '+module['kind']+' at '+str(module['center'])+' blocks route '+route['id']+'. Move the complete module; retain exact geometry and runtime checks.')
    for ridge in cfg.get('terrain_shape',{}).get('ridges',[]):
        noise=ridge.get('noise_amplitude',[.28,.12])
        if not isinstance(noise,list) or len(noise)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=.5 for v in noise):
            errors.append('Ridge noise_amplitude must be two finite values within 0-0.5')
    for name,mat in materials.items():
        if 'wetness_zones' in mat:
            from adapters.unreal.surface_wetness import validate as validate_wetness_zones
            try:
                if mat.get('surface')!='pbr':raise ValueError('wetness_zones requires pbr')
                validate_wetness_zones(mat['wetness_zones'])
            except ValueError as exc:errors.append(name+': '+str(exc))
        for key,lo,hi in [('wetness',0,1),('wetness_scale_m',.2,20)]:
            if key in mat:
                value=mat[key]
                if mat.get('surface')!='pbr' or type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
                    errors.append(name+': '+key+' requires pbr and a finite value in '+str((lo,hi)))
        if 'paint_color' in mat:
            color=mat['paint_color'];detail=mat.get('paint_detail',.16)
            if mat.get('surface')!='pbr' or not isinstance(color,list) or len(color)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in color):errors.append(name+': paint_color needs a pbr surface and linear RGB in 0-1')
            if type(detail) not in (int,float) or not math.isfinite(detail) or not 0<=detail<=1:errors.append(name+': paint_detail must be in 0-1')
        if mat.get('surface') in ('metal','grass') and mat.get('texture_set'):
            errors.append(name+': procedural '+mat['surface']+' ignores texture_set. Use surface pbr for a photographed metal, or clear the unused texture_set.')
    for role,key in [('terrain','floor_material'),('paving','path_material')]:
        name=scene[key]
        if materials[name].get('semantic_class')!=role:errors.append(name+': '+key+' requires semantic_class '+role+'; create separate material IDs for architecture and paving even if they share a scan.')
    if ex:
        names={ex['paving_material']}|{r.get('material',ex['paving_material']) for r in ex['routes']}
        for name in names:
            if materials[name].get('semantic_class')!='paving':errors.append(name+': route paving must carry semantic_class paving')
    for detail in cfg.get('destination_details',[]):
        if detail['kind'] not in ('bell_tower','vault_liner'):continue
        for route in ex.get('routes',[]):
            for a,b in zip(route['points'],route['points'][1:]):
                if detail['kind']=='bell_tower':
                    clearance=detail.get('width',3.4)*math.sqrt(2)/2+max(route.get('width_profile',[route['width']]))/2+.4
                    if segment_distance(detail['center'],a,b)<clearance and max(a[2],b[2])<detail.get('base_z',0)+detail.get('height',8.7):
                        errors.append('Solid bell_tower at '+str(detail['center'])+' overlaps route '+route['id']+'. Offset the tower beside the arrival court and reserve the full corridor.');break
                elif segment_distance(detail['center'],a,b)<detail['radius'] and detail.get('base_z',0)<max(a[2],b[2])+2.5:
                    errors.append('vault_liner at '+str(detail['center'])+' begins at walking height on route '+route['id']+'. Place roof base above 2.5m head clearance; do not use a dome liner as a building.');break
    if errors:raise ContractError('Scene intent errors:\n'+'\n'.join(dict.fromkeys(errors)))
    return data
