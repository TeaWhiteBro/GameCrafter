"""Render installed scan sets and record full imported mesh bounds for placement."""
import bpy,json,sys,math
from pathlib import Path
from mathutils import Vector
path=Path(sys.argv[sys.argv.index('--')+1]).resolve();catalog=json.loads(path.read_text());out=path.parent/'previews';out.mkdir(exist_ok=True)
audits={}

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.threads_mode='FIXED';scene.render.threads=6
    scene.render.resolution_x=400;scene.render.resolution_y=320;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('Neutral studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.20,.23,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    scene.view_settings.view_transform='AgX'
    return scene

def light(pos,power,size):
    d=bpy.data.lights.new('Softbox','AREA');d.energy=power;d.shape='DISK';d.size=size
    o=bpy.data.objects.new('Softbox',d);bpy.context.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector((0,0,.8))-o.location).to_track_quat('-Z','Y').to_euler()

def render(scene,name,radius=1):
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.015));floor=bpy.context.object
    m=bpy.data.materials.new('Studio matte');m.diffuse_color=(.055,.064,.079,1);floor.data.materials.append(m)
    light((3,-4,5),700,4);light((-3,0,3),420,3);light((1,3,4),650,3)
    c=bpy.data.cameras.new('Camera');o=bpy.data.objects.new('Camera',c);bpy.context.collection.objects.link(o)
    o.location=(3,-4,2.7);o.rotation_euler=(Vector((0,0,.8))-o.location).to_track_quat('-Z','Y').to_euler();c.type='ORTHO';c.ortho_scale=3.6;scene.camera=o
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)

for name,e in sorted(catalog['entries'].items()):
    if (out/(name+'.png')).exists() and name not in sys.argv[sys.argv.index('--')+2:]:continue
    scene=reset()
    if e['kind']=='textures':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=80,ring_count=48,radius=1,location=(0,0,1));o=bpy.context.object
        for p in o.data.polygons:p.use_smooth=True
        m=bpy.data.materials.new(name);m.use_nodes=True;o.data.materials.append(m);ns=m.node_tree.nodes;links=m.node_tree.links;p=ns.get('Principled BSDF')
        for ch,source in e['textures'].items():
            if ch not in ['base','normal','roughness','metallic']:continue
            n=ns.new('ShaderNodeTexImage');n.image=bpy.data.images.load(source);n.image.colorspace_settings.name='sRGB' if ch=='base' else 'Non-Color'
            if ch=='normal':
                sep=ns.new('ShaderNodeSeparateColor');comb=ns.new('ShaderNodeCombineColor');inv=ns.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1
                links.new(n.outputs['Color'],sep.inputs[0]);links.new(sep.outputs[0],comb.inputs[0]);links.new(sep.outputs[2],comb.inputs[2]);links.new(sep.outputs[1],inv.inputs[1]);links.new(inv.outputs[0],comb.inputs[1])
                normal=ns.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.6;links.new(comb.outputs[0],normal.inputs['Color']);links.new(normal.outputs[0],p.inputs['Normal'])
            else:links.new(n.outputs['Color'],p.inputs[{'base':'Base Color','roughness':'Roughness','metallic':'Metallic'}[ch]])
    else:
        bpy.ops.import_scene.gltf(filepath=e['file']);objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
        coords=[o.matrix_world@Vector(c) for o in objects for c in o.bound_box];lo=Vector(tuple(min(p[i] for p in coords) for i in range(3)));hi=Vector(tuple(max(p[i] for p in coords) for i in range(3)));size=hi-lo
        audits[name]={'original_bounds_m':[list(lo),list(hi)],'dimensions_m':list(size),'mesh_parts':len(objects),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects),'variant_mode':e.get('variant_mode','assembled')}
        if e.get('variant_mode')=='separate' and len(objects)>1:
            representative=max(objects,key=lambda ob:len(ob.data.vertices))
            for ob in objects:
                if ob!=representative:bpy.data.objects.remove(ob,do_unlink=True)
            objects=[representative];coords=[representative.matrix_world@Vector(c) for c in representative.bound_box]
            lo=Vector(tuple(min(p[i] for p in coords) for i in range(3)));hi=Vector(tuple(max(p[i] for p in coords) for i in range(3)));size=hi-lo
        center=Vector(((hi.x+lo.x)*.5,(hi.y+lo.y)*.5,lo.z));scale=2.1/max(size)
        from mathutils import Matrix
        for o in objects:o.matrix_world=Matrix.Scale(scale,4)@Matrix.Translation(-center)@o.matrix_world
    render(scene,name);print('LIBRARY_PREVIEW '+name,flush=True)
previous=json.loads((out/'mesh_audit.json').read_text()) if (out/'mesh_audit.json').exists() else {}
previous.update(audits);(out/'mesh_audit.json').write_text(json.dumps(previous,indent=2),encoding='utf-8')
