"""Settle explicit complete scanned islands and uniquely matched companions.

Targets are content data, selected from a source-hashed geometry audit. This
postprocess preserves every unchanged face, UV, material and source asset.
"""
import bpy,bmesh,json,sys,hashlib,math
import numpy as np
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mesh_components import components

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2),encoding='utf-8')
job_path=Path(sys.argv[sys.argv.index('--')+1]);job=read(job_path)
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise RuntimeError('Preserve completed scene revision')
report=read(job['source_report']);data=read(job['scene_spec']);audit=read(job['rock_audit'])
assert audit['source_report_sha256']==sha(job['source_report']) and audit['source_blend_sha256']==sha(report['blend'])
rows={(r['environment'],r['component']):r for r in audit['components']}
targets=job['targets'];assert targets and len({(t['environment'],t['component']) for t in targets})==len(targets)
for t in targets:
 assert (t['environment'],t['component']) in rows
 assert isinstance(t['delta_z_m'],(int,float)) and math.isfinite(t['delta_z_m']) and -5<=t['delta_z_m']<0
 assert len(t.get('delta_xy_m',[0,0]))==2 and all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<=20 for v in t.get('delta_xy_m',[0,0]))
bpy.ops.wm.open_mainfile(filepath=report['blend'])
companions=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_')]
assert len(companions)==1;wb=companions[0];wc,ww,wgroups=components(wb)
candidates=[]
for key,ids in wgroups.items():
 if len(ids)<12:continue
 pts=ww[ids]
 if np.ptp(pts[:,0])>6000 or np.ptp(pts[:,1])>6000:continue
 candidates.append((key,np.r_[pts.min(0),pts.max(0)]))
used=set();repairs=[];new_proxies=[]
for index in sorted({t['environment'] for t in targets}):
 allowed=job.get('allowed_semantic_ids',[4])
 assert allowed and all(v in [4,5,6] for v in allowed)
 assert report['environment'][index]['semantic_id'] in allowed
 ob=bpy.data.objects['Environment_'+str(index)];coords,world,groups=components(ob,True)
 for t in [t for t in targets if t['environment']==index]:
  row=rows[index,t['component']];ids=groups[t['component']];pts=world[ids];lo=pts.min(0);hi=pts.max(0)
  centre=np.array([(lo[0]+hi[0])/200,-(lo[1]+hi[1])/200,(lo[2]+hi[2])/200])
  assert len(ids)==row['vertices'] and np.max(abs(centre-np.array(row['center_m'])))<.001
  bounds=np.r_[lo,hi];size=np.maximum(hi-lo,20)
  ranked=sorted((float(np.linalg.norm((b-bounds)/np.r_[size,size])),key) for key,b in candidates if key not in used)
  score,key=ranked[0]
  # The structural companion excludes vegetation material classes.
  # Explicitly documented omissions may receive a new envelope only when no
  # existing component meets the unchanged matching tolerance.
  create=bool(t.get('create_missing_companion')) and t.get('source_proxy_policy')=='omitted_vegetation' and score>.25 and report['environment'][index]['semantic_id']==5 and report['environment'][index]['collision']
  if not create and (score>.25 or (len(ranked)>1 and ranked[1][0]-score<.015)):raise RuntimeError('Ambiguous structural scan companion: '+str({'environment':index,'component':t['component'],'center_m':row['center_m'],'nearest':ranked[:3]}))
  xy=t.get('delta_xy_m',[0,0]);delta=Vector((xy[0]*100,-xy[1]*100,t['delta_z_m']*100))
  coords[ids]+=np.asarray(ob.matrix_world.inverted().to_3x3()@delta)
  if create:new_proxies.append({'points':pts+np.asarray(delta),'environment':index,'component':t['component']})
  else:wc[wgroups[key]]+=np.asarray(wb.matrix_world.inverted().to_3x3()@delta);used.add(key)
  repairs.append({**t,'source_center_m':row['center_m'],'detail_vertices':len(ids),'proxy_component':None if create else key,'proxy_vertices':0 if create else len(wgroups[key]),'proxy_created':create,'proxy_match_error':None if create else score})
 ob.data.vertices.foreach_set('co',coords.ravel());ob.data.update()
wb.data.vertices.foreach_set('co',wc.ravel());wb.data.update()
for item in new_proxies:
 bm=bmesh.new()
 for point in np.unique(np.round(item['points'],4),axis=0):bm.verts.new(point)
 hull=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
 unused=set(hull.get('geom_interior',[])+hull.get('geom_unused',[]))
 if unused:bmesh.ops.delete(bm,geom=list(unused),context='VERTS')
 me=bpy.data.meshes.new('Rooted scan envelope');bm.to_mesh(me);bm.free()
 addition=bpy.data.objects.new('WB_rooted_scan',me);bpy.context.collection.objects.link(addition)
 bpy.context.view_layer.objects.active=addition
 dec=addition.modifiers.new('Envelope budget','DECIMATE');dec.ratio=min(1,80/max(1,len(me.polygons)));bpy.ops.object.modifier_apply(modifier=dec.name)
 nv=len(addition.data.vertices);nf=sum(len(p.vertices)-2 for p in addition.data.polygons)
 for row in repairs:
  if row['environment']==item['environment'] and row['component']==item['component']:row.update(proxy_vertices=nv,proxy_triangles=nf)
 report['whitebox']['parts'].append({'name':'Rooted solid scan envelope','environment':item['environment'],'source_component':item['component'],'triangles':nf})
 bpy.ops.object.select_all(action='DESELECT');wb.hide_set(False);wb.select_set(True);addition.select_set(True);bpy.context.view_layer.objects.active=wb;bpy.ops.object.join()
report['whitebox']['triangles']=sum(len(p.vertices)-2 for p in wb.data.polygons)
report['whitebox']['ratio']=report['whitebox']['triangles']/max(1,report['whitebox']['source_triangles_before_bevel'])
def export(ob,path):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
 bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
for i in sorted({t['environment'] for t in targets}):
 p=out/f'environment_{i}.fbx';export(bpy.data.objects['Environment_'+str(i)],p);report['environment'][i]['file']=str(p)
p=out/'whitebox.fbx';export(wb,p);wb.hide_set(True);wb.hide_render=True
data.setdefault('decisions',[]).append('Explicit whole-scan settlement from current visual evidence. Source-hashed job and unique detailed/structural component correspondence are retained; no paving, terrain or architecture was regenerated.')
spec=out/'scene_spec.json';write(spec,data)
report['whitebox'].update(file=str(p),manifest=str(out/'whitebox.json'),source_spec_sha256=sha(spec));report['whitebox'].pop('route_clearance',None)
write(out/'whitebox.json',report['whitebox'])
receipt={'source_report':job['source_report'],'source_report_sha256':sha(job['source_report']),'source_blend_sha256':audit['source_blend_sha256'],'job_sha256':sha(job_path),'repairs':repairs}
report['blend']=str(out/'scene.blend');report['rock_settlement']=receipt
bpy.ops.wm.save_as_mainfile(filepath=report['blend']);write(out/'report.json',report);write(out/'repair_audit.json',receipt)
write(out/'check_job.json',{'scene_spec':str(spec),'out':str(out)})
print('SETTLED_COMPLETE_ROCKS',json.dumps(repairs),flush=True)
