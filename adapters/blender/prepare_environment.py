"""Prepare generated static assets, preserve UV/material slots and build an open-surface proxy."""
import bpy, bmesh, json, math, sys, traceback, hashlib
from pathlib import Path
from mathutils import Vector, Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
asset=job['asset'];report={'ok':False};bpy.ops.wm.read_factory_settings(use_empty=True)

def upstream_image(socket,seen=None):
    seen=set() if seen is None else seen
    for link in socket.links:
        node=link.from_node
        if node in seen:continue
        seen.add(node)
        if node.type=='TEX_IMAGE' and node.image:return node.image
        for inp in node.inputs:
            found=upstream_image(inp,seen)
            if found:return found
    return None

def material_data(mat,index):
    if mat.get('pipeline_binding'):
        data=json.loads(mat['pipeline_binding']);data['name']=mat.name;return data
    bs=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if mat.use_nodes else None
    data={'name':mat.name,'surface':'scan','semantic_class':asset['category'],'color':list(mat.diffuse_color)[:3],
        'roughness':.65,'metallic':0,'normal_opengl':True,'normal_strength':.75,'textures':{}}
    if bs:
        data.update(color=list(bs.inputs['Base Color'].default_value)[:3],roughness=float(bs.inputs['Roughness'].default_value),metallic=float(bs.inputs['Metallic'].default_value))
        for kind,socket in [('base','Base Color'),('normal','Normal'),('orm','Roughness'),('emissive','Emission Color')]:
            image=upstream_image(bs.inputs[socket])
            if image:
                path=out/f'mat_{index}_{kind}.png';image.filepath_raw=str(path);image.file_format='PNG';image.save()
                data['textures'][kind]=str(path)
        # Extract only a real linked alpha; opaque atlas alpha is not foliage by default.
        if bs.inputs['Alpha'].is_linked:
            image=upstream_image(bs.inputs['Alpha'])
            if image:
                import numpy as np
                pixels=np.array(image.pixels[:],dtype='float32').reshape(-1,4)
                if float(pixels[:,3].min())<.95:
                    alpha=bpy.data.images.new('Mask',*image.size,alpha=True)
                    channel=pixels[:,3];rgba=np.stack([channel,channel,channel,np.ones_like(channel)],axis=1)
                    alpha.pixels.foreach_set(rgba.ravel());path=out/f'mat_{index}_alpha.png';alpha.filepath_raw=str(path);alpha.file_format='PNG';alpha.save()
                    data['textures']['alpha']=str(path);data['surface']='foliage'
    if 'base' not in data['textures']:
        # Constant materials retain a physical constant; don't invent a photographed scan.
        data.pop('surface')
    if mat.get('pipeline_surface'):data['surface']=mat['pipeline_surface']
    if 'pipeline_collision' in mat:data['collision']=bool(mat['pipeline_collision'])
    if 'pipeline_normal_strength' in mat:data['normal_strength']=float(mat['pipeline_normal_strength'])
    if mat.get('pipeline_constant_roughness'):data.update(roughness_scale=1,roughness_bias=0)
    return data

try:
    if asset.get('construction'):
        from static_recipes import build
        report['construction']=build(asset['construction'],job,out)
    else:bpy.ops.import_scene.gltf(filepath=job['source'])
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if not objects:raise ValueError('No static geometry')
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();ob=bpy.context.object
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    original_vertices=len(ob.data.vertices);bm=bmesh.new();bm.from_mesh(ob.data)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=list(bm.edges));bm.to_mesh(ob.data);bm.free()
    if asset.get('static_cleanup'):
        from static_cleanup import apply as cleanup_static
        report['static_cleanup']=cleanup_static(ob,asset['static_cleanup'])
    lo=Vector(tuple(min(v.co[i] for v in ob.data.vertices) for i in range(3)))
    hi=Vector(tuple(max(v.co[i] for v in ob.data.vertices) for i in range(3)))
    if min(hi-lo)<=1e-6:raise ValueError('Degenerate generated geometry')
    scale=asset['height_m']/(hi.z-lo.z);origin=Vector(((hi.x+lo.x)/2,(hi.y+lo.y)/2,lo.z))
    ob.data.transform(Matrix.Scale(scale,4)@Matrix.Translation(-origin));ob.data.update()
    initial_triangles=sum(len(p.vertices)-2 for p in ob.data.polygons)
    budget=asset.get('triangle_budget',100000 if asset['category']=='vegetation' else 65000)
    source_budget=asset.get('stem_clump',{}).get('source_triangle_budget',budget)
    if initial_triangles>source_budget:
        mod=ob.modifiers.new('Bounded static detail','DECIMATE');mod.ratio=source_budget/initial_triangles;bpy.ops.object.modifier_apply(modifier=mod.name)
    if asset.get('botanical_refinement'):
        from botanical_refinement import refine
        bs=next(n for n in ob.data.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        report['refinement']=refine(ob,asset['botanical_refinement'],upstream_image(bs.inputs['Base Color']))
        budget=max(budget,sum(len(p.vertices)-2 for p in ob.data.polygons))
    if asset.get('texture_regions'):
        from texture_regions import refine
        bs=next(n for n in ob.data.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        report['texture_refinement']=refine(ob,asset['texture_regions'],upstream_image(bs.inputs['Base Color']))
    if asset.get('roof_snow_refinement'):
        from roof_snow import refine
        bs=next(n for n in ob.data.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        report['roof_snow_refinement']=refine(ob,asset['roof_snow_refinement'],upstream_image(bs.inputs['Base Color']))
    if asset.get('culm_refinement'):
        from culm_refinement import refine
        report['culm_refinement']=refine(ob,asset['culm_refinement'])
    if asset.get('stem_clump'):
        from static_clump import build
        report['stem_clump']=build(ob,asset['stem_clump'],asset['height_m'])
        budget=max(budget,sum(len(p.vertices)-2 for p in ob.data.polygons))
    if asset.get('material_settings'):
        settings=asset['material_settings']
        for mat in ob.data.materials:
            bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            if 'roughness' in settings:
                for link in list(bs.inputs['Roughness'].links):mat.node_tree.links.remove(link)
                bs.inputs['Roughness'].default_value=settings['roughness'];mat['pipeline_constant_roughness']=True
            if 'normal_strength' in settings:
                for node in mat.node_tree.nodes:
                    if node.type=='NORMAL_MAP':node.inputs['Strength'].default_value=settings['normal_strength']
                mat['pipeline_normal_strength']=settings['normal_strength']
    for i,mat in enumerate(ob.data.materials):
        if mat:mat.name='gen_'+asset['id']+'_'+str(i)
    materials={str(i):material_data(mat,i) for i,mat in enumerate(ob.data.materials) if mat}
    if not materials or any(str(p.material_index) not in materials for p in ob.data.polygons):raise ValueError('Unbound generated material slot')
    bpy.context.view_layer.update()
    dims=[float(v) for v in ob.dimensions];lo=[min(v.co[i] for v in ob.data.vertices) for i in range(3)]
    # Topology-preserving decimation is intentional: convex hulls plug doors and branch gaps.
    proxy=ob.copy();proxy.data=ob.data.copy();bpy.context.collection.objects.link(proxy);bpy.context.view_layer.objects.active=proxy
    current_triangles=sum(len(p.vertices)-2 for p in proxy.data.polygons)
    mod=proxy.modifiers.new('Structural simplification','DECIMATE');mod.ratio=min(.12,1500/max(1,current_triangles))
    bpy.ops.object.modifier_apply(modifier=mod.name)
    proxy_path=out/'structural_proxy.json'
    proxy_path.write_text(json.dumps({'vertices':[[float((v.co[i]-lo[i])/dims[i]) if i==2 else float(v.co[i]/dims[i]) for i in range(3)] for v in proxy.data.vertices],
        'faces':[list(p.vertices) for p in proxy.data.polygons],'method':'topology-preserving decimation; normalized with full detailed bounds','dimensions_m':dims}),encoding='utf-8')
    bpy.data.objects.remove(proxy,do_unlink=True)
    bpy.context.view_layer.objects.active=ob;ob.select_set(True)
    model=out/'prepared.glb';bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_animations=False)
    mid='gen_'+asset['id']
    binding={'file':str(model),'triangle_budget':budget,'material_id':mid,'material':next(iter(materials.values())),
        'materials':materials,'variant_mode':'assembled','preserve_aspect':True,'placement':asset['use'],
        'structural_proxy':str(proxy_path),'generated':True}
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'prepared.blend'))
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
    scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('InspectionWorld');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.20,.20,.20,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
    scene.view_settings.view_transform='AgX'
    target=Vector((0,0,dims[2]*.5));radius=max(dims)*1.85
    for name,position,power,size in [('Key',(radius,-radius,radius*1.5),1600,5),('Fill',(-radius,-radius*.3,radius*.8),900,6),('Rim',(0,radius,radius),1300,4)]:
        lamp=bpy.data.lights.new(name,'AREA');lamp.energy=power*max(1,dims[2]/2)**2;lamp.shape='DISK';lamp.size=size
        light=bpy.data.objects.new(name,lamp);scene.collection.objects.link(light);light.location=position;light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    cam=bpy.data.cameras.new('Inspection');camera=bpy.data.objects.new('Inspection',cam);scene.collection.objects.link(camera);scene.camera=camera;cam.type='ORTHO';cam.ortho_scale=max(dims)*1.25
    views=[]
    for label,angle in [('front',-90),('side',0),('rear',90),('three_quarter',-45)]:
        a=math.radians(angle);camera.location=(math.cos(a)*radius,math.sin(a)*radius,dims[2]*.8)
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();path=out/(label+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);views.append(str(path))
    report.update(ok=True,binding=binding,views=views,geometry={'source_vertices':original_vertices,'vertices':len(ob.data.vertices),
        'triangles':sum(len(p.vertices)-2 for p in ob.data.polygons),'dimensions_m':dims,'removed_loose_vertices':len(loose),'materials':len(materials)},
        files=[str(model),str(proxy_path),str(out/'prepared.blend')]+views+[p for m in materials.values() for p in m['textures'].values()])
except Exception:report['error']=traceback.format_exc();print(report['error'],flush=True)
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['ok']:sys.exit(1)
