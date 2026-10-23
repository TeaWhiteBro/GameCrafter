"""Render unposed source geometry before a visual agent is allowed to bind it."""
import bpy,json,sys,math
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text());out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);source=Path(job['source'])
if source.suffix.lower() in ['.glb','.gltf']:bpy.ops.import_scene.gltf(filepath=str(source))
elif source.suffix.lower()=='.fbx':bpy.ops.import_scene.fbx(filepath=str(source))
else:bpy.ops.wm.open_mainfile(filepath=str(source))
rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
if rigs:
    (out/'inspection.json').write_text(json.dumps({'existing_skin':True,'armatures':len(rigs),'images':[]}));sys.exit(0)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];world={o:np.array([o.matrix_world@v.co for v in o.data.vertices]) for o in meshes}
points=np.concatenate(list(world.values()));lo=points.min(0);hi=points.max(0);h=hi[2]-lo[2]
if h<1e-5:raise RuntimeError('Empty character bounds')
center=np.array([(hi[0]+lo[0])/2,(hi[1]+lo[1])/2,lo[2]])
for ob,coords in world.items():
    ob.parent=None;ob.matrix_world=Matrix.Identity(4);ob.data.vertices.foreach_set('co',((coords-center)/h*2).astype(np.float32).ravel())
    bpy.context.view_layer.objects.active=ob
    triangles=sum(len(p.vertices)-2 for p in ob.data.polygons)
    if triangles>120000:
        m=ob.modifiers.new('Inspection LOD','DECIMATE');m.ratio=120000/triangles;bpy.ops.object.modifier_apply(modifier=m.name)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=560;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Inspection');scene.world.color=(.18,.18,.18);scene.view_settings.view_transform='AgX'
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
for name,pos in [('A',(3,-3,5)),('B',(-3,-2,4)),('C',(2,3,4)),('D',(-2,3,4))]:
    d=bpy.data.lights.new(name,'AREA');d.energy=380;d.size=4;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=pos;aim(o,(0,0,1))
cam=bpy.data.cameras.new('Review camera');o=bpy.data.objects.new('Review camera',cam);bpy.context.collection.objects.link(o);cam.type='ORTHO';cam.ortho_scale=2.75;scene.camera=o
images=[]
for axis,pos in [('+X',(5,0,1)),('-X',(-5,0,1)),('+Y',(0,5,1)),('-Y',(0,-5,1))]:
    o.location=pos;aim(o,(0,0,1));path=out/(axis.replace('+','positive').replace('-','negative')+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);images.append({'view_from':axis,'image':str(path)})
(out/'inspection.json').write_text(json.dumps({'existing_skin':False,'bounds':[lo.tolist(),hi.tolist()],'images':images},indent=2))
