"""Optional measured tubular detail attached to a semantic skeleton bone.

Dimensions are fractions of body height. This supplies geometry and skin weights,
not an independent secondary-motion simulation.
"""
import bpy
from mathutils import Vector


def build(meshes,rig,height,configs):
    added=[]
    for index,cfg in enumerate(configs):
        bone=cfg['bone']
        if bone not in rig.data.bones:raise RuntimeError('Appendage parent bone missing: '+bone)
        points=cfg['points'];radii=cfg['radii']
        if len(points)<2 or len(points)!=len(radii) or any(r<=0 for r in radii):raise RuntimeError('Appendage needs positive radii for each control point')
        material=bpy.data.materials.new('Appendage_'+str(index));material.use_nodes=True
        bs=material.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*cfg['color'],1);bs.inputs['Roughness'].default_value=cfg.get('roughness',.8)
        material.diffuse_color=(*cfg['color'],1)
        curve=bpy.data.curves.new('MeasuredAppendage','CURVE');curve.dimensions='3D';curve.resolution_u=12;curve.bevel_depth=height*max(radii);curve.bevel_resolution=6;curve.use_fill_caps=True
        spline=curve.splines.new('BEZIER');spline.bezier_points.add(len(points)-1)
        for point,co,radius in zip(spline.bezier_points,points,radii):
            point.co=Vector(co)*height;point.radius=radius/max(radii);point.handle_left_type='AUTO';point.handle_right_type='AUTO'
        obj=bpy.data.objects.new('AttachedDetail_'+str(index),curve);bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')
        parts=[bpy.context.object];parts[0].data.materials.append(material)
        tip=cfg.get('tip')
        if tip:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,location=Vector(tip['center'])*height)
            end=bpy.context.object;end.name='AppendageTip_'+str(index);end.scale=Vector(tip['scale'])*height;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            endmat=bpy.data.materials.new('AppendageTipMaterial_'+str(index));endmat.use_nodes=True
            endmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*tip['color'],1)
            endmat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.87;endmat.diffuse_color=(*tip['color'],1);end.data.materials.append(endmat);parts.append(end)
        for part in parts:
            for face in part.data.polygons:face.use_smooth=True
            group=part.vertex_groups.new(name=bone);group.add([v.index for v in part.data.vertices],1,'REPLACE')
            modifier=part.modifiers.new('AttachedSkin','ARMATURE');modifier.object=rig
        meshes.extend(parts);added.append({'bone':bone,'meshes':[o.name for o in parts],'control_points':points,'method':'rigid attachment follows parent bone'})
    return added
