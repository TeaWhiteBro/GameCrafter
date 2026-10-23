"""Source-preserving roof closure and road bedding repair against saved terrain."""
import bpy,bmesh,json,sys,hashlib,random,math
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from exploration import RouteField
from landscape_routes import build_paving
from courtyard import build_arcades

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8-sig'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise RuntimeError('Preserve previous revision')
source=Path(job['source_report']);report=json.loads(source.read_text(encoding='utf-8-sig'))
data=json.loads(Path(job['scene_spec']).read_text(encoding='utf-8-sig'));cfg=data['scene']['composition']
receipt={'source_report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_blend_sha256':hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest(),'source_report':str(source),'repairs':[]}
bpy.ops.wm.open_mainfile(filepath=report['blend'])
ground=bpy.data.objects['Environment_0']
tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],[tuple(p.vertices) for p in ground.data.polygons])
def height(x,y):
    hit=tree.ray_cast(Vector((x*100,-y*100,50000)),Vector((0,0,-1)))[0]
    if hit is None:raise RuntimeError('Missing terrain')
    return hit.z/100
def make_mesh(name,vs,fs,colors=None):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    if colors:
        attr=me.color_attributes.new(name='SurfaceWeights',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',np.asarray(colors,np.float32).ravel())
    me.transform(Matrix.Diagonal(Vector((100,-100,100,1))));me.flip_normals();me.update();return me
changed=set()
def material_index(mat):
    found=[i for i,e in enumerate(report['environment']) if e['material']==mat]
    if len(found)!=1:raise RuntimeError('Expected dedicated material '+mat)
    return found[0]
vs=[];fs=[];colors=[]
def paving(name,verts,faces,material,**kw):
    assert material==cfg['exploration']['paving_material'];offset=len(vs)
    vs.extend(verts);fs.extend([tuple(offset+i for i in f) for f in faces]);colors.extend(kw['colors'])
count=build_paving({'route_field':RouteField(cfg['exploration']),'rng':random.Random(job.get('seed',417)),'height':height,'mesh':paving,'finish_stone':lambda ob,w:ob})
idx=material_index(cfg['exploration']['paving_material']);ob=bpy.data.objects['Environment_'+str(idx)]
ob.data=make_mesh('Continuous fitted roads and arrivals',vs,fs,colors);ob.matrix_world=Matrix.Identity(4);changed.add(idx)
receipt['paving_slabs']=count;receipt['repairs'].append({'kind':'continuous_bedding','faces':len(fs),'route_edges':len(cfg['exploration']['routes']),'terrain_grid_m':cfg['exploration'].get('bedding_grid_m',.30)})
print('PAVING_COMPLETE',count,len(fs),flush=True)

def local(points,run):
    a=np.asarray(run['start']);d=np.asarray(run['end'])-a;length=np.linalg.norm(d);t=d/length;n=np.array([-t[1],t[0]])
    q=points[:,:2]-a;x=q@t;y=q@n;h=run.get('height',4.5);base=run.get('base_z',.08);width=run.get('width',2.5);slope=run.get('roof_rise',.62)/width
    return x,y,points[:,2]-(base+h+.57+y*slope),length,width
def remove_roofs(ob,proxy=False):
    bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.ensure_lookup_table();visited=set();remove=[];components=0
    for start in bm.verts:
        if start in visited:continue
        stack=[start];part=[];visited.add(start)
        while stack:
            v=stack.pop();part.append(v)
            for e in v.link_edges:
                other=e.other_vert(v)
                if other not in visited:visited.add(other);stack.append(other)
        if len(part)>200:continue
        pts=np.array([ob.matrix_world@v.co for v in part])*[.01,-.01,.01]
        for run in cfg['arcades']:
            x,y,z,length,width=local(pts,run)
            zlo,zhi=(.079,.201) if proxy else (-.025,.25)
            if x.min()>=-.04 and x.max()<=length+.04 and y.min()>=-.85 and y.max()<=width+.85 and z.min()>=zlo and z.max()<=zhi:
                remove.extend(part);components+=1;break
    bmesh.ops.delete(bm,geom=remove,context='VERTS');bm.to_mesh(ob.data);bm.free();ob.data.update()
    return components
roof_mats={r.get('roof_material',r.get('trim_material',r.get('material'))) for r in cfg['arcades']}
roof_vertices={m:[] for m in roof_mats};roof_faces={m:[] for m in roof_mats}
def roof_mesh(name,verts,faces,material,**kw):
    if name!='Curved clay roof tile':return
    v=roof_vertices[material];f=roof_faces[material];offset=len(v);v.extend(verts);f.extend([tuple(offset+i for i in face) for face in faces])
removed={}
for mat in roof_mats:
    idx=material_index(mat);removed[mat]=remove_roofs(bpy.data.objects['Environment_'+str(idx)]);changed.add(idx)
    if not removed[mat]:raise RuntimeError('No old roof tiles located')
for r in cfg['arcades']:r['roof_openings']=[];r['broken_end']=False
noop=lambda *a,**k:None
build_arcades({'cfg':{**cfg,'scatter':{}},'spec':data['scene'],'rng':random.Random(job.get('seed',417)), 'block':noop,'mesh':roof_mesh,'finish_stone':lambda ob,w:ob,'arch':noop,'cylinder':noop,'ring':noop,'instance':noop,'height':height})
def append(ob,me):
    added=bpy.data.objects.new('repair addition',me);bpy.context.collection.objects.link(added)
    bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);added.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
for mat in roof_mats:
    idx=material_index(mat);append(bpy.data.objects['Environment_'+str(idx)],make_mesh('Complete arcade roof',roof_vertices[mat],roof_faces[mat]))
wb=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_')];assert len(wb)==1;wb=wb[0]
old_wb=remove_roofs(wb,True)
old_parts=[p for p in report['whitebox']['parts'] if p['name'].startswith('WB_roof envelope')]
if old_wb!=len(old_parts):raise RuntimeError('Proxy roof count mismatch '+str((old_wb,len(old_parts))))
report['whitebox']['parts']=[p for p in report['whitebox']['parts'] if p not in old_parts]
vs=[];fs=[];F=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
for run in cfg['arcades']:
    a=np.asarray(run['start']);d=np.asarray(run['end'])-a;length=np.linalg.norm(d);t=d/length;n=np.array([-t[1],t[0]]);w=run.get('width',2.5);s=run.get('roof_rise',.62)/w;z=run.get('base_z',.08)+run.get('height',4.5)+.65
    off=len(vs)
    for zz in [0,.12]:
        for x,y in [(0,-.38),(length,-.38),(length,w+.38),(0,w+.38)]:
            p=a+t*x+n*y;vs.append((p[0],p[1],z+y*s+zz))
    fs.extend([tuple(off+i for i in f) for f in F]);report['whitebox']['parts'].append({'name':'WB_roof envelope repaired','triangles':12})
append(wb,make_mesh('Closed roof companion',vs,fs));receipt['repairs'].append({'kind':'closed_arcade_roofs','removed_tile_components':removed,'closed_roofs':len(cfg['arcades']),'removed_proxy_envelopes':old_wb})
print('ROOF_COMPLETE',json.dumps(receipt['repairs'][-1]),flush=True)
def export(ob,path):
    bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
for i in sorted(changed):
    ob=bpy.data.objects['Environment_'+str(i)];path=out/f'environment_{i}.fbx';export(ob,path);report['environment'][i].update(file=str(path),triangles=sum(len(p.vertices)-2 for p in ob.data.polygons))
path=out/'whitebox.fbx';export(wb,path);wb.hide_set(True);wb.hide_render=True
data.setdefault('decisions',[]).append('Close repeated arcade roof gaps with continuous clay tiles and matching structural envelopes. Unify route and destination bedding on one terrain-fitted grid with buried shoulders, retaining detailed stones and separate earth paths.')
spec=out/'scene_spec.json';spec.write_text(json.dumps(data,indent=2),encoding='utf-8')
report['whitebox'].update(file=str(path),manifest=str(out/'whitebox.json'),triangles=sum(len(p.vertices)-2 for p in wb.data.polygons),source_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest());report['whitebox'].pop('route_clearance',None)
for i,part in enumerate(report['whitebox']['parts']):part['id']=i
(out/'whitebox.json').write_text(json.dumps(report['whitebox'],indent=2),encoding='utf-8')
report['exploration']['paving_slabs']=count;report['blend']=str(out/'scene.blend');report['surface_refinement']=receipt
bpy.ops.wm.save_as_mainfile(filepath=report['blend'])
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(out/'repair_audit.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');(out/'check_job.json').write_text(json.dumps({'scene_spec':str(spec),'out':str(out)},indent=2),encoding='utf-8')
print('REFINEMENT_COMPLETE',flush=True)
