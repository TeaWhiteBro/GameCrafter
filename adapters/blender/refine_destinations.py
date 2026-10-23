"""Add data-authored destinations to a saved scene and its structural companion.

Source report/blend hashes, whole-component transformations and every planting
are recorded. Unchanged geometry and UVs are retained in the isolated revision.
"""
import bpy,bmesh,json,sys,hashlib,random,math
from pathlib import Path
import numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from destination_details import build
from island_transform import move_islands
from mesh_components import components
from exploration import RouteField
from landscape_routes import build_paving,terrain_mask

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8-sig'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise RuntimeError('Preserve completed revision')
source=Path(job['source_report']);report=json.loads(source.read_text(encoding='utf-8'))
data=json.loads(Path(job['scene_spec']).read_text(encoding='utf-8'));spec=data['scene'];cfg=spec['composition']
audit={'source_report':str(source),'source_report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_blend_sha256':hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest(),'transforms':[]}
bpy.ops.wm.open_mainfile(filepath=report['blend']);terrain=bpy.data.objects['Environment_0']
ground=BVHTree.FromPolygons([terrain.matrix_world@v.co for v in terrain.data.vertices],[tuple(p.vertices) for p in terrain.data.polygons])
def height(x,y):
 hit=ground.ray_cast(Vector((x*100,-y*100,50000)),Vector((0,0,-1)))[0]
 if hit is None:raise RuntimeError('Missing ground')
 return hit.z/100
wb=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_')];assert len(wb)==1;wb=wb[0]
changed=set();report['materials'].update(spec['materials'])
repair=job.get('gallery_transform')
if repair:
 moved={}
 for i,e in enumerate(report['environment']):
  if e['material'] in repair['materials']:
   count=move_islands(bpy.data.objects['Environment_'+str(i)],repair,repair['delta_m'])
   if count:changed.add(i);moved[str(i)]=count
 moved['whitebox']=move_islands(wb,repair,repair['delta_m'])
 if len(moved)<2 or not moved['whitebox']:raise RuntimeError('Gallery selection missed companion')
 for p in report['whitebox']['portal_tests']:
  x,y,z=p['origin_m'];cx,cy,_=repair['center_m'];hx,hy=repair['box_half_extent_m']
  if abs(x-cx)<hx and abs(y-cy)<hy and repair['z_range_m'][0]<z<repair['z_range_m'][1]:p['origin_m'][2]+=repair['delta_m'][2]
 audit['transforms'].append({'kind':'gallery_elevation','selection':repair,'vertices':moved})
 print('GALLERY_RAISED',moved,flush=True)
# Open the background of the viewpoint by lowering whole, hash-verified masses.
ra=json.loads(Path(job['rock_audit']).read_text());assert ra['source_report_sha256']==audit['source_report_sha256'] and ra['source_blend_sha256']==audit['source_blend_sha256']
lo,hi=job['vista_region_m'];selected=[r for r in ra['components'] if all(lo[i]<=r['center_m'][i]<=hi[i] for i in [0,1]) and r['bounds_m']['max'][2]>job['vista_top_m']+1]
wc,ww,wgroups=components(wb);candidates=[]
for key,ids in wgroups.items():
 if len(ids)<12:continue
 pts=ww[ids]
 if np.ptp(pts[:,0])>6000 or np.ptp(pts[:,1])>6000:continue
 candidates.append((key,np.r_[pts.min(0),pts.max(0)]))
used=set()
for i in sorted({r['environment'] for r in selected}):
 ob=bpy.data.objects['Environment_'+str(i)];coords,world,groups=components(ob,True)
 for r in [r for r in selected if r['environment']==i]:
  ids=groups[r['component']];pts=world[ids];bounds=np.r_[pts.min(0),pts.max(0)];size=np.maximum(pts.max(0)-pts.min(0),20)
  ranked=sorted((float(np.linalg.norm((b-bounds)/np.r_[size,size])),k) for k,b in candidates if k not in used)
  score,key=ranked[0]
  if score>.25 or (len(ranked)>1 and ranked[1][0]-score<.015):raise RuntimeError('Ambiguous vista rock companion')
  dz=job['vista_top_m']-r['bounds_m']['max'][2];coords[ids]+=np.asarray(ob.matrix_world.inverted().to_3x3()@Vector((0,0,dz*100)))
  wc[wgroups[key]]+=np.asarray(wb.matrix_world.inverted().to_3x3()@Vector((0,0,dz*100)));used.add(key)
  audit['transforms'].append({'kind':'vista_rock','environment':i,'component':r['component'],'center_m':r['center_m'],'delta_z_m':dz,'proxy_component':key,'match_error':score})
 ob.data.vertices.foreach_set('co',coords.ravel());ob.data.update();changed.add(i)
wb.data.vertices.foreach_set('co',wc.ravel());wb.data.update()
print('VISTA_OPENED',len(selected),flush=True)

def make(name,vs,fs,colors=None,bevel=False):
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
 if colors:
  attr=me.color_attributes.new(name='SurfaceWeights',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',np.asarray(colors,np.float32).ravel())
 ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
 if bevel:
  bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
  mod=ob.modifiers.new('Finished structural edges','BEVEL');mod.width=.013;mod.segments=3;mod.limit_method='ANGLE';mod.angle_limit=.74;bpy.ops.object.modifier_apply(modifier=mod.name)
 me=ob.data;me.transform(Matrix.Diagonal(Vector((100,-100,100,1))));me.flip_normals();me.update();return ob
def append(ob,addition):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);addition.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
def index(mat,collision=True):
 matches=[i for i,e in enumerate(report['environment']) if e['material']==mat and e['collision']==collision]
 if len(matches)>1:raise RuntimeError('Ambiguous material group')
 if matches:return matches[0]
 i=len(report['environment']);cls=report['materials'][mat]['semantic_class'];sid={'architecture':3,'terrain':1,'vegetation':5,'prop':6}[cls]
 ob=bpy.data.objects.new('Environment_'+str(i),bpy.data.meshes.new(mat));bpy.context.collection.objects.link(ob)
 report['environment'].append({'material':mat,'collision':collision,'semantic_id':sid});return i
groups={}
def collect(name,vs,fs,material,**kw):
 v,f,c=groups.setdefault(material,([],[],[]));off=len(v);v.extend(vs);f.extend([tuple(off+i for i in face) for face in fs]);c.extend(kw.get('colors',[(1,0,0,1)]*len(vs)))
api={'cfg':cfg,'spec':spec,'height':height,'mesh':collect,'finish_stone':lambda ob,w:ob}
result=build(api);report['destination_details']=result
for mat,(v,f,c) in groups.items():
 i=index(mat);append(bpy.data.objects['Environment_'+str(i)],make('Destination architecture',v,f,c,True));changed.add(i)
groups={};build({**api,'mesh':collect},proxy=True)
for mat,(v,f,c) in groups.items():
 append(wb,make('Destination companion',v,f));report['whitebox']['parts'].append({'name':'WB_destination '+mat,'triangles':sum(len(face)-2 for face in f)})
print('STRUCTURES_ADDED',result['counts'],flush=True)
# Rebuild road surfacing. Earth ravine retains continuous terrain instead of slabs.
groups={};field=RouteField(cfg['exploration'])
count=build_paving({'route_field':field,'rng':random.Random(417),'height':height,'mesh':collect,'finish_stone':lambda ob,w:ob})
for mat,(v,f,c) in groups.items():
 i=index(mat);target=bpy.data.objects['Environment_'+str(i)];fresh=make('Refined route surface',v,f,c);target.data=fresh.data;bpy.data.objects.remove(fresh,do_unlink=True);changed.add(i)
attr=terrain.data.color_attributes.get('SurfaceWeights')
if attr:
 colors=np.empty((len(attr.data),4),np.float32);attr.data.foreach_get('color',colors.ravel())
 for i,v in enumerate(terrain.data.vertices):
  x,y=v.co.x/100,-v.co.y/100;dist,z,width,route=field.query(x,y)
  if route>=0 and field.routes[route][0].get('id')=='lower_ravine' and dist<width/2+.8:
   colors[i,:3]=terrain_mask(field,x,y,*map(float,colors[i,:3]))
 attr.data.foreach_set('color',colors.ravel());changed.add(0)
report['exploration']['paving_slabs']=count;report['exploration']['places']=cfg['exploration']['places']
# Whole-plant scans: retain original UVs and aspect ratio at the authored soil top.
library=json.loads(Path(job['library_job']).read_text())['mesh_library'];templates={}
for p in result['plantings']:
 asset=p['asset'];conf=library[asset]
 if asset not in templates:
  before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=conf['file']);imported=[o for o in bpy.data.objects if o not in before and o.type=='MESH'];sources=[]
  if conf.get('variant_mode')!='separate' and len(imported)>1:
   bpy.ops.object.select_all(action='DESELECT')
   for ob in imported:ob.select_set(True)
   bpy.context.view_layer.objects.active=imported[0];bpy.ops.object.join();imported=[bpy.context.object]
  for ob in imported:
   bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
   triangles=sum(len(f.vertices)-2 for f in ob.data.polygons)
   if triangles>conf['triangle_budget']:
    mod=ob.modifiers.new('Whole plant budget','DECIMATE');mod.ratio=conf['triangle_budget']/triangles;bpy.ops.object.modifier_apply(modifier=mod.name)
   coords=np.array([ob.matrix_world@v.co for v in ob.data.vertices]);low=coords.min(0);high=coords.max(0);dims=np.maximum(high-low,.001);origin=Vector(((high[0]+low[0])/2,(high[1]+low[1])/2,low[2]))
   me=ob.data.copy();me.transform(Matrix.Translation(-origin)@ob.matrix_world);sources.append((me,dims))
  for ob in list(bpy.data.objects):
   if ob not in before:bpy.data.objects.remove(ob,do_unlink=True)
  templates[asset]=sources
 me,dims=templates[asset][p['variant']%len(templates[asset])];me=me.copy();s=p['size']/max(dims)
 me.transform(Matrix.Diagonal(Vector((100,-100,100,1)))@Matrix.Translation(Vector(p['position']))@Matrix.Rotation(p['yaw'],4,'Z')@Matrix.Diagonal(Vector((s,s,s,1))));me.flip_normals();me.update()
 ob=bpy.data.objects.new('Herb plant',me);bpy.context.collection.objects.link(ob);i=index(conf['material_id'],False);append(bpy.data.objects['Environment_'+str(i)],ob);changed.add(i)
audit['plantings']=result['plantings'];audit['destination_counts']=result['counts'];audit['paving_slabs']=count

def export(ob,path):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
 bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
for i in sorted(changed):
 ob=bpy.data.objects['Environment_'+str(i)];path=out/f'environment_{i}.fbx';export(ob,path);report['environment'][i].update(file=str(path),triangles=sum(len(p.vertices)-2 for p in ob.data.polygons))
path=out/'whitebox.fbx';export(wb,path);wb.hide_set(True);wb.hide_render=True
specpath=out/'scene_spec.json';specpath.write_text(json.dumps(data,indent=2),encoding='utf-8')
report['whitebox'].update(file=str(path),manifest=str(out/'whitebox.json'),triangles=sum(len(p.vertices)-2 for p in wb.data.polygons),source_spec_sha256=hashlib.sha256(specpath.read_bytes()).hexdigest());report['whitebox'].pop('route_clearance',None)
for i,part in enumerate(report['whitebox']['parts']):part['id']=i
(out/'whitebox.json').write_text(json.dumps(report['whitebox'],indent=2),encoding='utf-8')
report['blend']=str(out/'scene.blend');report['destination_refinement']=audit;bpy.ops.wm.save_as_mainfile(filepath=report['blend'])
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(out/'repair_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');(out/'check_job.json').write_text(json.dumps({'scene_spec':str(specpath),'out':str(out)},indent=2),encoding='utf-8')
print('DESTINATIONS_COMPLETE',flush=True)
