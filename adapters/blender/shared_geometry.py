"""Export repeated upright source meshes once, retaining metric placement.

Detailed and structural BVH checks run before extraction. Saved-mesh probes
include every placed instance; colliding prototypes retain exact fallback geometry.
Only positive scale and upright yaw are admitted by this first contract.
"""
import math


def extract(groups):
    prototypes=[];expanded=0;source=0;count=0
    for (material,collision),objects in list(groups.items()):
        by_mesh={}
        for ob in objects:
            if ob.modifiers or not ob.data.get('pipeline_source_key'):continue
            by_mesh.setdefault(ob.data.as_pointer(),[]).append(ob)
        taken=set()
        for members in by_mesh.values():
            if len(members)<2:continue
            transforms=[]
            for ob in members:
                position,rotation,scale=ob.matrix_world.decompose();angles=rotation.to_euler('XYZ')
                if abs(angles.x)>1e-5 or abs(angles.y)>1e-5 or min(scale)<=0:
                    raise ValueError('Shared geometry requires upright positive-scale transforms: '+ob.name)
                transforms.append({'position_cm':[float(v*100) for v in position],
                                   'yaw_deg':float(math.degrees(angles.z)),
                                   'scale':[float(v) for v in scale]})
            triangles=sum(len(p.vertices)-2 for p in members[0].data.polygons)
            prototypes.append({'material':material,'collision':collision,'objects':members,
                               'instances':transforms,'triangles':triangles})
            expanded+=triangles*len(members);source+=triangles;count+=len(members)
            taken.update(members)
        groups[material,collision]=[ob for ob in objects if ob not in taken]
        if not groups[material,collision]:del groups[material,collision]
    return prototypes,{'contract':'upright_shared_mesh_v2','prototypes':len(prototypes),
                       'instances':count,'source_triangles':source,'expanded_triangles':expanded}


def export(prototypes,out,start_index,materials):
    import bpy
    from mathutils import Matrix,Vector
    basis=Matrix.Diagonal(Vector((100,-100,100,1)));inverse=basis.inverted()
    entries=[]
    for offset,group in enumerate(prototypes):
        index=start_index+offset;members=group['objects']
        data=members[0].data.copy();data.transform(basis);data.flip_normals();data.update()
        prototype=bpy.data.objects.new('Prototype export',data);bpy.context.collection.objects.link(prototype)
        bpy.ops.object.select_all(action='DESELECT');prototype.select_set(True);bpy.context.view_layer.objects.active=prototype
        path=out/f'environment_{index}.fbx'
        bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,
            axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',mesh_smooth_type='FACE')
        bpy.data.objects.remove(prototype,do_unlink=True)
        # Keep the complete placed scene in its established saved-file basis.
        for j,ob in enumerate(members):
            transform=ob.matrix_world.copy();ob.data=data;ob.matrix_world=basis@transform@inverse
            ob.name=f'Environment_{index}_Instance_{j}'
        cls=materials[group['material']].get('semantic_class')
        if cls not in ['vegetation','prop','rock','architecture']:raise ValueError('Shared source object needs an explicit semantic class')
        entries.append({'file':str(path),'material':group['material'],'collision':group['collision'],
            'semantic_id':{'vegetation':5,'prop':6,'rock':4,'architecture':3}[cls],'triangles':group['triangles'],
            'instances':group['instances'],'instance_contract':'upright_shared_mesh_v2' if group['collision'] else 'upright_shared_mesh_v1',
            'expanded_triangles':group['triangles']*len(members)})
    return entries
