"""Precisely constructed alternatives for assets whose generated hard surfaces fail review."""
import bpy,math,json,shutil
from pathlib import Path

def build(config,job,out):
    if config.get('recipe')=='eroded_outcrop':
        from geological_recipe import build as build_geology
        return build_geology(config,job,out)
    if config.get('recipe')!='carved_lantern':raise ValueError('Unknown static construction recipe')
    textures=job['texture_library'][config.get('texture_set','rock_boulder_dry')]
    mat=bpy.data.materials.new('Carved stone');mat.use_nodes=True;bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    binding={'surface':'pbr','semantic_class':'prop','color':[.23,.27,.31],'roughness':.78,'metallic':0,
        'normal_opengl':False,'normal_strength':.16,'triplanar':True,'scale_cm':55,'tint':config.get('tint',[.27,.32,.39]),
        'roughness_scale':.25,'roughness_bias':.58,'textures':{}}
    coord=mat.node_tree.nodes.new('ShaderNodeTexCoord');mapping=mat.node_tree.nodes.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs['Scale'].default_value=1.25
    mat.node_tree.links.new(coord.outputs['Object'],mapping.inputs[0])
    for kind in ['base','normal','roughness']:
        source=Path(textures[kind]);path=out/('recipe_'+kind+source.suffix);shutil.copy2(source,path);binding['textures'][kind]=str(path)
        image=bpy.data.images.load(str(path));image.colorspace_settings.name='sRGB' if kind=='base' else 'Non-Color'
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;tex.projection='BOX';tex.projection_blend=.2;mat.node_tree.links.new(mapping.outputs['Vector'],tex.inputs['Vector'])
        if kind=='base':
            tint=mat.node_tree.nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1;tint.inputs[2].default_value=(*binding['tint'],1)
            mat.node_tree.links.new(tex.outputs['Color'],tint.inputs[1]);mat.node_tree.links.new(tint.outputs[0],bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value=.78
    mat['pipeline_binding']=json.dumps(binding)
    objects=[]
    def finish(ob,bevel=.009):
        objects.append(ob);ob.data.materials.append(mat)
        if bevel:
            mod=ob.modifiers.new('Carved edge bevel','BEVEL');mod.width=bevel;mod.segments=3;bpy.ops.object.modifier_apply(modifier=mod.name)
            mod=ob.modifiers.new('Planar stone normals','WEIGHTED_NORMAL');mod.keep_sharp=True;bpy.ops.object.modifier_apply(modifier=mod.name)
        return ob
    def block(p,d):
        bpy.ops.mesh.primitive_cube_add(size=1,location=p);ob=bpy.context.object;ob.scale=d;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return finish(ob)
    def column(z,r,h,n=8):
        bpy.ops.mesh.primitive_cylinder_add(vertices=n,radius=r,depth=h,location=(0,0,z+h/2));return finish(bpy.context.object)
    block((0,0,.075),(.78,.78,.15));column(.14,.28,.09);column(.21,.18,.68)
    column(.85,.22,.10);column(.93,.30,.10)
    block((0,0,1.06),(.63,.63,.12))
    for x in [-.24,.24]:
        for y in [-.24,.24]:block((x,y,1.30),(.12,.12,.40))
    block((0,0,1.52),(.64,.64,.09))
    n=24;vs=[];fs=[]
    def roof_z(x,y):
        t=max(abs(x),abs(y))/.57
        return 1.56+.24*(1-t)**1.25+.075*t**7
    for layer in [0,.075]:
        for j in range(n+1):
            for i in range(n+1):
                x=(i/n-.5)*1.14;y=(j/n-.5)*1.14;vs.append((x,y,roof_z(x,y)+layer))
    count=(n+1)**2
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i;fs += [(a,a+n+1,a+n+2,a+1),(a+count,a+1+count,a+n+2+count,a+n+1+count)]
    for j in range(n):
        for i in [0,n]:a=j*(n+1)+i;b=a+n+1;fs.append((a,b,b+count,a+count))
    for i in range(n):
        for j in [0,n]:a=j*(n+1)+i;b=a+1;fs.append((a,b,b+count,a+count))
    me=bpy.data.meshes.new('Solid gently upturned cap');me.from_pydata(vs,[],fs);me.update();ob=bpy.data.objects.new('Carved stone cap',me);bpy.context.collection.objects.link(ob);bpy.context.view_layer.objects.active=ob
    finish(ob,0)
    for face in me.polygons:face.use_smooth=True
    column(1.84,.11,.065,24)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=.112,location=(0,0,1.96));finish(bpy.context.object,0)
    for face in bpy.context.object.data.polygons:face.use_smooth=True
    return {'provider':'blender_recipe','recipe':config['recipe'],'components':len(objects),
        'reason':'Generated stone surfaces failed carving/planarity review; exact supports and open firebox are authored in Blender.',
        'generated_geometry_reused':False,'textures':binding['textures']}
