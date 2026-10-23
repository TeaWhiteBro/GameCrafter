"""Render front/side/rear of a prepared rig without modifying its saved artifact."""
import bpy,json,sys,hashlib
from pathlib import Path
from mathutils import Matrix,Vector
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
report_path=Path(job['report']);report=json.loads(report_path.read_text(encoding='utf-8'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=report['blend'])
for obj in list(bpy.context.scene.objects):
    if obj.type not in ['MESH','ARMATURE']:bpy.data.objects.remove(obj,do_unlink=True)
    else:
        obj.data.transform(Matrix.Scale(.01,4))
        if obj.type=='ARMATURE':
            obj.data.pose_position='POSE'
            for bone in obj.pose.bones:bone.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update()
h=report['height_cm']*.01;scene=bpy.context.scene;scene.unit_settings.scale_length=1
scene.render.engine='CYCLES';scene.cycles.samples=16
scene.render.resolution_x=650;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('PreparedReview');scene.world.color=(.16,.16,.16)
def aim(obj):obj.rotation_euler=(Vector((0,0,h*.5))-obj.location).to_track_quat('-Z','Y').to_euler()
for name,pos in [('A',(2,-3,3)),('B',(-2,-2,2)),('C',(2,3,3)),('D',(-2,3,2))]:
    light=bpy.data.lights.new(name,'AREA');light.energy=400*h;light.size=2*h
    obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj);obj.location=Vector(pos)*h;aim(obj)
cam=bpy.data.cameras.new('ReviewCamera');camera=bpy.data.objects.new('ReviewCamera',cam);scene.collection.objects.link(camera)
cam.type='ORTHO';cam.ortho_scale=h*1.32;scene.camera=camera;images=[]
for label,pos in [('front',(0,-3,.5)),('side',(3,0,.5)),('rear',(0,3,.5))]:
    camera.location=Vector(pos)*h;aim(camera);path=out/(label+'.png');scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True);images.append({'view':label,'image':str(path.resolve())})
manifest={'rig_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),'report':str(report_path.resolve()),'images':images}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
