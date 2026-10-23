"""Add recorded small scan instances to an isolated scene revision.

Only non-colliding vegetation is supported here; structural additions belong in
the scene builder. Placement reads the saved terrain instead of an estimated Z.
"""
import bpy,json,sys,hashlib
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise RuntimeError('Use a new scene revision directory')
report=json.loads(Path(job['source_report']).read_text());data=json.loads(Path(job['scene_spec']).read_text())
library=json.loads(Path(job['library_job']).read_text())['mesh_library']
bpy.ops.wm.open_mainfile(filepath=report['blend'])
terrain=bpy.data.objects['Environment_0']
ground=BVHTree.FromPolygons([terrain.matrix_world@v.co for v in terrain.data.vertices],[tuple(p.vertices) for p in terrain.data.polygons])
templates={};created={};placements=[]
for item in job['instances']:
    asset=item['asset'];conf=library[asset];mat=conf['material_id']
    if conf['material'].get('semantic_class')!='vegetation' or conf['material'].get('surface')!='foliage':raise RuntimeError('This repair only accepts small masked vegetation')
    if max(item['scale'])>1.5:raise RuntimeError('Large vegetation requires a structural companion policy')
    if asset not in templates:
        before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=conf['file'])
        imported=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
        mode=job.get('variant_modes',{}).get(asset,conf.get('variant_mode','assembled'))
        if mode=='separate' and conf.get('variant_mode')!='separate' and not job.get('variant_evidence',{}).get(asset):raise RuntimeError('Separating a source assembly requires recorded variant-sheet evidence')
        if mode=='assembled' and len(imported)>1:
            bpy.ops.object.select_all(action='DESELECT')
            for ob in imported:ob.select_set(True)
            bpy.context.view_layer.objects.active=imported[0];bpy.ops.object.join();imported=[bpy.context.object]
        sources=[]
        for ob in imported:
            bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
            triangles=sum(len(p.vertices)-2 for p in ob.data.polygons)
            if triangles>conf['triangle_budget']:
                mod=ob.modifiers.new('Source scan budget','DECIMATE');mod.ratio=conf['triangle_budget']/triangles;bpy.ops.object.modifier_apply(modifier=mod.name)
            m=ob.matrix_world.copy();coords=np.array([m@v.co for v in ob.data.vertices]);lo=coords.min(0);hi=coords.max(0);dims=np.maximum(hi-lo,.001)
            origin=Vector(((hi[0]+lo[0])/2,(hi[1]+lo[1])/2,lo[2]))
            me=ob.data.copy();me.transform(Matrix.Diagonal(Vector((1/dims[0],1/dims[1],1/dims[2],1)))@Matrix.Translation(-origin)@m)
            sources.append((me,dims.tolist()))
        for ob in list(bpy.data.objects):
            if ob not in before:bpy.data.objects.remove(ob,do_unlink=True)
        templates[asset]=sources
    source,dims=templates[asset][item.get('variant',0)%len(templates[asset])]
    hit=ground.ray_cast(Vector((item['position'][0]*100,-item['position'][1]*100,10000)),Vector((0,0,-1)),20000)[0]
    if hit is None:raise RuntimeError('Missing saved terrain beneath planting')
    scale=item['scale']
    if conf.get('preserve_aspect',True):
        factor=min(scale[i]/dims[i] for i in range(3));scale=[v*factor for v in dims]
    # The saved scene uses the same reflected centimetre basis as FBX exports.
    z=hit.z/100+item['position'][2];me=source.copy()
    world=Matrix.Translation(Vector((item['position'][0],item['position'][1],z)))@Matrix.Rotation(item.get('yaw',0),4,'Z')@Matrix.Diagonal(Vector((*scale,1)))
    me.transform(Matrix.Diagonal(Vector((100,-100,100,1)))@world);me.flip_normals();me.update()
    ob=bpy.data.objects.new('Groundcover addition',me);bpy.context.collection.objects.link(ob);created.setdefault(mat,[]).append(ob)
    placements.append({**item,'measured_ground_z_m':hit.z/100,'variant_mode':job.get('variant_modes',{}).get(asset,conf.get('variant_mode','assembled'))})
    data['scene']['objects'].append({'kind':'asset','asset':asset,'position':item['position'],'scale':item['scale'],'yaw_deg':item.get('yaw',0)*180/np.pi,'variant':item.get('variant',0),'material':data['scene']['path_material'],'collision':False,'snap_to_terrain':True})
for mat,objects in created.items():
    index=next(i for i,e in enumerate(report['environment']) if e['material']==mat and not e['collision'])
    target=bpy.data.objects['Environment_'+str(index)];bpy.ops.object.select_all(action='DESELECT');target.select_set(True)
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=target;bpy.ops.object.join()
    path=out/f'environment_{index}.fbx';bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
    report['environment'][index]['file']=str(path);report['environment'][index]['triangles']=sum(len(p.vertices)-2 for p in target.data.polygons)
spec=out/'scene_spec.json';spec.write_text(json.dumps(data,indent=2),encoding='utf-8')
report['whitebox']['source_spec_sha256']=hashlib.sha256(spec.read_bytes()).hexdigest()
report['whitebox']['manifest']=str(out/'whitebox.json')
report['whitebox']['omitted_small_groundcover_additions']=report['whitebox'].get('omitted_small_groundcover_additions',0)+len(placements)
(out/'whitebox.json').write_text(json.dumps(report['whitebox'],indent=2),encoding='utf-8')
report['blend']=str(out/'scene.blend');report['groundcover_repairs']=report.get('groundcover_repairs',[])+placements
bpy.ops.wm.save_as_mainfile(filepath=report['blend'])
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(out/'check_job.json').write_text(json.dumps({'scene_spec':str(spec),'out':str(out)},indent=2))
(out/'planting_audit.json').write_text(json.dumps({'source_report':job['source_report'],'source_sha256':hashlib.sha256(Path(job['source_report']).read_bytes()).hexdigest(),'variant_evidence':job.get('variant_evidence',{}),'placements':placements},indent=2))
print('GROUNDCOVER_ADDED',len(placements),flush=True)
