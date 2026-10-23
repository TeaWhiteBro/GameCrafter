"""Blender bone-heat option for connected organic meshes; failures stay explicit."""
import bpy


def assign(meshes,rig,height,config):
    bpy.ops.object.select_all(action='DESELECT')
    for mesh in meshes:
        mesh.vertex_groups.clear();mesh.select_set(True)
        for modifier in list(mesh.modifiers):
            if modifier.type=='ARMATURE':mesh.modifiers.remove(modifier)
    rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    protected=0
    for mesh in meshes:
        for vertex in mesh.data.vertices:
            co=vertex.co/height
            overrides=[]
            for region in config.get('rigid_regions',[]):
                if 'bone' in region:
                    strength=max(0,min(1,(co.z-region['z_min'])/region.get('feather',.025)))
                    if strength:overrides.append((region['bone'],strength))
            for region in config.get('anatomical_regions',[]):
                if 'bone' not in region:raise RuntimeError('Bone heat takes bone overrides, not heuristic chain masks')
                if region['shape']!='box':raise RuntimeError('Bone heat bone override must be a box')
                if all(lo<=v<=hi for v,lo,hi in zip(co,region['min'],region['max'])):overrides.append((region['bone'],1))
            for name,strength in overrides:
                if name not in rig.data.bones:raise RuntimeError('Bone heat override references missing bone')
                target=mesh.vertex_groups.get(name) or mesh.vertex_groups.new(name=name)
                links=[(g.group,g.weight) for g in vertex.groups]
                old_target=next((w for i,w in links if i==target.index),0)
                for i,weight in links:
                    mesh.vertex_groups[i].add([vertex.index],weight*(1-strength),'REPLACE')
                target.add([vertex.index],old_target*(1-strength)+strength,'REPLACE');protected+=1
        for modifier in mesh.modifiers:
            if modifier.type=='ARMATURE':modifier.use_deform_preserve_volume=True
        # Blender can warn and return FINISHED when heat solving fails.
        deform={g.index for g in mesh.vertex_groups if g.name in rig.data.bones and rig.data.bones[g.name].use_deform}
        missing=sum(not any(g.group in deform and g.weight>1e-6 for g in vertex.groups) for vertex in mesh.data.vertices)
        if missing:raise RuntimeError(f'Bone heat failed: {missing} unweighted vertices; inspect topology and landmarks')
    return {'method':'blender_bone_heat','protected_vertex_assignments':protected,'volume_preservation':True}
