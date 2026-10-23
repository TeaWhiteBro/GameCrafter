"""Rebuild only route paving and settle selected rocks with matching proxies.

Uses a saved scene, real terrain BVH and bounded content-data regions. Source
assets are preserved. The repair job plus source hashes reproduces this step.
"""
import bpy,bmesh,json,sys,hashlib,random
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from exploration import RouteField
from landscape_routes import build_paving
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8-sig'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise RuntimeError('Preserve previous repair result')
report=json.loads(Path(job['source_report']).read_text(encoding='utf-8-sig'))
data=json.loads(Path(job['scene_spec']).read_text(encoding='utf-8-sig'))
audit=json.loads(Path(job['rock_audit']).read_text(encoding='utf-8-sig'))
assert audit['source_report_sha256']==hashlib.sha256(Path(job['source_report']).read_bytes()).hexdigest()
assert audit['source_blend_sha256']==hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=report['blend'])
ground=bpy.data.objects['Environment_0']
tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],[tuple(p.vertices) for p in ground.data.polygons])
def height(x,y):
 hit=tree.ray_cast(Vector((x*100,-y*100,50000)),Vector((0,0,-1)))[0]
 if hit is None:raise RuntimeError('Missing saved terrain')
 return hit.z/100
cfg=data['scene']['composition']['exploration'];vs=[];fs=[];colors=[]
def mesh(name,verts,faces,material,**kwargs):
 if material!=cfg['paving_material']:raise RuntimeError('Mixed paving materials require separate rebuilds')
 offset=len(vs);vs.extend(verts);fs.extend([tuple(offset+i for i in f) for f in faces]);colors.extend(kwargs['colors'])
api={'route_field':RouteField(cfg),'rng':random.Random(job.get('seed',417)),'height':height,'mesh':mesh,'finish_stone':lambda ob,w:ob}
count=build_paving(api)
indices=[i for i,e in enumerate(report['environment']) if e['material']==cfg['paving_material']]
if len(indices)!=1:raise RuntimeError('Expected dedicated route paving material')
index=indices[0];ob=bpy.data.objects['Environment_'+str(index)]
me=bpy.data.meshes.new('Refined continuous route paving');me.from_pydata(vs,[],fs);me.update()
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
attr=me.color_attributes.new(name='SurfaceWeights',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',np.asarray(colors,np.float32).ravel())
me.transform(Matrix.Diagonal(Vector((100,-100,100,1))));me.flip_normals();me.update();ob.data=me;ob.matrix_world=Matrix.Identity(4)
changed={index};print('REBUILT_PAVING',count,len(fs),flush=True)

def components(ob,seams=False):
 me=ob.data;coords=np.empty((len(me.vertices),3),np.float32);me.vertices.foreach_get('co',coords.ravel())
 matrix=np.asarray(ob.matrix_world);world=coords@matrix[:3,:3].T+matrix[:3,3]
 parent=list(range(len(coords)))
 def find(v):
  while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
  return v
 if seams:
  _,first,inverse=np.unique(np.round(world,2),axis=0,return_index=True,return_inverse=True)
  for i,j in enumerate(first[inverse]):parent[i]=int(j)
 edges=np.empty((len(me.edges),2),np.int32);me.edges.foreach_get('vertices',edges.ravel())
 for a,b in edges:
  a=find(int(a));b=find(int(b))
  if a!=b:parent[b]=a
 roots=np.array([find(i) for i in range(len(coords))]);order=np.argsort(roots);cuts=np.r_[0,1+np.flatnonzero(np.diff(roots[order])),len(order)]
 groups={int(roots[order[a]]):order[a:b] for a,b in zip(cuts[:-1],cuts[1:])}
 return coords,world,groups
wb=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_')]
assert len(wb)==1;wb=wb[0];wc,ww,wgroups=components(wb)
candidate=[]
for key,ids in wgroups.items():
 if len(ids)<12:continue
 pts=ww[ids];lo=pts.min(0);hi=pts.max(0)
 if np.ptp(pts[:,0])>6000 or np.ptp(pts[:,1])>6000:continue
 candidate.append((key,np.r_[lo,hi]))
used=set();repairs=[]
lo,hi=job['rock_region_m']
selected=[r for r in audit['components'] if all(lo[i]<=r['center_m'][i]<=hi[i] for i in range(2)) and r.get('max_bottom_gap_m',0)>job.get('max_undercut_m',.2)]
for index in sorted({r['environment'] for r in selected}):
 ob=bpy.data.objects['Environment_'+str(index)];coords,world,groups=components(ob,True)
 for row in [r for r in selected if r['environment']==index]:
  ids=groups[row['component']];pts=world[ids];low=pts.min(0);high=pts.max(0);bounds=np.r_[low,high];size=np.maximum(high-low,20)
  ranked=sorted((float(np.linalg.norm((b-bounds)/np.r_[size,size])),key) for key,b in candidate if key not in used)
  score,key=ranked[0]
  if score>.25 or (len(ranked)>1 and ranked[1][0]-score<.015):raise RuntimeError('Ambiguous structural rock match: '+str((row['center_m'],ranked[:2])))
  delta=-row['max_bottom_gap_m']-.10
  coords[ids]+=np.asarray(ob.matrix_world.inverted().to_3x3()@Vector((0,0,delta*100)));wc[wgroups[key]]+=np.asarray(wb.matrix_world.inverted().to_3x3()@Vector((0,0,delta*100)));used.add(key)
  repairs.append({'environment':index,'component':row['component'],'center_m':row['center_m'],'delta_z_m':delta,'whitebox_component':key,'proxy_match_error':score,'old_max_undercut_m':row['max_bottom_gap_m'],'detail_vertices':len(ids),'whitebox_vertices':len(wgroups[key])})
 ob.data.vertices.foreach_set('co',coords.ravel());ob.data.update();changed.add(index)
wb.data.vertices.foreach_set('co',wc.ravel());wb.data.update()
assert repairs,'No target rocks selected'
print('SETTLED_ROCKS',json.dumps(repairs),flush=True)
def export(ob,path):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
 bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
for i in sorted(changed):
 ob=bpy.data.objects['Environment_'+str(i)];path=out/f'environment_{i}.fbx';export(ob,path);report['environment'][i]['file']=str(path);report['environment'][i]['triangles']=sum(len(p.vertices)-2 for p in ob.data.polygons)
path=out/'whitebox.fbx';export(wb,path);wb.hide_set(True);wb.hide_render=True
data.setdefault('decisions',[]).append('Saved-terrain route refinement: continuous shared cross-sections, coherent paved centre and feathered shoulders, earth paths without slab stamps; visible gallery-side rock undercuts settled together with matched structural companions. Exact source-hashed postprocess job retained.')
spec=out/'scene_spec.json';spec.write_text(json.dumps(data,indent=2),encoding='utf-8')
report['whitebox'].update(file=str(path),manifest=str(out/'whitebox.json'),source_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest())
report['whitebox'].pop('route_clearance',None)
(out/'whitebox.json').write_text(json.dumps(report['whitebox'],indent=2),encoding='utf-8')
report['exploration']['paving_slabs']=count
report['blend']=str(out/'scene.blend');report['local_refinement']={'source_report':job['source_report'],'source_report_sha256':hashlib.sha256(Path(job['source_report']).read_bytes()).hexdigest(),'source_blend_sha256':audit['source_blend_sha256'],'paving_slabs':count,'settled_rocks':repairs}
bpy.ops.wm.save_as_mainfile(filepath=report['blend'])
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(out/'repair_audit.json').write_text(json.dumps(report['local_refinement'],indent=2),encoding='utf-8')
(out/'check_job.json').write_text(json.dumps({'scene_spec':str(spec),'out':str(out)},indent=2),encoding='utf-8')
print('REFINEMENT_COMPLETE',flush=True)
