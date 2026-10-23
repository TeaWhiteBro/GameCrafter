"""Continuous terrain and compositional modules driven by the scene contract.

Library geometry, surface layers, architecture and planting are independent inputs.
No existing level or character asset is required by this builder.
"""
import bpy,bmesh,json,math,random,sys,traceback
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix,noise
sys.path.insert(0,str(Path(__file__).resolve().parent))

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
data=json.loads(Path(job['scene_spec']).read_text());spec=data['scene'];cfg=spec['composition']
rng=random.Random(job.get('seed',417));groups={};report={'ok':False,'environment':[]};materials=dict(spec['materials'])
bpy.ops.wm.read_factory_settings(use_empty=True)

def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def n(x,y,s=.2,z=1):return noise.noise_vector(Vector((x*s,y*s,z)))[0]
center=cfg.get('court_center',[0,0]);rx,ry=cfg.get('court_radii',[7,8])
height_field=None
shape=cfg.get('terrain_shape',{})
if shape.get('height_texture_set'):
    image=bpy.data.images.load(job['texture_library'][shape['height_texture_set']]['height'],check_existing=True)
    image.colorspace_settings.name='Non-Color'
    height_field=np.asarray(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)[:,:,0]
    low,high=np.percentile(height_field,[1,99]);height_field=np.clip((height_field-low)/max(.001,high-low),0,1)
def relief(x,y):
    if height_field is None:return 0.
    scale=cfg['terrain_shape'].get('height_scale_m',16);hh,ww=height_field.shape
    u=(x/scale%1)*(ww-1);v=(y/scale%1)*(hh-1);i,j=int(u),int(v);a,b=u-i,v-j
    return float((height_field[j,i]*(1-a)+height_field[j,i+1]*a)*(1-b)+(height_field[j+1,i]*(1-a)+height_field[j+1,i+1]*a)*b)-.5
def court(x,y):return math.sqrt(((x-center[0])/rx)**2+((y-center[1])/ry)**2)
def base_height(x,y):
    shape=cfg.get('terrain_shape')
    if shape:
        sx,sy=shape['shelf_radii'];ox,oy=shape.get('shelf_center',[0,0])
        r=math.sqrt(((x-ox)/sx)**2+((y-oy)/sy)**2)
        contour=r+.042*n(x,y,.33,7)+.028*n(x,y,.77,3)
        fall=smooth(.86,1.40,contour)
        # A continuous eroded shelf and cliff face, not a bowl of level soil.
        z=.08-shape['cliff_drop']*fall
        z+=fall*(.85*n(x,y,.32,8)+.25*n(x,y,.94,5))
        z+=smooth(.62,.95,r)*(1-fall)*(.21+.34*n(x,y,.38,4))
        for ridge in shape.get('ridges',[]):
            dx=(x-ridge['center'][0])/ridge['radii'][0];dy=(y-ridge['center'][1])/ridge['radii'][1]
            q=max(0,1-math.sqrt(dx*dx+dy*dy))
            if q<=0:continue
            coarse,fine=ridge.get('noise_amplitude',[.28,.12])
            z+=ridge['height']*q**1.2*(.78+coarse*n(x,y,.20,2)+fine*n(x,y,.58,8))
        z+=shape.get('relief_amplitude',2.4)*relief(x,y)*smooth(.82,1.12,r)
        return z
    r=court(x,y);fade=smooth(.94,1.65,r)
    distance=math.hypot(x-center[0],y-center[1]);rise=max(0,distance-9)
    bank=cfg.get('bank_strength',1.)*(.16*rise**1.26+.50*n(x,y,.15,8))
    ridge=cfg.get('ridge_strength',2.8)*math.exp(-((y+19)/7)**2)*smooth(9,15,distance)
    z=.07+fade*(.18+bank+ridge+.16*n(x,y,.38,4)+.035*n(x,y,1.1,1))+.018*n(x,y,.8,2)
    if cfg.get('terrace'):
        approach=(1-smooth(3.2,5.4,abs(x-center[0])))*smooth(5,9,y-center[1])
        z=z*(1-approach)+(.08+.012*n(x,y,.6))*approach
    return z

from exploration import RouteField
from functools import lru_cache
route_field=RouteField(cfg.get('exploration',{}))
from surface_deposits import validate as validate_deposits
from terrain_modifiers import apply as apply_terrain_modifiers
validate_deposits(cfg.get('surface_deposits',[]))
@lru_cache(maxsize=550000)
def height(x,y):
    base=base_height(x,y)+cfg.get('terrain_base_z',0)
    result=route_field.height(x,y,base) if cfg.get('exploration') and cfg.get('terrain_conform_to_routes',True) else base
    return apply_terrain_modifiers(cfg,route_field,x,y,result)

def mesh(name,verts,faces,mat,collision=True,colors=None,smooth_faces=True,preserve_winding=False):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    if name!='Continuous terrain' and not preserve_winding:
        bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
    for face in me.polygons:face.use_smooth=smooth_faces
    if colors:
        attr=me.color_attributes.new(name='SurfaceWeights',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',np.asarray(colors,dtype=np.float32).ravel())
    groups.setdefault((mat,collision),[]).append(ob)
    return ob

def finish_stone(ob,width=.025):
    # Defer modifier evaluation until batching. Thousands of per-object modifier
    # applications repeatedly rebuild Blender's dependency graph and take minutes.
    ob['edge_finish']=width
    return ob

def block(pos,dim,mat,yaw=0,bevel=.025):
    x,y,z=dim;pts=[(-.5,-.40),(-.40,-.5),(.40,-.5),(.5,-.40),(.5,.40),(.40,.5),(-.40,.5),(-.5,.40)]
    verts=[];ca,sa=math.cos(yaw),math.sin(yaw);jitter=min(x,y)*.018
    shifts=[(rng.uniform(-jitter,jitter),rng.uniform(-jitter,jitter)) for p in pts]
    for zz in [-z/2,z/2]:
        for i,(a,b) in enumerate(pts):
            xx=a*x+shifts[i][0];yy=b*y+shifts[i][1];verts.append((pos[0]+xx*ca-yy*sa,pos[1]+xx*sa+yy*ca,pos[2]+zz))
    faces=[tuple(range(7,-1,-1)),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
    value=rng.uniform(.83,1.13);moss=rng.uniform(.05,.5) if pos[2]<cfg.get('terrace',{}).get('height',0)+.6 or rng.random()<.06 else 0
    ob=mesh('Masonry',verts,faces,mat,colors=[(value,moss,.0,1)]*16)
    return finish_stone(ob,bevel) if bevel else ob

def wedge(cx,cy,z,r0,r1,a0,a1,depth,mat):
    count=max(2,int((a1-a0)*r1/.20));verts=[]
    for zz in [z-depth/2,z+depth/2]:
        for rad in [r0,r1]:
            for i in range(count+1):
                a=a0+(a1-a0)*i/count;verts.append((cx+math.cos(a)*rad,cy+math.sin(a)*rad,zz))
    nn=count+1;faces=[]
    for i in range(count):
        faces.extend([(i,i+1,nn+i+1,nn+i),(2*nn+i,3*nn+i,3*nn+i+1,2*nn+i+1),
         (i,2*nn+i,2*nn+i+1,i+1),(nn+i,nn+i+1,3*nn+i+1,3*nn+i)])
    faces.extend([(0,nn,3*nn,2*nn),(count,2*nn+count,3*nn+count,nn+count)])
    moss=rng.uniform(.04,.48) if z<cfg.get('terrace',{}).get('height',0)+.5 else rng.uniform(0,.08)
    ob=mesh('Radial masonry',verts,faces,mat,colors=[(rng.uniform(.88,1.07),moss,0,1)]*len(verts))
    return finish_stone(ob,.018)

def cylinder(pos,radius,depth,mat,vertices=40):
    verts=[(pos[0]+math.cos(i*math.tau/vertices)*radius,pos[1]+math.sin(i*math.tau/vertices)*radius,pos[2]+z) for z in [-depth/2,depth/2] for i in range(vertices)]
    faces=[tuple(range(vertices-1,-1,-1)),tuple(range(vertices,vertices*2))]+[(i,(i+1)%vertices,(i+1)%vertices+vertices,i+vertices) for i in range(vertices)]
    return finish_stone(mesh('Moulding',verts,faces,mat),min(.025,depth*.15))

def arch(position,width,depth,total_height,mat,yaw=0,broken=False,thickness=.48):
    from arch_profiles import parameters,ordinate
    before={o for items in groups.values() for o in items};r=width/2;thick=thickness
    profile=cfg.get('arch_profile','round');spring,rise=parameters(r,total_height,profile)
    for sign in [-1,1]:
        for row in range(max(1,int(spring/.40))):
            rows=max(1,int(spring/.40));hh=spring/rows
            block((sign*(r-thick*.5),0,hh*(row+.5)),(thick,depth,hh-.012),mat,bevel=.03)
        for z in [.13,spring-.07]:block((sign*(r-thick*.5),0,z),(thick+.20,depth+.15,.22),mat,bevel=.027)
    for i in range(23):
        if broken and i in [9,10,11,12]:continue
        a0=i*math.pi/23+.003;a1=(i+1)*math.pi/23-.003
        vs=[(math.cos(a)*rad,yy,spring+ordinate(a,rad,r,rise,profile)) for yy in [-depth/2,depth/2] for rad in [r-thick,r] for a in [a0,a1]]
        ob=mesh('Arch voussoir',vs,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)],mat);finish_stone(ob,.024)
    m=Matrix.Translation(Vector(position))@Matrix.Rotation(yaw,4,'Z')
    for items in groups.values():
        for ob in items:
            if ob not in before:ob.matrix_world=m@ob.matrix_world

def ring(pos,radius,tube,mat,rotation=(0,0,0),arc=(0,math.tau)):
    seg=max(32,int(radius*80));verts=[];faces=[];rot=Matrix.Rotation(rotation[2],4,'Z')@Matrix.Rotation(rotation[1],4,'Y')@Matrix.Rotation(rotation[0],4,'X')
    for i in range(seg+1):
        a=arc[0]+(arc[1]-arc[0])*i/seg
        for j in range(10):
            b=j*math.tau/10;p=Vector(((radius+math.cos(b)*tube)*math.cos(a),(radius+math.cos(b)*tube)*math.sin(a),math.sin(b)*tube));verts.append(rot@p+Vector(pos))
    for i in range(seg):
        for j in range(10):faces.append((i*10+j,i*10+(j+1)%10,(i+1)*10+(j+1)%10,(i+1)*10+j))
    return mesh('Instrument ring',verts,faces,mat)

templates={}
def library(asset):
    if asset in templates:return templates[asset]
    conf=job['mesh_library'][asset];before=set(bpy.data.objects);path=Path(conf['file'])
    if path.suffix.lower() in ['.gltf','.glb']:bpy.ops.import_scene.gltf(filepath=str(path))
    else:bpy.ops.import_scene.fbx(filepath=str(path))
    imported=[ob for ob in bpy.data.objects if ob not in before and ob.type=='MESH'];sources=[]
    if conf.get('variant_mode')=='assembled' and len(imported)>1:
        bpy.ops.object.select_all(action='DESELECT')
        for ob in imported:ob.select_set(True)
        bpy.context.view_layer.objects.active=imported[0];bpy.ops.object.join();imported=[bpy.context.object]
    for ob in imported:
        bpy.context.view_layer.objects.active=ob;ob.select_set(True)
        triangles=sum(len(p.vertices)-2 for p in ob.data.polygons);budget=conf.get('triangle_budget',14000)
        if triangles>budget:
            m=ob.modifiers.new('Scan budget','DECIMATE');m.ratio=budget/triangles;bpy.ops.object.modifier_apply(modifier=m.name)
        m=ob.matrix_world.copy();coords=np.array([m@v.co for v in ob.data.vertices]);lo=coords.min(0);hi=coords.max(0);dims=np.maximum(hi-lo,.001)
        # Mesh templates are normalized once; copies retain their photographed UVs.
        origin=Vector(((hi[0]+lo[0])/2,(hi[1]+lo[1])/2,lo[2]))
        ob.data.transform(Matrix.Diagonal(Vector((1/dims[0],1/dims[1],1/dims[2],1)))@Matrix.Translation(-origin)@m)
        ob.matrix_world=Matrix.Identity(4);ob.data.update()
        ob.data['source_dimensions']=list(map(float,dims))
        ob.data['pipeline_source_key']=asset+'#'+str(len(sources))
        sources.append(ob.data.copy());bpy.data.objects.remove(ob,do_unlink=True)
    for ob in list(bpy.data.objects):
        if ob not in before:bpy.data.objects.remove(ob,do_unlink=True)
    templates[asset]=sources
    if not sources:raise RuntimeError('Empty mesh library entry '+asset)
    from generated_parts import register
    register(conf,materials)
    for key,override in cfg.get('material_overrides',{}).items():
        if key in materials:materials[key]={**materials[key],**override}
    return sources

def instance(asset,pos,dim,yaw,variant=0,collision=True,choose_palette=True,ground=False,material_variant=None):
    if choose_palette and asset==cfg.get('scatter',{}).get('plant_asset') and cfg.get('plant_palette'):
        palette=cfg['plant_palette'];asset=rng.choices([e['asset'] for e in palette],weights=[e.get('weight',1) for e in palette])[0]
    sources=library(asset);conf=job['mesh_library'][asset];me=sources[variant%len(sources)];ob=bpy.data.objects.new(asset,me);bpy.context.collection.objects.link(ob)
    if conf.get('preserve_aspect',False):
        original=me.get('source_dimensions',[1,1,1]);factor=min(dim[i]/max(.001,original[i]) for i in range(3));dim=[v*factor for v in original]
    ob.location=pos;ob.scale=dim;ob.rotation_euler.z=yaw
    if ground:
        from landscape_routes import rock_origin,base_origin
        ob.location.z,audit=(base_origin if ground=='base' else rock_origin)([v.co[:] for v in me.vertices],pos,dim,yaw,height)
        report.setdefault('rock_grounding',[]).append({'asset':asset,'position':list(pos),'settled_z':float(ob.location.z),**audit})
    ob['whitebox_instance']=True
    from generated_parts import group_instance
    if material_variant is not None:
        from material_variants import binding
        from generated_parts import register
        conf=binding(conf,cfg.get('asset_material_variants',{}).get(asset,{}),material_variant)
        register(conf,materials)
        key=asset+'/'+material_variant
        report.setdefault('material_variant_usage',{})[key]=report.setdefault('material_variant_usage',{}).get(key,0)+1
    ob=group_instance(ob,conf,groups,collision)
    usage=report.setdefault('asset_instances',{}).setdefault(asset,{'count':0,'colliding_instances':0,'variants':[],
        'source_file':conf['file'],'material_id':conf['material_id']})
    usage['count']+=1;usage['colliding_instances']+=int(collision)
    actual_variant=variant%len(sources)
    if actual_variant not in usage['variants']:usage['variants'].append(actual_variant)
    return ob

try:
    extent=cfg.get('terrain_extent_m',100);step=cfg.get('terrain_grid_m',.45);count=int(extent/step)
    vs=[];fs=[];colors=[]
    for j in range(count+1):
        y=(j/count-.5)*extent
        for i in range(count+1):
            x=(i/count-.5)*extent;r=court(x,y);z=height(x,y)
            # Soil, bedrock and plants share geological masks across the whole ground.
            slope=math.hypot(height(x+.20,y)-height(x-.20,y),height(x,y+.20)-height(x,y-.20))/.4
            distance_bias=min(1.5,r-1) if cfg.get('exploration',{}).get('composition_version',1)>=2 else r-1
            rock=max(smooth(.03,.55,n(x,y,.18,8)+.10*distance_bias)*.8,smooth(.24,.86,slope))
            moss=smooth(-.14,.40,n(x,y,.24,2))*(.32+.68*smooth(.85,1.35,r))*.86*(1-smooth(.6,1.6,slope))
            wet=smooth(.05,.60,n(x,y,.15,6))*.62
            weights=cfg.get('terrain_material_weights',{})
            if cfg.get('terrain_rock_slope_only',False):rock=smooth(.32,.95,slope)
            rock*=weights.get('rock',1);moss*=weights.get('moss',1);wet*=weights.get('wet',1)
            from landscape_materials import weights as region_weights
            rock,moss,wet=region_weights(cfg.get('terrain_material_regions',[]),x,y,(rock,moss,wet))
            if cfg.get('exploration',{}).get('composition_version',1)>=2:
                from landscape_routes import terrain_mask
                rock,moss,wet=terrain_mask(route_field,x,y,rock,moss,wet)
            vs.append((x,y,z));colors.append((rock,moss,wet,1))
    for j in range(count):
        for i in range(count):
            k=j*(count+1)+i;fs.append((k,k+1,k+count+2,k+count+1))
    mesh('Continuous terrain',vs,fs,spec['floor_material'],colors=colors)
    if cfg.get('horizon_terrain'):
        from horizon_terrain import build as build_horizon
        build_horizon(globals())
    mat=spec['path_material']
    if cfg.get('terrace'):
        from architecture import build_terrace, build_structures
        paving_count=build_terrace(globals());build_structures(globals())
    elif cfg.get('paving_style')=='terrain':
        paving_count=0 # Continuous terrain owns this explicitly unpaved court.
    elif cfg.get('paving_style')=='modular':
        from modular_paving import court as modular_court
        paving_count=modular_court(globals())
    elif cfg.get('paving_style')=='fitted':
        from courtyard import fitted_court
        paving_count=fitted_court(globals())
    else:
        # Unequal flagstone courses disappear into earth at the edge of the court.
        mat=spec['path_material'];paving_count=0
        for row in range(-12,13):
            y=row*.76
            for col in range(-12,13):
                x=col*.98+(row%2)*.49;r=court(x,y);cut=.99+.045*n(x,y,1.2,5)
                if r>cut or (r>.78 and rng.random()<.14):continue
                top=.125+.008*n(x,y,.5,2)-.085*smooth(.79,1.04,r)
                block((x,y,top-.10),(rng.uniform(.944,.958),rng.uniform(.732,.744),.20),mat,rng.uniform(-.014,.014),.023)
                paving_count+=1
        # Broken radial foundation ties the architecture to the same paved court.
        if cfg.get('radial_border',True):
            for i in range(56):
                if 31<i<44 or rng.random()<.13:continue
                a=i*math.tau/56;wedge(center[0],center[1],.11,rx+.15,rx+.72,a+.004,a+math.tau/56-.007,.26,mat)
    if not cfg.get('terrace') and (cfg.get('structures') or cfg.get('galleries')):
        from architecture import build_structures
        build_structures(globals())
    if cfg.get('arcades') or cfg.get('apses'):
        from courtyard import build_arcades,build_apses,build_gardens
        build_arcades(globals());build_apses(globals());build_gardens(globals())
    if cfg.get('exploration'):
        from exploration import build as build_exploration
        report['exploration']=build_exploration(globals())
    if cfg.get('terrain_channels'):
        from terrain_channels import build as build_channels
        build_channels(globals())
    if cfg.get('destination_details'):
        from destination_details import build as build_destinations
        destination_result=build_destinations(globals())
        report['destination_details']=destination_result
        for planting in destination_result['plantings']:
            size=planting['size'];instance(planting['asset'],planting['position'],[size]*3,planting['yaw'],planting['variant'],False,choose_palette=False)
    for item in spec['objects']:
        pos=item['position'];dim=item['scale'];material=item.get('material');yaw=math.radians(item.get('yaw_deg',0));kind=item['kind']
        if item.get('snap_to_terrain'):pos=[pos[0],pos[1],height(pos[0],pos[1])+pos[2]]
        if kind=='arch':arch(pos,dim[0],dim[1],dim[2],material,yaw,item.get('broken',False))
        elif kind=='column':
            for zz,rr,hh in [(.12,.67,.24),(.35,.54,.18),(dim[2]/2,.40,dim[2]-.65),(dim[2]-.25,.53,.24),(dim[2]-.05,.62,.16)]:cylinder((pos[0],pos[1],pos[2]+zz),dim[0]*rr,hh,material)
        elif kind=='box':block((pos[0],pos[1],pos[2]+dim[2]/2),dim,material,yaw)
        elif kind=='stairs':
            from ground_support import stair_boxes
            for step_position,step_dimensions in stair_boxes(pos,dim,yaw,height):block(step_position,step_dimensions,material,yaw)
        elif kind=='asset':instance(item['asset'],pos,dim,yaw,item.get('variant',0),item.get('collision',True),ground=item.get('grounding') if item.get('grounding') in ('rock','footprint','base') else False,material_variant=item.get('material_variant'))
        elif kind=='arc_wall':
            radius=dim[0];a0,a1=[math.radians(x) for x in item.get('arc_degrees',[15,165])];rows=max(1,int(dim[2]/.42));segments=max(3,int((a1-a0)*radius/.85))
            for row in range(rows):
                for seg in range(segments):
                    a=a0+(a1-a0)*(seg+.5*(row%2))/segments;b=a+(a1-a0)/segments-.007
                    broken=row/rows>.58 and rng.random()<.13
                    if not broken:wedge(pos[0],pos[1],pos[2]+.42*(row+.5),radius,radius+dim[1],a+.007,b,.40,material)
        elif kind=='armillary':
            r=dim[0]*.5;z=pos[2]+dim[2]*.56
            cylinder((pos[0],pos[1],pos[2]+.30),r*.56,.6,mat)
            cylinder((pos[0],pos[1],pos[2]+.78),r*.24,.7,material)
            for rot,scale in [((0,0,0),1),((math.pi/2,.2,0),.99),((1.02,.68,.3),.97)]:ring((pos[0],pos[1],z),r*scale,.055,material,rot)
            ring((pos[0],pos[1],z),r*.44,.04,material,(math.pi/2,0,.2))
            cylinder((pos[0],pos[1],z),r*.11,.26,material)
    scatter=cfg.get('scatter',{});rock_asset=scatter.get('rock_asset');plant_asset=scatter.get('plant_asset')
    placed=[(o['position'][0],o['position'][1],max(o['scale'][:2])) for o in spec['objects'] if o['kind']=='asset' and o.get('asset')==rock_asset]
    formation_asset=scatter.get('formation_asset')
    if formation_asset:
        for i in range(scatter.get('formation_count',18)):
            a=i*math.tau/scatter.get('formation_count',18)+rng.uniform(-.09,.09)
            x=math.cos(a)*rng.uniform(11.2,15.2);y=math.sin(a)*rng.uniform(12.5,18)-2.5
            if abs(x)<4.0 and y>7:continue
            size=rng.uniform(7,12);h=rng.uniform(2,4)
            instance(formation_asset,(x,y,height(x,y)-h*.55),(size,size*rng.uniform(.72,1.05),h),a+rng.uniform(-.3,.3),i,True,ground=True)
            placed.append((x,y,size))
    if rock_asset:
        for i in range(scatter.get('rock_count',50)):
            a=rng.uniform(0,math.tau);r=rng.uniform(*scatter.get('rock_radii',[11,17]));x=math.cos(a)*r;y=math.sin(a)*r
            # Wide entrance and a clear view toward the ruin, no isolated random boulders in the duel area.
            if y<-4 and abs(x)<6:continue
            size=rng.uniform(1.2,3.4);sz=size*rng.uniform(.40,.78)
            if cfg.get('exploration') and route_field.clear(x,y,size*.6):continue
            instance(rock_asset,(x,y,height(x,y)-.42*sz),(size,size*rng.uniform(.70,1.16),sz),rng.uniform(0,math.tau),i,True,ground=True);placed.append((x,y,size))
        for i in range(scatter.get('small_rock_count',75)):
            a=rng.uniform(0,math.tau);r=rng.uniform(8.2,11.8);x=math.cos(a)*r;y=math.sin(a)*r;size=rng.uniform(.25,.95)
            if abs(x)<3.3 and y<-6:continue
            instance(rock_asset,(x,y,height(x,y)-.10),(size,size*.8,size*.5),rng.uniform(0,math.tau),i,False)
    plants=0
    if plant_asset and scatter.get('plant_count',200)>0:
        plant_extent=scatter.get('plant_extent_m',19)
        for i in range(6500):
            x=rng.uniform(-plant_extent,plant_extent);y=rng.uniform(-plant_extent,plant_extent);r=court(x,y)
            if r<1.01 or abs(x)<2 and y>7 or n(x,y,.24,2)<-.18:continue
            if cfg.get('exploration') and route_field.clear(x,y,.25):continue
            bank=min((math.hypot(x-a,y-b)-radius*.52 for a,b,radius in placed),default=50)
            if bank>2.1 and not 1.01<r<1.60:continue
            size=rng.uniform(.45,1.34)
            instance(plant_asset,(x,y,height(x,y)-.025),(size,size,size*rng.uniform(.6,.92)),rng.uniform(0,math.tau),i,False);plants+=1
            if plants>=scatter.get('plant_count',200):break
    # A lower grass layer softens transitions, with vertex masks for anchored wind.
    verts=[];faces=[];colors=[];clumps=0
    grass_extent=cfg.get('grass_extent_m',18)
    for i in range(max(2800,cfg.get('grass_clumps',550)*5) if cfg.get('grass_clumps',550)>0 else 0):
        x=rng.uniform(-grass_extent,grass_extent);y=rng.uniform(-grass_extent,grass_extent);r=court(x,y)
        if r<.99 or n(x,y,.24,2)<-.13 or abs(x)<2.5 and y<-5:continue
        if cfg.get('exploration') and route_field.clear(x,y,-.2):continue
        clumps+=1;phase=rng.random()
        for blade in range(rng.randint(12,22)):
            a=rng.uniform(0,math.tau);rr=rng.uniform(0,.25);xx=x+math.cos(a)*rr;yy=y+math.sin(a)*rr;z=height(xx,yy)-.02
            h=rng.uniform(.10,.34);w=rng.uniform(.008,.020);angle=rng.uniform(0,math.tau);wx,wy=math.cos(angle)*w,math.sin(angle)*w;lean=rng.uniform(-.12,.12);start=len(verts)
            for t,width in [(0,1),(.45,.8),(.8,.4)]:
                for sign in [-1,1]:verts.append((xx+lean*t*t+sign*wx*width,yy+sign*wy*width,z+h*t));colors.append((t,phase,.65,1))
            verts.append((xx+lean,yy,z+h));colors.append((1,phase,.65,1));faces.extend([(start,start+1,start+3,start+2),(start+2,start+3,start+5,start+4),(start+4,start+5,start+6)])
        if clumps>=cfg.get('grass_clumps',550):break
    if verts:mesh('Rooted groundcover',verts,faces,cfg['grass_material'],False,colors)
    if cfg.get('modular_architecture'):
        from modular_architecture import build as build_modules
        report['modular_architecture']=build_modules(globals())
    if cfg.get('organic_paths'):
        from organic_paths import build as build_organic_paths
        build_organic_paths(globals())
    if cfg.get('pressure_habitat'):
        from pressure_habitat import build as build_habitat
        report['pressure_habitat']=build_habitat(globals())
    from whitebox import build as build_whitebox
    missing_overrides=set(cfg.get('material_overrides',{}))-set(materials)
    if missing_overrides:raise ValueError('Unconsumed material overrides: '+str(sorted(missing_overrides)))
    bpy.context.view_layer.update()
    report['whitebox']=build_whitebox(globals())
    # Scene extent exceeds the complete camera travel envelope; a square asset edge
    # must never act as the visible world boundary.
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    from shared_geometry import extract as extract_shared,export as export_shared
    shared,report['shared_geometry']=extract_shared(groups)
    from geometry_batches import build as batch_geometry, join_objects
    export_batches,report['batching']=batch_geometry(groups,cfg.get('max_export_batch_triangles',4000000))
    for index,((material,collision),objects) in enumerate(export_batches):
        finish_widths=[ob.get('edge_finish',0) for ob in objects if ob.get('edge_finish',0)>0]
        needs_finish=bool(finish_widths)
        ob=join_objects(objects)
        if needs_finish:
            mod=ob.modifiers.new('Batch worn edges','BEVEL');mod.width=min(finish_widths);mod.segments=3;mod.limit_method='ANGLE';mod.angle_limit=.74
            bpy.ops.object.modifier_apply(modifier=mod.name)
            mod=ob.modifiers.new('Batch planar normals','WEIGHTED_NORMAL');mod.keep_sharp=True
            bpy.ops.object.modifier_apply(modifier=mod.name)
        # FBX static import reflects Blender Y. Encode the scene contract's UE world
        # coordinates explicitly, so asymmetrical geometry and spawn positions agree.
        if material==spec['floor_material'] and sum(p.normal.z for p in ob.data.polygons)<0:ob.data.flip_normals()
        ob.data.transform(Matrix.Diagonal(Vector((100,-100,100,1))));ob.data.flip_normals();ob.data.update();ob.name='Environment_'+str(index)
        path=out/f'environment_{index}.fbx';bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
        cls=materials[material].get('semantic_class')
        if not cls:cls='terrain' if material==spec['floor_material'] else 'paving' if material==spec['path_material'] else {'foliage':'vegetation','grass':'vegetation','scan':'rock','masonry':'architecture'}.get(materials[material].get('surface'),'prop')
        sid={'terrain':1,'paving':2,'architecture':3,'rock':4,'vegetation':5,'prop':6}[cls]
        report['environment'].append({'file':str(path),'material':material,'collision':collision,'semantic_id':sid,'triangles':sum(len(p.vertices)-2 for p in ob.data.polygons)})
    report['environment'].extend(export_shared(shared,out,len(report['environment']),materials))
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    report.update(ok=True,materials=materials,lighting=data['lighting'],spawns=data['spawns'],size_m=spec['size_m'],blend=str(out/'scene.blend'),
        quality={'continuous_terrain':True,'terrain_extent_m':extent,'layered_ground':materials[spec['floor_material']].get('surface')=='layered_ground','ground_material':{'id':spec['floor_material'],'surface':materials[spec['floor_material']].get('surface','constant')},'paving_blocks':paving_count,'scanned_rock_clusters':len(placed),'scanned_plants':plants,'rooted_grass_clumps':clumps})
except Exception:report['error']=traceback.format_exc();print(report['error'],flush=True)
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ENVIRONMENT_RESULT',report.get('quality',report.get('error')),flush=True)
if not report['ok']:sys.exit(1)
