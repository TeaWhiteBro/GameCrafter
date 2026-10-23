"""Build a scene from a data grammar; no asset names or theme are embedded here."""
import bpy, json, math, random, sys, traceback
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.noise import noise_vector
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
data=json.loads(Path(job['scene_spec']).read_text(encoding='utf-8'));spec=data['scene']
rng=random.Random(job.get('seed',417));report={'ok':False,'repairs':[],'environment':[]}
bpy.ops.wm.read_factory_settings(use_empty=True)
groups={}

def collect(o,material,collision=True):
    key=(material,collision);groups.setdefault(key,[]).append(o)
    for p in o.data.polygons:p.use_smooth=True
    return o
def cube(pos,scale,mat,bevel=.045):
    bpy.ops.mesh.primitive_cube_add(size=1,location=pos);o=bpy.context.object;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        mod=o.modifiers.new('Rounded wear','BEVEL');mod.width=bevel;mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return collect(o,mat)
def column(pos,radius,height,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=radius,depth=height,location=pos)
    o=bpy.context.object;mod=o.modifiers.new('Edge wear','BEVEL');mod.width=min(.035,radius*.1);mod.segments=3
    bpy.ops.object.modifier_apply(modifier=mod.name);return collect(o,mat)
def rock(pos,scale,mat):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3,radius=1,location=pos);o=bpy.context.object
    for v in o.data.vertices:
        n=noise_vector(v.co*2.3);v.co*=.9+.17*n.x;v.co.x*=scale[0]*.5;v.co.y*=scale[1]*.5;v.co.z*=scale[2]*.5
    return collect(o,mat)
def arch(pos,scale,yaw,mat):
    width,depth,height=scale;r=width/2;spring=max(.7,height-r);thick=min(.55,width*.15)
    local=[]
    for x in [-r+thick/2,r-thick/2]:local.append(cube((x,0,spring/2),(thick,depth,spring),mat))
    for i in range(22):
        a0=i*math.pi/22+.007;a1=(i+1)*math.pi/22-.007
        verts=[(math.cos(a)*rad,y,spring+math.sin(a)*rad) for y in [-depth/2,depth/2] for rad in [r-thick,r] for a in [a0,a1]]
        faces=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
        mesh=bpy.data.meshes.new('Voussoir');mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new('ArchBlock',mesh);bpy.context.collection.objects.link(obj);collect(obj,mat);local.append(obj)
    transform=Matrix.Translation(Vector(pos))@Matrix.Rotation(math.radians(yaw),4,'Z')
    for o in local:o.matrix_world=transform@o.matrix_world

try:
    size=spec['size_m'];n=int(size*2.5);verts=[];faces=[]
    for y in range(n+1):
        for x in range(n+1):
            px=(x/n-.5)*size;py=(y/n-.5)*size
            edge=min(1,max(0,(math.hypot(px,py)-5)/4))
            z=edge*(.10*math.sin(px*.6)*math.cos(py*.43)+.05*math.sin(py*1.7+px))-.06
            verts.append((px,py,z))
    for y in range(n):
        for x in range(n):
            i=y*(n+1)+x;faces.append((i,i+1,i+n+2,i+n+1))
    mesh=bpy.data.meshes.new('Terrain');mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new('Terrain',mesh);bpy.context.collection.objects.link(o);collect(o,spec['floor_material'])
    if spec.get('paving',True):
        material=spec['path_material'];step=.91
        for row in range(-6,7):
            for col in range(-6,7):
                x=col*step+(.45 if row%2 else 0);y=row*step
                if math.hypot(x,y)>5.6+rng.uniform(-.4,.5):continue
                tile=cube((x,y,-.045+rng.uniform(-.008,.008)),(.86+rng.uniform(-.04,.04),.86+rng.uniform(-.04,.04),.12),material,.035)
                tile.rotation_euler.z=rng.uniform(-.023,.023)
    for item in spec['objects']:
        kind=item['kind'];pos=list(item['position']);scale=item['scale'];mat=item['material'];yaw=item.get('yaw_deg',0)
        if kind not in ['arch']:
            for spawn in data['spawns'].values():
                dx=pos[0]-spawn[0];dy=pos[1]-spawn[1];dist=math.hypot(dx,dy);clear=max(scale[:2])*.5+1.6
                if dist<clear:
                    if dist<.1:dx,dy,dist=1,0,1
                    pos[0]=spawn[0]+dx/dist*clear;pos[1]=spawn[1]+dy/dist*clear
                    report['repairs'].append({'kind':'spawn_clearance','object':kind,'before':item['position'],'after':pos[:]})
        if kind=='arch':arch(pos,scale,yaw,mat)
        elif kind=='box':
            obj=cube((pos[0],pos[1],pos[2]+scale[2]/2),scale,mat);obj.rotation_euler.z=math.radians(yaw)
        elif kind=='column':
            column((pos[0],pos[1],pos[2]+scale[2]/2),scale[0]/2,scale[2],mat)
            for z in [.12,scale[2]-.12]:column((pos[0],pos[1],pos[2]+z),scale[0]*.6,.24,mat)
        elif kind=='rock':rock((pos[0],pos[1],pos[2]+scale[2]*.35),scale,mat)
        elif kind=='stairs':
            for i in range(6):cube((pos[0],pos[1]+(i/6-.5)*scale[1],pos[2]+scale[2]*(i+1)/12),(scale[0],scale[1]/6,scale[2]*(i+1)/6),mat)
        elif kind=='tree':
            trunk=column((pos[0],pos[1],pos[2]+scale[2]*.45),min(.22,scale[0]*.18),scale[2]*.9,mat)
            for i in range(4):
                a=i*2.4;branch=column((pos[0]+math.cos(a)*.4,pos[1]+math.sin(a)*.4,pos[2]+scale[2]*(.55+i*.08)),.07,1.3,mat)
                branch.rotation_euler=(math.cos(a)*.8,math.sin(a)*.8,0)
                rock((pos[0]+math.cos(a)*scale[0]*.25,pos[1]+math.sin(a)*scale[1]*.25,pos[2]+scale[2]*(.72+i*.06)),(scale[0]*.8,scale[1]*.8,scale[2]*.35),mat)
    # Export material groups, not named scene entities. Geometry remains replaceable.
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    for index,((material,collision),objects) in enumerate(groups.items()):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:obj.select_set(True)
        bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();obj=bpy.context.object
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);obj.data.transform(Matrix.Scale(100,4));obj.name='Geometry_'+str(index)
        path=out/f'geometry_{index}.fbx'
        bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL')
        report['environment'].append({'file':str(path),'material':material,'collision':collision,'triangles':sum(len(p.vertices)-2 for p in obj.data.polygons)})
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    report.update(ok=True,materials=spec['materials'],lighting=data['lighting'],spawns=data['spawns'],size_m=size,blend=str(out/'scene.blend'))
except Exception:report['error']=traceback.format_exc();print(report['error'],flush=True)
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SCENE_ADAPTER_RESULT',report['ok'],flush=True)
if not report['ok']:sys.exit(1)
