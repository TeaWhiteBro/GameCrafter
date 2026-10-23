"""Structural companion geometry, authored from the same metric layout as RGB.

Never whiten the render mesh. Terrain is resampled, paving is a continuous slab,
arcades retain open bays, and roofs/walls are coarse envelopes without courses.
Scan props use per-instance convex envelopes; small vegetation is omitted.
"""
import math, json, hashlib
from pathlib import Path
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def build(api):
    cfg=api['cfg'];spec=api['spec'];out=api['out'];height=api['height'];parts=[];portals=[]
    def mesh(name,vs,fs):
        me=bpy.data.meshes.new('WB_'+name);me.from_pydata(vs,[],fs);me.update()
        bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
        ob=bpy.data.objects.new('WB_'+name,me);bpy.context.collection.objects.link(ob);parts.append(ob);return ob
    def box(name,p,d,yaw=0):
        ca,sa=math.cos(yaw),math.sin(yaw)
        return mesh(name,[(p[0]+x*ca-y*sa,p[1]+x*sa+y*ca,p[2]+z) for z in [-d[2]/2,d[2]/2] for x,y in [(-d[0]/2,-d[1]/2),(d[0]/2,-d[1]/2),(d[0]/2,d[1]/2),(-d[0]/2,d[1]/2)]],FACES)
    def wedge(name,cx,cy,z,r0,r1,a0,a1,thickness,n=24):
        for k in range(n):
            aa=a0+(a1-a0)*k/n;bb=a0+(a1-a0)*(k+1)/n
            mesh(name,[(cx+r*math.cos(a),cy+r*math.sin(a),zz) for zz in [z-thickness/2,z+thickness/2] for r,a in [(r0,aa),(r1,aa),(r1,bb),(r0,bb)]],FACES)
    def disc(name,cx,cy,z,rx,ry,thickness):
        n=48;vs=[(cx+rx*math.cos(i*math.tau/n),cy+ry*math.sin(i*math.tau/n),zz) for zz in [z-thickness,z] for i in range(n)]
        return mesh(name,vs,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)])
    def portal(name,position,width,depth,h,yaw=0,thick=.37,top=None,broken=False):
        r=width/2;spring=h-r;ca,sa=math.cos(yaw),math.sin(yaw)
        def p(x,y,z):return (position[0]+x*ca-y*sa,position[1]+x*sa+y*ca,position[2]+z)
        pier_height=spring if top is None else top
        for sign in [-1,1]:box(name+' pier',p(sign*(r-thick/2),0,pier_height/2),(thick,depth,pier_height),yaw)
        for k in range(12):
            if broken and k in [5,6]:continue
            aa=k*math.pi/12;bb=(k+1)*math.pi/12
            if top is None:
                vs=[p(rad*math.cos(a),y,spring+rad*math.sin(a)) for y in [-depth/2,depth/2] for rad,a in [(r-thick,aa),(r,aa),(r,bb),(r-thick,bb)]]
            else:
                x0=-(r-thick)+2*(r-thick)*k/12;x1=-(r-thick)+2*(r-thick)*(k+1)/12
                z0=spring+math.sqrt(max(0,(r-thick)**2-x0*x0));z1=spring+math.sqrt(max(0,(r-thick)**2-x1*x1))
                vs=[p(x,y,z) for y in [-depth/2,depth/2] for x,z in [(x0,z0),(x1,z1),(x1,top),(x0,top)]]
            mesh(name+' arch',vs,FACES)
        origin=p(0,-depth-1,min(1.,spring*.5));direction=(-sa,ca,0)
        portals.append({'name':name,'origin_m':origin,'direction':direction,'distance_m':depth*2+2,'clear_width_m':width-2*thick})
    # Pair with the actual detailed surface, including its discretization, not
    # merely the analytic height function from which that surface was sampled.
    def tree(objects):
        vs=[];fs=[]
        for ob in objects:
            off=len(vs);vs.extend([ob.matrix_world@v.co for v in ob.data.vertices]);fs.extend([tuple(off+i for i in p.vertices) for p in ob.data.polygons])
        return BVHTree.FromPolygons(vs,fs)
    source=[o for objects in api['groups'].values() for o in objects if o.name=='Continuous terrain']
    if len(source)!=1:raise ValueError('Structural terrain requires one unambiguous detailed terrain surface')
    source_tree=tree(source)
    # Distant visible terrain remains present in structural paired data.
    for objects in api['groups'].values():
        for distant in objects:
            if distant.name=='Distant terrain':
                mesh('Distant terrain',[tuple(distant.matrix_world@v.co) for v in distant.data.vertices],[tuple(p.vertices) for p in distant.data.polygons])
    court_exposure=None
    if cfg.get('paving_style') in ('fitted','modular') and not cfg.get('terrace'):
        from court_exposure import evaluate as evaluate_court_exposure
        paving_tree=tree([o for (mat,collision),objects in api['groups'].items() if mat==spec['path_material'] and collision for o in objects])
        def surface_z(surface,x,y):
            hit=surface.ray_cast(Vector((x,y,1000)),Vector((0,0,-1)),2000)[0]
            return None if hit is None else hit.z
        court_exposure=evaluate_court_exposure(cfg,lambda x,y:surface_z(source_tree,x,y),lambda x,y:surface_z(paving_tree,x,y))
        (out/'court_exposure.json').write_text(json.dumps(court_exposure,indent=2),encoding='utf-8')
        if not court_exposure['passed']:raise ValueError('Actual court paving is missing or buried beneath terrain; see court_exposure.json')
    if cfg.get('paving_style')=='terrain':
        from natural_court import evaluate as evaluate_natural_court
        def actual_terrain(x,y):
            hit=source_tree.ray_cast(Vector((x,y,1000)),Vector((0,0,-1)),2000)[0]
            return None if hit is None else hit.z
        court_exposure=evaluate_natural_court(cfg,actual_terrain,height)
        (out/'court_exposure.json').write_text(json.dumps(court_exposure,indent=2),encoding='utf-8')
        if not court_exposure['passed']:raise ValueError('Natural court lacks continuous gentle support; see court_exposure.json')
    top=max(v.co.z for v in source[0].data.vertices)+20
    bottom=min(v.co.z for v in source[0].data.vertices)-20
    extent=cfg.get('terrain_extent_m',100);half=spec['size_m']/2
    # BVH triangle tests at the outermost shared vertex are numerically unstable.
    # Keep the proxy XY boundary, sampling Z 0.1 mm inside that same surface;
    # interior validation probes are never shifted and any interior miss fails.
    edge_inset=.0001
    def ground(surface,x,y):
        limit=extent/2
        if abs(abs(x)-limit)<1e-8:x=math.copysign(limit-edge_inset,x)
        if abs(abs(y)-limit)<1e-8:y=math.copysign(limit-edge_inset,y)
        hit=surface.ray_cast(Vector((x,y,top)),Vector((0,0,-1)),top-bottom)[0]
        if hit is None:raise ValueError('Terrain surface probe missed at '+str((x,y)))
        return hit.z
    probes=[(-half+2*half*(i+.37)/31,-half+2*half*(j+.61)/31) for i in range(31) for j in range(31)]
    expected=[ground(source_tree,x,y) for x,y in probes]
    def evaluate(vs,fs):
        candidate=BVHTree.FromPolygons(vs,fs)
        return [abs(ground(candidate,x,y)-z) for (x,y),z in zip(probes,expected)]
    from terrain_lod import refine,probe_regions
    regional_points=probe_regions(extent,cfg)
    regional_expected={name:[ground(source_tree,x,y) for x,y in points] for name,points in regional_points.items()}
    def evaluate_regions(vs,fs):
        candidate=BVHTree.FromPolygons(vs,fs)
        return {name:[abs(ground(candidate,x,y)-z) for (x,y),z in zip(points,regional_expected[name])]
                for name,points in regional_points.items()}
    vs,fs,terrain_audit=refine(extent,max(cfg.get('whitebox_grid_m',1.25),cfg.get('terrain_grid_m',.5)),
        cfg.get('terrain_grid_m',.5),lambda x,y:ground(source_tree,x,y),evaluate,evaluate_regions=evaluate_regions)
    terrain_audit['reference']='Independent vertical rays against actual detailed terrain mesh before FBX coordinate conversion'
    terrain_audit['outer_boundary_height_probe_inset_m']=edge_inset
    (out/'whitebox_terrain_audit.json').write_text(json.dumps(terrain_audit,indent=2),encoding='utf-8')
    if not terrain_audit['passed']:raise ValueError('Whitebox terrain error exceeds 18 cm after bounded grid refinement; see whitebox_terrain_audit.json')
    terrain=mesh('terrain',vs,fs)
    if cfg.get('exploration'):
        from exploration import whitebox as exploration_whitebox
        exploration_whitebox(api,{'mesh':mesh,'disc':disc,'wedge':wedge})
    cx,cy=api['center'];rx,ry=cfg.get('court_radii',[7,8])
    if cfg.get('terrace'):
        t=cfg['terrace'];disc('terrace',cx,cy,t['height']+.045,t['radius'],t['radius'],t['height']+.045)
    elif cfg.get('paving_style')=='modular':
        from court_outline import prism
        court_vs,court_fs=prism(cfg)
        mesh('modular court footprint',court_vs,court_fs)
    elif cfg.get('paving_style')!='terrain':disc('court',cx,cy,cfg.get('court_base_z',0)+.135,rx,ry,.14)
    for ri,run in enumerate(cfg.get('arcades',[])):
        start=Vector((*run['start'],0));delta=Vector((*run['end'],0))-start;length=delta.length;tangent=delta.normalized();side=Vector((-tangent.y,tangent.x,0));yaw=math.atan2(tangent.y,tangent.x)
        width=run.get('width',2.5);base=run.get('base_z',.08);h=run.get('height',4.5);bays=run.get('bays',max(2,round(length/3.3)));bay=length/bays
        def p(x,y,z):return start+tangent*x+side*y+Vector((0,0,z))
        box('aisle',p(length/2,width/2,base-.03),(length,width,.14),yaw)
        for j in range(bays):
            x=(j+.5)*bay
            for yy in ([0] if run.get('backing_wall',False) else [0,width]):portal(f'arcade {ri} bay {j}',p(x,yy,base),bay+.1,.52,h,yaw,top=h+.10)
            if j in run.get('open_bays',[]):pass
            elif run.get('backing_wall',False):
                # Keep each slit window open; a single box here would destroy it.
                for xx in [-1,1]:box('back wall',p(x+xx*(bay*.25+.21),width,base+h/2),(bay*.5-.42,.65,h),yaw)
                box('window sill wall',p(x,width,base+.75),(.84,.65,1.5),yaw)
                box('window lintel',p(x,width,base+h-.40),(.84,.65,.8),yaw)
            else:box('low wall',p(x,width,base+.32),(bay,.65,.64),yaw)
        for yy in [0,width]:box('cornice',p(length/2,yy,base+h+.30),(length,.76,.52),yaw)
        slope=run.get('roof_rise',.62)/width
        # Coarse roof strips keep explicitly authored gaps, without individual tiles.
        cuts=sorted({0.,1.,*[float(v) for opening in run.get('roof_openings',[]) for v in opening[:2]]})
        for a,b in zip(cuts,cuts[1:]):
            trim=max([o[2] for o in run.get('roof_openings',[]) if o[0]<(a+b)/2<o[1]] or [0.])
            y0=-.38+(width+.76)*trim;y1=width+.38
            z=base+h+.65
            mesh('roof envelope',[p(x,y,z+y*slope+zz) for zz in [0,.12] for x,y in [(a*length,y0),(b*length,y0),(b*length,y1),(a*length,y1)]],FACES)
    for ai,item in enumerate(cfg.get('apses',[])):
        cx,cy=item['center'];r=item['radius'];h=item['height'];base=item.get('base_z',.08);rot=math.radians(item.get('rotation_deg',0));op=math.radians(item.get('opening_degrees',100))
        a0=math.pi/2+op/2+rot;a1=math.pi/2+math.tau-op/2+rot
        from curved_wall import build_wall
        build_wall(item,lambda name,vs,fs,material:mesh(name,vs,fs),None,proxy=True)
        wedge('apse cornice',cx,cy,base+h+.19,r-.32,r+.5,a0,a1,.5,40)
        rise=item.get('roof_rise',r*.78);ra,rb=(0,math.tau) if item.get('complete_roof') else (a0,a1)
        vs=[];fs=[];bands=8;sectors=32
        for b in range(bands+1):
            t=b*math.pi/2/bands
            for s in range(sectors+1):
                a=ra+(rb-ra)*s/sectors;vs.append((cx+(r+.23)*math.cos(t)*math.cos(a),cy+(r+.23)*math.cos(t)*math.sin(a),base+h+.45+(rise+.06)*math.sin(t)))
        for b in range(bands):
            for s in range(sectors):k=b*(sectors+1)+s;fs.append((k,k+1,k+sectors+2,k+sectors+1))
        roof=mesh('vault envelope',vs,fs);mod=roof.modifiers.new('Physical shell','SOLIDIFY');mod.thickness=.12
        bpy.context.view_layer.objects.active=roof;bpy.ops.object.modifier_apply(modifier=mod.name)
        if item.get('front_portal'):
            width=2*r*math.sin(op/2);front=r*math.cos(op/2)
            portal('apse entrance '+str(ai),(cx-front*math.sin(rot),cy+front*math.cos(rot),base),width,1.05,h+.15,rot,.52,h+.70)
    for bed in cfg.get('garden_beds',[]):
        cx,cy=bed['center'];rx,ry=bed['radii'];z=height(cx,cy);n=24
        vs=[(cx,cy,z+bed.get('height',.3))]+[(cx+rx*math.cos(i*math.tau/n),cy+ry*math.sin(i*math.tau/n),height(cx+rx*math.cos(i*math.tau/n),cy+ry*math.sin(i*math.tau/n))+.015) for i in range(n)]
        mesh('earth bed',vs,[(0,i+1,(i+1)%n+1) for i in range(n)])
    for item in spec['objects']:
        p=item['position'];d=item['scale'];yaw=math.radians(item.get('yaw_deg',0));kind=item['kind']
        if kind=='asset':continue # Per-instance scan envelopes below.
        if item.get('snap_to_terrain'):p=[p[0],p[1],height(p[0],p[1])+p[2]]
        if kind=='arch':portal('freestanding arch',p,*d,yaw,thick=.48,broken=item.get('broken',False))
        elif kind=='column':disc('column',p[0],p[1],p[2]+d[2],d[0]*.43,d[0]*.43,d[2])
        elif kind=='stairs':
            from ground_support import stair_boxes
            for center,dimensions in stair_boxes(p,d,yaw,height):box('step',center,dimensions,yaw)
        elif kind=='arc_wall':
            aa,bb=map(math.radians,item.get('arc_degrees',[15,165]));wedge('curved wall',p[0],p[1],p[2]+d[2]/2,d[0],d[0]+d[1],aa,bb,d[2])
        else:box('prop mass',(p[0],p[1],p[2]+d[2]/2),d,yaw)
    # Unrecognized architecture modules retain source connectivity through a
    # structural union, rather than bounding-boxing across their doorways.
    if cfg.get('structures') or cfg.get('galleries') or cfg.get('terrace'):
        candidates=[o for (mat,col),objs in api['groups'].items() for o in objs if col and o.name not in ['Continuous terrain'] and not o.name.startswith(('Fitted','Rooted')) and not o.get('whitebox_instance')]
        if candidates:
            vs=[];fs=[]
            for ob in candidates:
                off=len(vs);vs.extend([ob.matrix_world@v.co for v in ob.data.vertices]);fs.extend([tuple(off+i for i in p.vertices) for p in ob.data.polygons])
            ob=mesh('structural source union',vs,fs);bpy.context.view_layer.objects.active=ob
            remesh=ob.modifiers.new('Fuse masonry courses','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.12;remesh.use_smooth_shade=False
            bpy.ops.object.modifier_apply(modifier=remesh.name)
            dec=ob.modifiers.new('Coarse structural envelope','DECIMATE');dec.ratio=min(1,12000/max(1,len(ob.data.polygons)));bpy.ops.object.modifier_apply(modifier=dec.name)
    # A modifier in the populated scene updates thousands of unrelated objects.
    # Simplify each normalized source once in a tiny isolated scene, then place
    # the same envelope with each instance's actual world transform.
    envelopes={};scratch=bpy.data.scenes.new('Whitebox envelope workspace')
    for (mat,col),objects in api['groups'].items():
        material=api['materials'][mat];cls=material.get('semantic_class')
        # Leaves and grass remain omitted, but solid collidable scans such as
        # rooted wood need a companion envelope even when semantically vegetation.
        if (cls=='vegetation' or material.get('surface') in ['grass','foliage']) and not col:continue
        for source in objects:
            if not source.get('whitebox_instance'):continue
            dims=source.dimensions
            if max(dims)<.65:continue
            key=source.data.get('pipeline_source_key') or source.data.as_pointer()
            if key not in envelopes and source.data.get('pipeline_proxy_file'):
                from generated_parts import proxy_mesh
                envelopes[key]=proxy_mesh(source.data['pipeline_proxy_file'])
            if key not in envelopes:
                bm=bmesh.new();bm.from_mesh(source.data)
                hull=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
                remove=set(hull.get('geom_interior',[])+hull.get('geom_unused',[]))
                if remove:bmesh.ops.delete(bm,geom=list(remove),context='VERTS')
                me=bpy.data.meshes.new('proxy envelope');bm.to_mesh(me);bm.free()
                temporary=bpy.data.objects.new('Envelope simplification',me);scratch.collection.objects.link(temporary)
                layer=scratch.view_layers[0];layer.objects.active=temporary;temporary.select_set(True,view_layer=layer)
                dec=temporary.modifiers.new('Envelope budget','DECIMATE');dec.ratio=min(1,60/max(1,len(me.polygons)))
                with bpy.context.temp_override(scene=scratch,view_layer=layer,object=temporary,active_object=temporary,selected_objects=[temporary],selected_editable_objects=[temporary]):
                    bpy.ops.object.modifier_apply(modifier=dec.name)
                envelopes[key]=temporary.data.copy();bpy.data.objects.remove(temporary,do_unlink=True)
            ob=bpy.data.objects.new('WB_scan envelope',envelopes[key]);bpy.context.collection.objects.link(ob);ob.matrix_world=source.matrix_world.copy();parts.append(ob)
    bpy.data.scenes.remove(scratch)
    print('WHITEBOX_ENVELOPES',len(envelopes),'templates',flush=True)
    if cfg.get('terrain_channels'):
        from terrain_channels import build as build_channels
        build_channels({**api,'mesh':lambda name,vs,fs,material,**kw:mesh(name,vs,fs)})
    if cfg.get('destination_details'):
        from destination_details import build as build_destinations
        build_destinations({**api,'mesh':lambda name,vs,fs,material,**kw:mesh(name,vs,fs)},proxy=True)
    if cfg.get('modular_architecture'):
        from modular_architecture import build as build_modules
        def module_proxy(name,vs,fs,material,**kw):
            # Transparent architectural infill has no opaque measurement
            # surface. Keep its supporting frame and dry collision structure.
            if api['materials'].get(material,{}).get('surface')=='thin_glass':return None
            return mesh(name,vs,fs)
        build_modules({**api,'portal_tests':portals,'mesh':module_proxy},proxy=True)
    if cfg.get('pressure_habitat'):
        from pressure_habitat import build as build_habitat
        build_habitat({**api,'portal_tests':portals,'mesh':lambda name,vs,fs,material,**kw:mesh(name,vs,fs)},proxy=True)
    if cfg.get('organic_paths'):
        from organic_paths import build as build_organic_paths
        build_organic_paths({**api,'mesh':lambda name,vs,fs,material,**kw:mesh(name,vs,fs)},proxy=True)
    # Independent portal ray tests in source and companion geometry. Missing or
    # plugged openings are release failures, not merely a matching matrix.
    low=tree(parts);high=tree([o for (m,c),objs in api['groups'].items() if c for o in objs])
    for p in portals:
        start=Vector(p['origin_m']);direction=Vector(p['direction'])
        p['source_clear']=high.ray_cast(start,direction,p['distance_m'])[0] is None
        p['whitebox_clear']=low.ray_cast(start,direction,p['distance_m'])[0] is None
    # Test ray distance only across each wall. Source collisions from adjacent
    # buttresses are still reported and cannot be claimed as a clear portal.
    if any(p['source_clear'] and not p['whitebox_clear'] for p in portals):raise ValueError('Whitebox filled an open source portal')
    corridor_samples=0;corridor_obstructions=[];support_failures=[]
    try:from .walk_support import sample as walking_support
    except ImportError:from walk_support import sample as walking_support
    def support_cast(origin,direction,distance):return high.ray_cast(Vector(origin),Vector(direction),distance)
    habitat_support=None
    if cfg.get('pressure_habitat'):
        # The seabed is not the combat floor. Verify the actual dry deck in
        # both representations at distributed points before exporting either.
        rows=[];cx,cy=cfg.get('court_center',[0,0]);rx,ry=cfg['court_radii'];z=cfg.get('court_base_z',0)
        for j in range(-3,4):
            for i in range(-3,4):
                x=cx+rx*i*.18;y=cy+ry*j*.18
                try:
                    detailed=walking_support(support_cast,x,y,z)
                    proxy_z=walking_support(lambda o,d,t:low.ray_cast(Vector(o),Vector(d),t),x,y,z)
                    ok=abs(detailed-z)<.18 and abs(proxy_z-detailed)<.18
                    rows.append({'xy_m':[x,y],'detailed_z_m':detailed,'proxy_z_m':proxy_z,'passed':ok})
                except ValueError as error:rows.append({'xy_m':[x,y],'passed':False,'error':str(error)})
        habitat_support={'samples':len(rows),'rows':rows,'passed':all(row['passed'] for row in rows)}
        if not habitat_support['passed'] or any(not p['source_clear'] or not p['whitebox_clear'] for p in portals):
            (out/'habitat_geometry_failure.json').write_text(json.dumps({'dry_support':habitat_support,'portals':portals},indent=2))
            raise ValueError('Dry habitat floor support or actual pressure portal failed; inspect habitat_geometry_failure.json')
    if cfg.get('exploration'):
        # Check the built collision geometry, independently of the path author's
        # intent. Body-height rays sample both sides of a humanoid corridor.
        for ri,(route,points) in enumerate(api['route_field'].routes):
            for i in range(len(points)-1):
                a,b=points[i],points[i+1];dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
                if length<.01:continue
                for side in [-.4,0,.4]:
                    ax,ay=a[0]-dy/length*side,a[1]+dx/length*side
                    bx,by=b[0]-dy/length*side,b[1]+dx/length*side
                    try:
                        # Foundation blending can raise an approach above its
                        # guide spline; bridge excavation can lower the bed.
                        # Probe the greater intended/actual ground elevation.
                        az=walking_support(support_cast,ax,ay,max(float(a[2]),height(ax,ay)))
                        bz=walking_support(support_cast,bx,by,max(float(b[2]),height(bx,by)))
                    except ValueError as error:
                        support_failures.append({'route':ri,'segment':i,'offset_m':side,'error':str(error)})
                        continue
                    for elevation in [.45,1.0,1.65]:
                        start=Vector((ax,ay,az+elevation));end=Vector((bx,by,bz+elevation));delta=end-start
                        hit=high.ray_cast(start,delta.normalized(),delta.length)[0];corridor_samples+=1
                        if hit is not None:corridor_obstructions.append({'route':ri,'segment':i,'offset_m':side,'height_m':elevation,'hit_m':list(hit)})
    terrain_tree=tree([terrain])
    samples=[abs(ground(terrain_tree,x,y)-z) for (x,y),z in zip(probes,expected)]
    samples.sort();p95=samples[int(len(samples)*.95)]
    if p95>.18:raise ValueError('Whitebox terrain error exceeds 18 cm in the gameplay envelope')
    from mesh_complexity import triangle_count
    original_triangles=triangle_count(o for objs in api['groups'].values() for o in objs)
    triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in parts)
    if triangles>=original_triangles*.5:raise ValueError('Whitebox did not remove enough render complexity')
    records=[]
    # Single mesh asset, but retain the per-part manifest for traceability/editing.
    for i,o in enumerate(parts):records.append({'id':i,'name':o.name,'triangles':sum(len(p.vertices)-2 for p in o.data.polygons)})
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();ob=bpy.context.object
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    ob.data.transform(Matrix.Diagonal(Vector((100,-100,100,1))));ob.data.flip_normals();ob.data.update()
    path=out/'whitebox.fbx';bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
    ob.hide_render=True;ob.hide_set(True)
    report={'schema_version':1,'file':str(path),'triangles':triangles,'source_triangles_before_bevel':original_triangles,'ratio':triangles/original_triangles,'source_spec_sha256':hashlib.sha256(Path(api['job']['scene_spec']).read_bytes()).hexdigest(),'coordinate_contract':'same metric layout and FBX basis as RGB; UE cm','parts':records,'portal_tests':portals,'terrain_p95_error_m':p95,'omitted':['grass','small foliage','material detail','brick and tile courses'],'collision':False}
    if cfg.get('exploration'):report['route_clearance']={'samples':corridor_samples,'obstructions':corridor_obstructions,'support_failures':support_failures,'passed':not corridor_obstructions and not support_failures,'support_policy':'Actual upward-facing collision surface within +31/-35cm of declared route feet, before body-clearance probes.'}
    if court_exposure is not None:report['court_exposure']=court_exposure
    if habitat_support is not None:report['habitat_dry_support']=habitat_support
    report['terrain_sampling']=terrain_audit
    manifest=out/'whitebox.json';manifest.write_text(json.dumps(report,indent=2),encoding='utf-8');report['manifest']=str(manifest)
    return report
