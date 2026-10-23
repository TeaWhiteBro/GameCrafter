"""Independent clearance probe against the saved/exported scene geometry.

Run Blender --background --python check_routes.py -- <scene job.json>.
This is also usable for scenes authored before the inline route validator.
"""
import bpy,json,sys,math,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from exploration import RouteField
from walk_support import sample as walking_support

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
out=Path(job['out']);report_path=out/'report.json';report=json.loads(report_path.read_text())
spec=json.loads(Path(job['scene_spec']).read_text())['scene'];field=RouteField(spec['composition']['exploration'])
bpy.ops.wm.open_mainfile(filepath=report['blend'])
def tree(objects):
    vs=[];fs=[]
    for ob in objects:
        start=len(vs);vs.extend([ob.matrix_world@v.co for v in ob.data.vertices])
        fs.extend([tuple(start+i for i in p.vertices) for p in ob.data.polygons])
    return BVHTree.FromPolygons(vs,fs)
objects=[]
for i,e in enumerate(report['environment']):
    if not e['collision']:continue
    names=['Environment_'+str(i)+'_Instance_'+str(j) for j in range(len(e['instances']))] if 'instances' in e else ['Environment_'+str(i)]
    objects.extend(bpy.data.objects[name] for name in names)
ground=[bpy.data.objects['Environment_'+str(i)] for i,e in enumerate(report['environment']) if e['material']==spec['floor_material'] and e['collision']]
high=tree(objects);terrain=tree(ground)
companions=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('WB_')]
if len(companions)!=1:raise RuntimeError('Expected one structural companion')
low=tree(companions)
for portal in report['whitebox'].get('portal_tests',[]):
    x,y,z=portal['origin_m'];dx,dy,dz=portal['direction'];origin=Vector((x*100,-y*100,z*100));direction=Vector((dx,-dy,dz))
    portal['source_clear']=high.ray_cast(origin,direction,portal['distance_m']*100)[0] is None
    portal['whitebox_clear']=low.ray_cast(origin,direction,portal['distance_m']*100)[0] is None
    if portal['source_clear'] and not portal['whitebox_clear']:raise RuntimeError('Structural companion blocked an open detailed portal')
def position(x,y,expected_z,elevation):
    def cast(origin,direction,distance):return high.ray_cast(Vector(origin),Vector(direction),distance)
    ground_hit=terrain.ray_cast(Vector((x*100,-y*100,10000)),Vector((0,0,-1)),20000)[0]
    if ground_hit is None:raise ValueError('Missing physical terrain beneath route')
    z=walking_support(cast,x*100,-y*100,max(expected_z*100,ground_hit.z),100)
    return Vector((x*100,-y*100,z+elevation*100))
samples=0;hits=[];support_failures=[]
for ri,(route,points) in enumerate(field.routes):
    for i in range(len(points)-1):
        a,b=points[i],points[i+1];dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        for offset in [-.4,0,.4]:
            for elevation in [.45,1.0,1.65]:
                try:
                    start=position(a[0]-dy/length*offset,a[1]+dx/length*offset,float(a[2]),elevation)
                    end=position(b[0]-dy/length*offset,b[1]+dx/length*offset,float(b[2]),elevation)
                except ValueError as error:
                    support_failures.append({'route':ri,'segment':i,'offset_m':offset,'height_m':elevation,'error':str(error)});continue
                delta=end-start;hit=high.ray_cast(start,delta.normalized(),delta.length)[0];samples+=1
                if hit is not None:hits.append({'route':ri,'segment':i,'offset_m':offset,'height_m':elevation,'hit_m':[hit.x/100,-hit.y/100,hit.z/100]})
result={'samples':samples,'obstructions':hits,'support_failures':support_failures,'passed':not hits and not support_failures,'source_blend_sha256':hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest(),'method':'independent saved-centimetre collision BVH; measured upward-facing walking support within +31/-35cm of authored feet, then body clearance'}
(out/'route_clearance.json').write_text(json.dumps(result,indent=2))
report['whitebox']['route_clearance']=result
manifest=Path(report['whitebox']['manifest']);whitebox=json.loads(manifest.read_text());whitebox['route_clearance']=result
whitebox['portal_tests']=report['whitebox'].get('portal_tests',[])
if '--read-only' not in sys.argv:
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    manifest.write_text(json.dumps(whitebox,indent=2),encoding='utf-8')
print('ROUTE_CLEARANCE',json.dumps(result),flush=True)
if hits or support_failures:raise SystemExit(2)
