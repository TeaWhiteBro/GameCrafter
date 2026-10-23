"""Replace legacy open-joint apse courses and their matching coarse wall rings.

Selection uses each configured wall's radius, layer height and complete islands.
Expected old-course counts are reconstructed before any mutation.
"""
import bpy,bmesh,json,sys,hashlib,math
from pathlib import Path
import numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mesh_components import components
from curved_wall import build_wall

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2),encoding='utf-8')
jobpath=Path(sys.argv[sys.argv.index('--')+1]);job=read(jobpath)
source=Path(job['source_report']);report=read(source);data=read(job['scene_spec'])
assert sha(source)==job['source_report_sha256'] and sha(report['blend'])==job['source_blend_sha256']
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise RuntimeError('Preserve completed scene revision')
items=data['scene']['composition']['apses']
bpy.ops.wm.open_mainfile(filepath=report['blend'])
wb=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_')]
assert len(wb)==1;wb=wb[0];changes={};selections=[]

def old_count(item,proxy):
 r=item['radius'];h=item['height'];rot=math.radians(item.get('rotation_deg',0));op=math.radians(item.get('opening_degrees',100))
 a0=math.pi/2+op/2+rot;a1=math.pi/2+math.tau-op/2+rot
 n=80 if proxy else max(12,round((a1-a0)*r/.72));rows=1 if proxy else round(h/.37);count=0
 for row in range(rows):
  for k in range(0 if proxy else (-1 if row%2 else 0),n):
   aa=max(a0,a0+(k+(0 if proxy else .5*(row%2)))*(a1-a0)/n);bb=min(a1,a0+(k+1+(0 if proxy else .5*(row%2)))*(a1-a0)/n)
   if bb-aa<.005 and not proxy:continue
   ang=(aa+bb)/2;win=min(abs(math.atan2(math.sin(ang-w),math.cos(ang-w)))*r for w in [rot+math.pi,rot+1.5*math.pi,rot+2*math.pi])
   z=h/rows*(row+.5)
   if proxy:count+=2 if win<.45 else 1
   elif not (win<.45 and 2<z<h-1.1+math.sqrt(max(0,.45**2-win**2))):count+=1
 return count

def find_ids(ob,these,proxy):
 _,world,groups=components(ob);metric=world*np.array([.01,-.01,.01]);allids=[]
 for number,item in these:
  cx,cy=item['center'];r=item['radius'];h=item['height'];base=item.get('base_z',.08);hh=h/round(h/.37)
  found=[]
  for key,ids in groups.items():
   pts=metric[ids];zz=pts[:,2];rad=np.linalg.norm(pts[:,:2]-[cx,cy],axis=1)
   if rad.min()<r-.312 or rad.max()>r+.306 or zz.min()<base-.003 or zz.max()>base+h+.003:continue
   if proxy:
    good=any(abs(zz.min()-base-lo)<.004 and abs(zz.max()-base-hi)<.004 for lo,hi in [(0,h),(0,2),(h-.9,h)])
   else:
    row=(zz.min()+zz.max())*.5-base
    good=abs(np.ptp(zz)-(hh-.013))<.004 and abs(row/hh-.5-round(row/hh-.5))<.005
   if good:found.append(key);allids.extend(ids.tolist())
  expected=old_count(item,proxy)
  selections.append({'object':ob.name,'apse':number,'proxy':proxy,'components':len(found),'expected':expected,'vertices':sum(len(groups[k]) for k in found)})
  if len(found)!=expected:raise RuntimeError('Ambiguous legacy wall selection: '+str(selections[-1]))
 return allids

materials={item.get('material',data['scene']['path_material']) for item in items}
for mat in materials:
 ids=[i for i,e in enumerate(report['environment']) if e['material']==mat and e['collision']]
 assert len(ids)==1;i=ids[0];ob=bpy.data.objects['Environment_'+str(i)]
 changes[i]=(ob,find_ids(ob,[(j,it) for j,it in enumerate(items) if it.get('material',data['scene']['path_material'])==mat],False))
white_ids=find_ids(wb,list(enumerate(items)),True)
write(out/'selection.json',selections);print('WALL_SELECTION',json.dumps(selections),flush=True)

def delete(ob,ids):
 bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.verts[i] for i in ids],context='VERTS');bm.to_mesh(ob.data);bm.free();ob.data.update()
def add(ob,item,proxy=False):
 def emit(name,vs,fs,mat):
  me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
  bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
  marker=me.attributes.new(name='WallContinuity',type='INT',domain='FACE');marker.data.foreach_set('value',np.ones(len(me.polygons),np.int32))
  if not proxy:
   attr=me.color_attributes.new(name='SurfaceWeights',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',np.tile([.96,.04,0,1],len(me.vertices)))
  me.transform(Matrix.Diagonal(Vector((100,-100,100,1))));me.flip_normals();me.update()
  addition=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(addition)
  bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);addition.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
 build_wall(item,emit,item.get('material',data['scene']['path_material']),proxy)
for i,(ob,ids) in changes.items():
 delete(ob,ids)
 for item in items:
  if item.get('material',data['scene']['path_material'])==report['environment'][i]['material']:add(ob,item)
delete(wb,white_ids)
for item in items:add(wb,item,True)

def tree(objects):
 vs=[];fs=[]
 for ob in objects:
  k=len(vs);vs.extend(ob.matrix_world@v.co for v in ob.data.vertices)
  marker=ob.data.attributes.get('WallContinuity');assert marker is not None
  fs.extend(tuple(k+i for i in f.vertices) for f in ob.data.polygons if marker.data[f.index].value==1)
 return BVHTree.FromPolygons(vs,fs),vs,fs
ht=tree([ob for ob,ids in changes.values()]);lt=tree([wb]);high=ht[0];low=lt[0];samples=0;failures=[]
for ai,item in enumerate(items):
 cx,cy=item['center'];r=item['radius'];h=item['height'];base=item.get('base_z',.08);rot=math.radians(item.get('rotation_deg',0));op=math.radians(item.get('opening_degrees',100))
 aa=math.pi/2+op/2+rot;bb=math.pi/2+math.tau-op/2+rot
 for a in np.linspace(aa+.09,bb-.09,173):
  dist=min(abs(a-w)*r for w in [rot+math.pi,rot+1.5*math.pi,rot+2*math.pi]);top=h-1.1+math.sqrt(max(0,.45*.45-dist*dist))
  for z in np.arange(.19,h-.06,.137):
   # Avoid classifying the deliberately tessellated aperture's boundary as drift.
   if abs(dist-.45)<.035 or abs(z-2)<.025 or abs(z-top)<.025:continue
   expected=not(dist<.45 and 2<z<top)
   o=Vector(((cx+(r-.32)*math.cos(a))*100,-(cy+(r-.32)*math.sin(a))*100,(base+z)*100));d=Vector((math.cos(a),-math.sin(a),0))
   hits=[t.ray_cast(o,d,64) for t in [high,low]];actual=[hit[0] is not None for hit in hits];samples+=1
   if actual!=[expected,expected]:
    record={'apse':ai,'angle':float(a),'z':float(z),'expected_solid':expected,'actual':actual}
    if len(failures)<15:
     record['hit_faces']=[{'point':list(hit[0]),'face':[list(geo[1][i]) for i in geo[2][hit[2]]]} if hit[0] is not None else None for hit,geo in zip(hits,[ht,lt])]
    failures.append(record)
audit={'samples':samples,'failures':failures,'passed':not failures,'method':'Independent radial triangle rays through the rebuilt detailed and structural wall face groups, tagged WallContinuity in the saved blend. Includes former mortar seams and deliberate arched apertures. Full-scene probes are retained as diagnostics: other aisle roofs, piers and the bell tower can legitimately stand behind or intersect a window. This test measures the wall shell itself; whole-scene composition and portals are checked separately.'}
write(out/'wall_aperture_audit.json',audit)
if failures:raise RuntimeError('Wall aperture audit failed: '+str(failures[:3]))
print('WALL_APERTURES_VERIFIED',samples,flush=True)

def export(ob,path):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
 bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
for i,(ob,_) in changes.items():
 p=out/f'environment_{i}.fbx';export(ob,p);report['environment'][i].update(file=str(p),triangles=sum(len(f.vertices)-2 for f in ob.data.polygons))
p=out/'whitebox.fbx';export(wb,p);wb.hide_set(True);wb.hide_render=True
data.setdefault('decisions',[]).append('Replaced apse open-joint courses with continuous masonry and explicit arched apertures in detail and structural companion. Source-hashed legacy selection and independent wall/aperture rays are preserved.')
specpath=out/'scene_spec.json';write(specpath,data)
report['whitebox'].update(file=str(p),manifest=str(out/'whitebox.json'),triangles=sum(len(f.vertices)-2 for f in wb.data.polygons),source_spec_sha256=sha(specpath));report['whitebox'].pop('route_clearance',None)
report['whitebox']['parts'].append({'name':'Rebuilt continuous apse walls','replaces':'legacy apse wall rings','count':len(items)})
write(out/'whitebox.json',report['whitebox'])
receipt={'source_report':str(source),'source_report_sha256':sha(source),'source_blend_sha256':job['source_blend_sha256'],'job_sha256':sha(jobpath),'selection':selections,'wall_audit':audit}
report['blend']=str(out/'scene.blend');report['curved_wall_refinement']=receipt
bpy.ops.wm.save_as_mainfile(filepath=report['blend']);write(out/'report.json',report);write(out/'repair_audit.json',receipt);write(out/'check_job.json',{'scene_spec':str(specpath),'out':str(out)})
print('CURVED_WALLS_COMPLETE',flush=True)
