"""Asset-independent humanoid preparation, existing-skin reuse or baseline auto skin."""
import bpy, bmesh, json, math, sys, traceback
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from skin_quality import cleanup, assign_skin, stress_test

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
report={'ok':False}

CANON={'root':'Root','hips':'Hip','spine_start':'Waist','spine_end':'Spine02','neck':'NeckTwist01','head':'Head'}
for side,prefix in [('left','L_'),('right','R_')]:
    for key,name in [('clavicle','Clavicle'),('upperarm','Upperarm'),('hand','Hand'),('thigh','Thigh'),('foot','Foot')]:CANON[side+'_'+key]=prefix+name

def reset():bpy.ops.wm.read_factory_settings(use_empty=True)
def select(objects,active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.hide_set(False);o.select_set(True)
    bpy.context.view_layer.objects.active=active or objects[0]
def bbox(meshes):
    points=np.concatenate([np.array([o.matrix_world@v.co for v in o.data.vertices]) for o in meshes])
    return points.min(0),points.max(0)

def fit_armature(meshes,height):
    lo,hi=bbox(meshes);width=hi[0]-lo[0];h=height
    shoulder=min(.21*h,.25*width);hand=.44*width;elbow=(shoulder+hand)*.5
    wrist_z=.48 if width/h>.65 else .43
    positions={'Root':((0,0,0),(0,0,.1*h),None),
      'Hip':((0,0,.51*h),(0,0,.56*h),'Root'),
      'Waist':((0,0,.56*h),(0,0,.63*h),'Hip'),
      'Spine01':((0,0,.63*h),(0,0,.70*h),'Waist'),
      'Spine02':((0,0,.70*h),(0,0,.77*h),'Spine01'),
      'NeckTwist01':((0,0,.77*h),(0,0,.83*h),'Spine02'),
      'Head':((0,0,.83*h),(0,0,.98*h),'NeckTwist01')}
    for side,sign in [('L',1),('R',-1)]:
        p=side+'_';x=lambda f:sign*f
        positions.update({
          p+'Clavicle':((0,0,.755*h),(x(shoulder),0,.75*h),'Spine02'),
          p+'Upperarm':((x(shoulder),0,.75*h),(x(elbow),-.005*h,.60*h),p+'Clavicle'),
          p+'Forearm':((x(elbow),-.005*h,.60*h),(x(hand),-.025*h,wrist_z*h),p+'Upperarm'),
          p+'Hand':((x(hand),-.025*h,wrist_z*h),(x(hand),-.03*h,(wrist_z-.08)*h),p+'Forearm'),
          p+'Thigh':((x(.12*h),0,.51*h),(x(.12*h),-.012*h,.29*h),'Hip'),
          p+'Calf':((x(.12*h),-.012*h,.29*h),(x(.12*h),0,.065*h),p+'Thigh'),
          p+'Foot':((x(.12*h),0,.065*h),(x(.12*h),-.12*h,.045*h),p+'Calf')})
    # Optional artist/agent landmarks replace defaults without changing the adapter.
    for name,points in job.get('landmarks',{}).items():
        if name in positions:positions[name]=(tuple(v*h for v in points[0]),tuple(v*h for v in points[1]),positions[name][2])
    data=bpy.data.armatures.new('HumanoidSkeleton');rig=bpy.data.objects.new('CharacterRig',data);bpy.context.collection.objects.link(rig)
    select([rig]);bpy.ops.object.mode_set(mode='EDIT')
    for name,(head,tail,parent) in positions.items():
        b=data.edit_bones.new(name);b.head=head;b.tail=tail;b.use_deform=name!='Root'
        if parent:b.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    report['skinning']=assign_skin(meshes,rig,height,job.get('skinning',{}))
    return rig

def identify(rig):
    names={b.name.lower().replace('mixamorig:','').replace('_','').replace('.',''):b.name for b in rig.data.bones}
    aliases={'root':['Root','rootmotion'],'hips':['Hip','Hips','pelvis'],'spine_start':['Waist','spine','spine01'],'spine_end':['Spine02','spine03','chest','spine2'],'neck':['NeckTwist01','neck','neck01'],'head':['Head']}
    for side,prefix in [('left','L'),('right','R')]:
        for sem,items in [('clavicle',[prefix+'_Clavicle',side+'shoulder','clavicle_'+prefix]),('upperarm',[prefix+'_Upperarm',side+'arm','upperarm_'+prefix]),('hand',[prefix+'_Hand',side+'hand','hand_'+prefix]),('thigh',[prefix+'_Thigh',side+'upleg','thigh_'+prefix]),('foot',[prefix+'_Foot',side+'foot','foot_'+prefix])]:aliases[side+'_'+sem]=items
    mapping=dict(job.get('bone_map',{}))
    for sem,options in aliases.items():
        if sem in mapping:continue
        for option in options:
            n=names.get(option.lower().replace('_','').replace('.',''))
            if n:mapping[sem]=n;break
    missing=set(CANON)-set(mapping)
    if missing:raise RuntimeError('Existing skeleton needs explicit bone_map for: '+','.join(sorted(missing)))
    return mapping

def image_from(socket,depth=0):
    if depth>5 or not socket.is_linked:return None
    node=socket.links[0].from_node
    if node.type=='TEX_IMAGE':return node.image
    for inp in node.inputs:
        image=image_from(inp,depth+1)
        if image:return image

try:
    reset();src=Path(job['source'])
    if src.suffix.lower()=='.glb':bpy.ops.import_scene.gltf(filepath=str(src))
    elif src.suffix.lower()=='.fbx':bpy.ops.import_scene.fbx(filepath=str(src))
    elif src.suffix.lower()=='.blend':bpy.ops.wm.open_mainfile(filepath=str(src))
    else:raise RuntimeError('Unsupported character input: '+src.suffix)
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    helpers={b.custom_shape for r in rigs for b in r.pose.bones if b.custom_shape}
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in helpers]
    report['ignored_rig_display_helpers']=len(helpers)
    if not meshes or len(rigs)>1:raise RuntimeError('Expected one character asset with at most one armature')
    rig=rigs[0] if rigs else None
    if rig:
        rig.animation_data_clear();rig.data.pose_position='REST'
        for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4);bone.custom_shape=None
    keep=meshes+rigs
    for o in keep:
        matrix=o.matrix_world.copy();o.parent=None;o.matrix_world=matrix
    for o in list(bpy.context.scene.objects):
        if o not in keep:bpy.data.objects.remove(o,do_unlink=True)
    if not rig:
        review=job.get('asset_review',{})
        if not review.get('complete_body') or not review.get('evidence'):
            raise RuntimeError('Unskinned character requires a recorded front/side completeness review before binding. Do not rig a cropped body.')
        forward=job.get('source_forward')
        rotations={'+X':-90,'-X':90,'+Y':180,'-Y':0}
        if forward not in rotations:raise RuntimeError('source_forward must be visually confirmed (+X/-X/+Y/-Y) before automatic binding')
        rotation=Matrix.Rotation(math.radians(rotations[forward]),4,'Z')
        for o in keep:o.matrix_world=rotation@o.matrix_world
        report['orientation']={'source_forward':forward,'canonical_forward':'-Y','rotation_z_degrees':rotations[forward]}
        report['asset_review']=review
    bpy.context.view_layer.update();lo,hi=bbox(meshes);height=hi[2]-lo[2]
    if height<=1e-5:raise RuntimeError('Degenerate character bounds')
    desired=job['height_m'];scale=desired/height;center=Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]))
    transform=Matrix.Scale(scale,4)@Matrix.Translation(-center)
    for o in keep:o.matrix_world=transform@o.matrix_world
    select(keep,rig or meshes[0]);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    if not rig:
        print('Cleaning topology before reduction and rigging',flush=True)
        report['cleanup']=cleanup(meshes,desired)
    original=sum(len(m.data.polygons) for m in meshes);budget=job['triangle_budget']
    if original>budget:
        for mesh in meshes:
            select([mesh]);disabled=[m for m in mesh.modifiers if m.type=='ARMATURE']
            for m in disabled:m.show_viewport=False
            mod=mesh.modifiers.new('RealtimeBudget','DECIMATE');mod.ratio=budget/original;mod.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=mod.name)
            for m in disabled:m.show_viewport=True
    generated=not bool(rig)
    if not rig:rig=fit_armature(meshes,desired);keep=meshes+[rig]
    if job.get('appendages'):
        from appendages import build
        report['appendages']=build(meshes,rig,desired,job['appendages'])
        keep=meshes+[rig]
    mapping=identify(rig)
    weighted={b.name for b in rig.data.bones if b.use_deform};unweighted=0;repaired=0
    loose_removed=0
    for mesh in meshes:
        bm=bmesh.new();bm.from_mesh(mesh.data);loose=[v for v in bm.verts if not v.link_faces]
        if loose:
            loose_removed+=len(loose);bmesh.ops.delete(bm,geom=loose,context='VERTS');bm.to_mesh(mesh.data);mesh.data.update()
        bm.free()
        groups={g.index:g.name for g in mesh.vertex_groups}
        missing=[];valid=[]
        for vertex in mesh.data.vertices:
            if not any(groups.get(g.group) in weighted and g.weight>0 for g in vertex.groups):missing.append(vertex)
            else:valid.append(vertex)
        # Decimation can leave a few vertices without groups. Repair only a small,
        # measured fraction by copying the nearest valid skin, preserving the rig.
        if missing and valid and len(missing)<=max(8,int(len(mesh.data.vertices)*.001)):
            tree=KDTree(len(valid))
            for vertex in valid:tree.insert(vertex.co,vertex.index)
            tree.balance()
            for vertex in missing:
                point,index,distance=tree.find(vertex.co)
                if distance>desired*.06:
                    report.setdefault('unweighted_diagnostics',[]).append({'vertex':vertex.index,'position':list(vertex.co),'nearest_valid_distance_m':distance})
                    continue
                src_vertex=mesh.data.vertices[index]
                links=[g for g in src_vertex.groups if groups.get(g.group) in weighted and g.weight>0]
                total=sum(g.weight for g in links)
                for group in links:mesh.vertex_groups[group.group].add([vertex.index],group.weight/total,'REPLACE')
                repaired+=1
        for vertex in mesh.data.vertices:
            if not any(groups.get(g.group) in weighted and g.weight>0 for g in vertex.groups):unweighted+=1
        for face in mesh.data.polygons:face.use_smooth=True
    if unweighted:raise RuntimeError(f'{unweighted} vertices have no deforming bone weights')
    print('Testing reach, stride, crouch and strike deformation',flush=True)
    report['deformation']=stress_test(meshes,rig,desired,out,render=job.get('render_qa',True),semantic_map=None if generated else mapping)
    if not report['deformation']['passed']:raise RuntimeError('Deformation quality gate failed; inspect pose images and edge stretch diagnostics')
    mats=[]
    for mesh in meshes:
        for mat in mesh.data.materials:
            if not mat or any(x['name']==mat.name for x in mats):continue
            bs=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if mat.use_nodes else None
            entry={'name':mat.name,'color':list(mat.diffuse_color)[:3],'roughness':.65,'metallic':0,'textures':{}}
            if bs:
                entry.update(color=list(bs.inputs['Base Color'].default_value)[:3],roughness=bs.inputs['Roughness'].default_value,metallic=bs.inputs['Metallic'].default_value)
                for kind,socket in [('base','Base Color'),('normal','Normal'),('orm','Roughness')]:
                    image=image_from(bs.inputs[socket])
                    if image:
                        path=out/f'material_{len(mats)}_{kind}.png';image.filepath_raw=str(path);image.file_format='PNG';image.save();entry['textures'][kind]=str(path)
            mats.append(entry)
    # Centimetres in both bone data and mesh data avoid FBX scale/additive collapse bugs.
    for mesh in meshes:mesh.data.transform(Matrix.Scale(100,4))
    rig.data.transform(Matrix.Scale(100,4));rig.data.pose_position='POSE'
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    select(meshes+[rig],rig);bpy.context.view_layer.update()
    fbx=out/'character.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,
        axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',use_armature_deform_only=False,path_mode='STRIP')
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'character.blend'))
    report.update(ok=True,fbx=str(fbx),blend=str(out/'character.blend'),bone_map=mapping,materials=mats,
       skeleton_provider='blender_baseline_humanoid' if generated else 'existing_skin',unweighted_vertices=unweighted,
       orphan_weights_repaired=repaired,
       loose_vertices_removed=loose_removed,
       original_triangles=original,triangles=sum(len(m.data.polygons) for m in meshes),height_cm=desired*100,
       bones=len(rig.data.bones),mesh_materials=[[m.name for m in mesh.data.materials if m] for mesh in meshes])
except Exception:
    report['error']=traceback.format_exc();print(report['error'],flush=True)
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('CHARACTER_ADAPTER_RESULT',json.dumps({k:v for k,v in report.items() if k not in ['materials','error']}),flush=True)
if not report['ok']:sys.exit(1)
