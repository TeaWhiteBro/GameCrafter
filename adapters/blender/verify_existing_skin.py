"""Regression harness: preserved source skin must deform; a disabled skin must fail."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from skin_quality import stress_test

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8-sig'))
report=json.loads(Path(job['report']).read_text(encoding='utf-8'))
out=Path(job['out']).resolve();out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=report['blend'])
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
for mesh in meshes:mesh.data.transform(Matrix.Scale(.01,4))
rig.data.transform(Matrix.Scale(.01,4));bpy.context.scene.unit_settings.scale_length=1
height=report['height_cm']*.01
positive=stress_test(meshes,rig,height,out,render=job.get('render',True),semantic_map=report['bone_map'])
modifiers=[m for mesh in meshes for m in mesh.modifiers if m.type=='ARMATURE']
for m in modifiers:m.show_viewport=False;m.show_render=False
negative=stress_test(meshes,rig,height,out,render=False,semantic_map=report['bone_map'])
expected=job.get('expected_skin_pass',True)
result={'passed':positive['passed']==expected and not negative['passed'],'expected_skin_pass':expected,'skin_suite':positive,'disabled_armature_negative_control':negative,'source_report':job['report']}
(out/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if not result['passed']:raise RuntimeError('Existing-skin regression failed')
print('Existing-skin expected outcome and disabled-armature negative control verified')
