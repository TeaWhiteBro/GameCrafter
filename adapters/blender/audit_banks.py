"""Independent detailed/proxy terrain comparison in locally refined regions."""
import bpy,json,sys,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mesh_components import components
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text());report=json.loads(Path(job['report']).read_text());cfg=json.loads(Path(job['scene_spec']).read_text())['scene']['composition'];bpy.ops.wm.open_mainfile(filepath=report['blend'])
ground=bpy.data.objects['Environment_0'];wb=next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_'))
high=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],[tuple(p.vertices) for p in ground.data.polygons]);wc,world,groups=components(wb)
found=[ids for ids in groups.values() if np.ptp(world[ids,0])>cfg['terrain_extent_m']*80 and np.ptp(world[ids,1])>cfg['terrain_extent_m']*80]
assert len(found)==1;ids=found[0];lookup=np.full(len(world),-1,np.int32);lookup[ids]=np.arange(len(ids));faces=[]
for p in wb.data.polygons:
 f=lookup[np.array(p.vertices)]
 if np.all(f>=0):faces.append(tuple(int(v) for v in f))
low=BVHTree.FromPolygons([Vector(v) for v in world[ids]],faces);errors=[]
for bank in cfg['exploration']['route_banks']:
 cx,cy=bank['center'];rx,ry=bank['radii']
 for x in np.arange(cx-rx,cx+rx,.5):
  for y in np.arange(cy-ry,cy+ry,.5):
   if ((x-cx)/rx)**2+((y-cy)/ry)**2>1:continue
   origin=Vector((x*100,-y*100,50000));a=high.ray_cast(origin,Vector((0,0,-1)))[0];b=low.ray_cast(origin,Vector((0,0,-1)))[0]
   if a is None or b is None:raise RuntimeError('Missing detailed or structural bank terrain')
   errors.append(abs(a.z-b.z)/100)
result={'samples':len(errors),'p95_error_m':float(np.percentile(errors,95)),'max_error_m':max(errors),'passed':float(np.percentile(errors,95))<=.18,'source_report_sha256':hashlib.sha256(Path(job['report']).read_bytes()).hexdigest(),'source_blend_sha256':hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest(),'method':'Independent BVH heights from detailed terrain and uniquely selected structural terrain component, sampled every 0.5m inside each edited region.'}
Path(job['out']).write_text(json.dumps(result,indent=2),encoding='utf-8');print('BANK_AUDIT',result,flush=True)
if not result['passed']:raise SystemExit(2)
