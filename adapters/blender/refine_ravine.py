"""Saved-scene terrain banks, scanned ecology and a paired timber crossing."""
import bpy,bmesh,json,sys,hashlib,math
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from exploration import RouteField
from route_banks import offset
from destination_details import build
from landscape_routes import rock_origin
from mesh_components import components
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise RuntimeError('Preserve previous scene revision')
source=Path(job['source_report']);report=json.loads(source.read_text());data=json.loads(Path(job['scene_spec']).read_text());spec=data['scene'];cfg=spec['composition'];field=RouteField(cfg['exploration'])
audit={'source_report':str(source),'source_report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_blend_sha256':hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest(),'banks':cfg['exploration']['route_banks'],'instances':[]}
bpy.ops.wm.open_mainfile(filepath=report['blend']);ground=bpy.data.objects['Environment_0'];wb=next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_'));changed={0}
coords=np.empty((len(ground.data.vertices),3),np.float32);ground.data.vertices.foreach_get('co',coords.ravel());deltas=np.array([offset(cfg['exploration'],field,float(v[0])/100,-float(v[1])/100) for v in coords]);coords[:,2]+=100*deltas;ground.data.vertices.foreach_set('co',coords.ravel());ground.data.update()
attr=ground.data.color_attributes.get('SurfaceWeights')
if attr:
 colors=np.empty((len(attr.data),4),np.float32);attr.data.foreach_get('color',colors.ravel());mask=deltas>.04;colors[mask,:3]=[.52,.60,.10];attr.data.foreach_set('color',colors.ravel())
wc,world,wgroups=components(wb);terrain_groups=[ids for ids in wgroups.values() if np.ptp(world[ids,0])>cfg['terrain_extent_m']*80 and np.ptp(world[ids,1])>cfg['terrain_extent_m']*80]
if len(terrain_groups)!=1:raise RuntimeError('Ambiguous structural terrain component')
ids=terrain_groups[0]
for i in ids:
 x,y=world[i,0]/100,-world[i,1]/100;wc[i,2]+=100*offset(cfg['exploration'],field,float(x),float(y))
wb.data.vertices.foreach_set('co',wc.ravel());wb.data.update()
tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],[tuple(p.vertices) for p in ground.data.polygons])
def height(x,y):
 hit=tree.ray_cast(Vector((x*100,-y*100,50000)),Vector((0,0,-1)))[0]
 if hit is None:raise RuntimeError('No terrain under ravine asset')
 return hit.z/100
audit['changed_terrain_vertices']=int(np.count_nonzero(deltas));print('BANKS_BUILT',audit['changed_terrain_vertices'],flush=True)
def make(name,v,f,colors=None,bevel=False):
 me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
 if colors:
  a=me.color_attributes.new(name='SurfaceWeights',type='FLOAT_COLOR',domain='POINT');a.data.foreach_set('color',np.asarray(colors,np.float32).ravel())
 ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
 if bevel:
  bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;mod=ob.modifiers.new('Timber and stone edges','BEVEL');mod.width=.013;mod.segments=3;mod.limit_method='ANGLE';mod.angle_limit=.74;bpy.ops.object.modifier_apply(modifier=mod.name)
 ob.data.transform(Matrix.Diagonal(Vector((100,-100,100,1))));ob.data.flip_normals();ob.data.update();return ob
added={};proxies=[];groups={}
def collect(name,v,f,material,**kw):
 vs,fs,cs=groups.setdefault(material,([],[],[]));off=len(vs);vs.extend(v);fs.extend([tuple(off+i for i in face) for face in f]);cs.extend(kw.get('colors',[(1,0,0,1)]*len(v)))
api={'cfg':{'destination_details':job['new_details']},'spec':spec,'height':height,'mesh':collect,'finish_stone':lambda ob,w:ob}
bridge=build(api)
for mat,(v,f,c) in groups.items():added.setdefault((mat,True),[]).append(make('Ravine crossing',v,f,c,True))
groups={};build(api,True)
for mat,(v,f,c) in groups.items():proxies.append(make('Crossing structure',v,f));report['whitebox']['parts'].append({'name':'WB_ravine crossing '+mat,'triangles':sum(len(face)-2 for face in f)})
library=json.loads(Path(job['library_job']).read_text())['mesh_library'];templates={};hulls={}
for item in job['instances']:
 asset=item['asset'];conf=library[asset]
 if asset not in templates:
  before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=conf['file']);imported=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
  if conf.get('variant_mode')=='assembled' and len(imported)>1:
   bpy.ops.object.select_all(action='DESELECT')
   for ob in imported:ob.select_set(True)
   bpy.context.view_layer.objects.active=imported[0];bpy.ops.object.join();imported=[bpy.context.object]
  sources=[]
  for ob in imported:
   bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;tris=sum(len(p.vertices)-2 for p in ob.data.polygons)
   if tris>conf['triangle_budget']:
    mod=ob.modifiers.new('Verified scan budget','DECIMATE');mod.ratio=conf['triangle_budget']/tris;bpy.ops.object.modifier_apply(modifier=mod.name)
   points=np.array([ob.matrix_world@v.co for v in ob.data.vertices]);lo=points.min(0);hi=points.max(0);dims=np.maximum(hi-lo,.001);origin=Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]));me=ob.data.copy();me.transform(Matrix.Diagonal(Vector((1/dims[0],1/dims[1],1/dims[2],1)))@Matrix.Translation(-origin)@ob.matrix_world);sources.append((me,dims))
  for ob in list(bpy.data.objects):
   if ob not in before:bpy.data.objects.remove(ob,do_unlink=True)
  templates[asset]=sources
 source_me,dims=templates[asset][item['variant']%len(templates[asset])];scale=item['scale'];x,y,z=item['position'];collision=item['collision']
 if not collision:
  factor=min(scale[i]/dims[i] for i in range(3));scale=[float(v*factor) for v in dims];yaw=item['yaw'];z+=height(x,y)
 else:
  q=np.array([x,y]);t=np.clip(np.sum((q-field.a[:,:2])*field.d[:,:2],axis=1)/field.lengths,0,1);near=field.a[:,:2]+field.d[:,:2]*t[:,None];i=int(np.argmin(np.sum((q-near)**2,axis=1)));yaw=math.atan2(field.d[i,1],field.d[i,0])
  z,grounding=rock_origin([v.co[:] for v in source_me.vertices],[x,y,0],scale,yaw,height)
 m=Matrix.Diagonal(Vector((100,-100,100,1)))@Matrix.Translation(Vector((x,y,z)))@Matrix.Rotation(yaw,4,'Z')@Matrix.Diagonal(Vector((*scale,1)))
 me=source_me.copy();me.transform(m);me.flip_normals();me.update();ob=bpy.data.objects.new('Ravine '+asset,me);bpy.context.collection.objects.link(ob);added.setdefault((conf['material_id'],collision),[]).append(ob)
 if collision:
  key=(asset,item['variant']%len(templates[asset]))
  if key not in hulls:
   bm=bmesh.new();bm.from_mesh(source_me);hull=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False);remove=set(hull.get('geom_interior',[])+hull.get('geom_unused',[]))
   if remove:bmesh.ops.delete(bm,geom=list(remove),context='VERTS')
   me=bpy.data.meshes.new('Rock companion template');bm.to_mesh(me);bm.free();hulls[key]=me
  me=hulls[key].copy();me.transform(m);me.flip_normals();me.update();ob=bpy.data.objects.new('WB ravine rock',me);bpy.context.collection.objects.link(ob);proxies.append(ob);report['whitebox']['parts'].append({'name':'WB_ravine outcrop '+asset,'triangles':sum(len(p.vertices)-2 for p in me.polygons)})
 audit['instances'].append({**item,'resolved_z':float(z),'yaw':float(yaw),'resolved_scale':scale})
def join(target,objects):
 bpy.ops.object.select_all(action='DESELECT');target.hide_set(False);target.select_set(True)
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=target;bpy.ops.object.join()
for (mat,col),objects in added.items():
 matches=[i for i,e in enumerate(report['environment']) if e['material']==mat and e['collision']==col]
 if len(matches)!=1:raise RuntimeError('Missing dedicated material group '+mat)
 i=matches[0];join(bpy.data.objects['Environment_'+str(i)],objects);changed.add(i)
join(wb,proxies)
audit['bridge_counts']=bridge['counts'];audit['changed_groups']=sorted(changed)
def export(ob,path):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
for i in sorted(changed):
 ob=bpy.data.objects['Environment_'+str(i)];path=out/f'environment_{i}.fbx';export(ob,path);report['environment'][i].update(file=str(path),triangles=sum(len(p.vertices)-2 for p in ob.data.polygons))
path=out/'whitebox.fbx';export(wb,path);wb.hide_set(True);wb.hide_render=True
sp=out/'scene_spec.json';sp.write_text(json.dumps(data,indent=2),encoding='utf-8');report['whitebox'].update(file=str(path),manifest=str(out/'whitebox.json'),triangles=sum(len(p.vertices)-2 for p in wb.data.polygons),source_spec_sha256=hashlib.sha256(sp.read_bytes()).hexdigest());report['whitebox'].pop('route_clearance',None)
for i,p in enumerate(report['whitebox']['parts']):p['id']=i
report['whitebox']['omitted_small_groundcover_additions']=report['whitebox'].get('omitted_small_groundcover_additions',0)+sum(not i['collision'] for i in job['instances'])
(out/'whitebox.json').write_text(json.dumps(report['whitebox'],indent=2),encoding='utf-8');report['blend']=str(out/'scene.blend');report['ravine_refinement']=audit;bpy.ops.wm.save_as_mainfile(filepath=report['blend']);(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(out/'repair_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');(out/'check_job.json').write_text(json.dumps({'scene_spec':str(sp),'out':str(out)},indent=2),encoding='utf-8');print('RAVINE_COMPLETE',flush=True)
