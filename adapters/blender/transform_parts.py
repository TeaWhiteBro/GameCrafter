"""Move complete enclosed geometry islands in a new scene revision.

Local art repairs do not need to regenerate millions of unchanged plant faces.
The selection rejects every component crossing the selection boundary, so a
terrain patch or connected wall cannot be accidentally pulled out of its mesh.
"""
import bpy,json,sys,hashlib,math
from pathlib import Path
from collections import defaultdict,deque
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text());out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
report=json.loads(Path(job['source_report']).read_text());data=json.loads(Path(job['scene_spec']).read_text())
bpy.ops.wm.open_mainfile(filepath=report['blend'])
terrain=bpy.data.objects['Environment_0']
ground=BVHTree.FromPolygons([terrain.matrix_world@v.co for v in terrain.data.vertices],[tuple(p.vertices) for p in terrain.data.polygons])

from island_transform import move_islands

changed=set();audit=[]
whiteboxes=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_')]
if len(whiteboxes)!=1:raise RuntimeError('Expected the combined structural whitebox')
for repair in job['repairs']:
    delta=repair.get('delta_m')
    if delta is None:
        target=repair['target_center_m'];hit=ground.ray_cast(Vector((target[0]*100,-target[1]*100,10000)),Vector((0,0,-1)),20000)[0]
        if hit is None:raise RuntimeError('Repair target has no terrain')
        target[2]=hit.z/100+repair.get('ground_offset_m',0)
        delta=[target[i]-repair['center_m'][i] for i in range(3)]
        data['scene']['objects'][repair['scene_object_index']]['position']=target
    elif 'scene_object_index' in repair:
        item=data['scene']['objects'][repair['scene_object_index']]
        item['position']=[item['position'][i]+delta[i] for i in range(3)]
    counts={}
    for i,e in enumerate(report['environment']):
        if e['material'] not in repair['materials']:continue
        ob=bpy.data.objects['Environment_'+str(i)];count=move_islands(ob,repair,delta)
        if count:changed.add(i);counts[ob.name]=count
    counts['whitebox']=move_islands(whiteboxes[0],repair,delta)
    if not counts['whitebox'] or len(counts)<2:raise RuntimeError('Repair missed detailed or companion geometry')
    audit.append({'selection':repair,'delta_m':delta,'vertices_moved':counts})
    for index in repair.get('portal_indices',[]):
        portal=report['whitebox']['portal_tests'][index]
        portal['origin_m']=[portal['origin_m'][i]+delta[i] for i in range(3)]

def tree(objects):
    vs=[];fs=[]
    for ob in objects:
        offset=len(vs);vs.extend([ob.matrix_world@v.co for v in ob.data.vertices]);fs.extend([tuple(offset+i for i in p.vertices) for p in ob.data.polygons])
    return BVHTree.FromPolygons(vs,fs)
high=tree([bpy.data.objects['Environment_'+str(i)] for i,e in enumerate(report['environment']) if e['collision']]);low=tree(whiteboxes)
for portal in report['whitebox'].get('portal_tests',[]):
    origin=portal['origin_m'];direction=portal['direction'];start=Vector((origin[0]*100,-origin[1]*100,origin[2]*100));ray=Vector((direction[0],-direction[1],direction[2]))
    portal['source_clear']=high.ray_cast(start,ray,portal['distance_m']*100)[0] is None
    portal['whitebox_clear']=low.ray_cast(start,ray,portal['distance_m']*100)[0] is None
    if portal['source_clear'] and not portal['whitebox_clear']:raise RuntimeError('Repair blocked a structural companion portal')

def export(ob,path):
    bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
for i in sorted(changed):
    path=out/f'environment_{i}.fbx';export(bpy.data.objects['Environment_'+str(i)],path);report['environment'][i]['file']=str(path)
path=out/'whitebox.fbx';export(whiteboxes[0],path);whiteboxes[0].hide_set(True);whiteboxes[0].hide_render=True
scene_spec=out/'scene_spec.json';scene_spec.write_text(json.dumps(data,indent=2),encoding='utf-8')
report['whitebox']['file']=str(path);report['whitebox']['manifest']=str(out/'whitebox.json');report['whitebox']['source_spec_sha256']=hashlib.sha256(scene_spec.read_bytes()).hexdigest()
report['whitebox'].pop('route_clearance',None)
(out/'whitebox.json').write_text(json.dumps(report['whitebox'],indent=2),encoding='utf-8')
report['blend']=str(out/'scene.blend');report['local_repairs']=audit
bpy.ops.wm.save_as_mainfile(filepath=report['blend'])
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(out/'repair_audit.json').write_text(json.dumps({'source_report':job['source_report'],'source_report_sha256':hashlib.sha256(Path(job['source_report']).read_bytes()).hexdigest(),'repairs':audit},indent=2))
(out/'check_job.json').write_text(json.dumps({'scene_spec':str(scene_spec),'out':str(out)},indent=2))
print('LOCAL_GEOMETRY_REPAIR',json.dumps(audit),flush=True)
