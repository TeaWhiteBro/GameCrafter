"""Broad joined cliff rock with broken planes and matched mineral maps.

Author natural bank geometry, never a separate display base. Source review and
route clearance remain independent consumers of the resulting geometry.
"""
import bpy,bmesh,math,json,shutil,random
from pathlib import Path
from mathutils import Vector
from mathutils.noise import noise_vector


def build(config,job,out):
    rng=random.Random(int(config.get('seed',47)))
    dimensions=config.get('dimensions_m',[9,6,5])
    if len(dimensions)!=3 or any(not 1<=v<=25 for v in dimensions):
        raise ValueError('Outcrop dimensions must be within 1..25m')
    maps=job['texture_library'][config['texture_set']]
    mat=bpy.data.materials.new('Weathered mineral rock');mat.use_nodes=True
    nodes=mat.node_tree.nodes;links=mat.node_tree.links
    bs=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    binding=dict(surface='pbr',semantic_class='rock',color=[.24,.23,.20],roughness=.78,
                 metallic=0,normal_opengl=False,normal_strength=.55,triplanar=True,
                 scale_cm=165,tint=config.get('tint',[.76,.80,.74]),
                 roughness_scale=.48,roughness_bias=.35,textures={})
    coord=nodes.new('ShaderNodeTexCoord');mapping=nodes.new('ShaderNodeVectorMath')
    mapping.operation='SCALE';mapping.inputs['Scale'].default_value=1/1.65
    links.new(coord.outputs['Object'],mapping.inputs[0])
    for kind in ['base','normal','roughness','height','ao']:
        if kind not in maps:continue
        src=Path(maps[kind]);dst=out/('geology_'+kind+src.suffix);shutil.copy2(src,dst)
        binding['textures'][kind]=str(dst)
        im=bpy.data.images.load(str(dst));im.colorspace_settings.name='sRGB' if kind=='base' else 'Non-Color'
        tex=nodes.new('ShaderNodeTexImage');tex.image=im;tex.projection='BOX';tex.projection_blend=.16
        links.new(mapping.outputs['Vector'],tex.inputs['Vector'])
        if kind=='base':
            tint=nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY'
            tint.inputs[0].default_value=1;tint.inputs[2].default_value=(*binding['tint'],1)
            links.new(tex.outputs['Color'],tint.inputs[1]);links.new(tint.outputs[0],bs.inputs['Base Color'])
        elif kind=='roughness':links.new(tex.outputs['Color'],bs.inputs['Roughness'])
        elif kind=='height':
            bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.42;bump.inputs['Distance'].default_value=.045
            links.new(tex.outputs['Color'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    mat['pipeline_binding']=json.dumps(binding)
    objects=[]
    # Irregular polygonal rings give planar cliff faces; uneven upper shoulders
    # break their outline. The unequal masses overlap throughout their bases.
    components=[((-1.0,.35,0),(6.7,5.6,4.75),.10),
                ((2.2,-.45,0),(4.6,4.25,3.45),-.22),
                ((-2.8,-1.20,0),(3.8,3.3,2.45),.25)]
    for index,(center,size,yaw) in enumerate(components):
        vertices=[];faces=[];n=9
        angles=[2*math.pi*i/n+rng.uniform(-.10,.10) for i in range(n)]
        factors=[rng.uniform(.89,1.08) for _ in range(n)]
        for level,(height,rad) in enumerate([(0,.94),(.20,1.02),(.48,.87),(.64,.96),(1,.62)]):
            for i,a in enumerate(angles):
                a+=yaw
                x=math.cos(a)*size[0]*.5*factors[i]*rad
                y=math.sin(a)*size[1]*.5*factors[i]*rad
                z=size[2]*height
                if level>=2:
                    z+=.38*math.sin(a*2.3+index)+rng.uniform(-.19,.19)
                    x+=.27*height;y-=.35*height
                vertices.append((x+center[0],y+center[1],z))
        faces.append(tuple(reversed(range(n))));faces.append(tuple(range(4*n,5*n)))
        for j in range(4):
            for i in range(n):faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
        me=bpy.data.meshes.new('Broken rock planes');me.from_pydata(vertices,[],faces);me.update()
        ob=bpy.data.objects.new('Interlocked bank mass '+str(index),me);bpy.context.collection.objects.link(ob)
        bpy.context.view_layer.objects.active=ob;ob.select_set(True)
        # A few sloping fracture planes remove wedges rather than repeated
        # horizontal pancake layers. Remaining rock has thick load-bearing joins.
        bm=bmesh.new();bm.from_mesh(me)
        for plane_co,plane_no in [((center[0],center[1],size[2]*.90),(.15,-.20,1)),
                                  ((center[0]+size[0]*.39,center[1],size[2]*.5),(1,.27,.24))]:
            cut=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.0001,
                plane_co=plane_co,plane_no=plane_no,clear_outer=True,clear_inner=False)
            edges=[e for e in cut['geom_cut'] if isinstance(e,bmesh.types.BMEdge) and e.is_boundary]
            if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
        objects.append(ob);ob.select_set(False)
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();rock=bpy.context.object
    mod=rock.modifiers.new('Connected solid rock','REMESH');mod.mode='VOXEL';mod.voxel_size=.065;mod.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # True open fissures and chipped shelves, with a continuous thick lower body.
    cuts=[((-.7,-1.0,3.3),(.25,6.8,4.3),(.10,.16,.30)),
          ((2.2,-1.3,2.9),(.20,5.5,3.1),(-.20,-.25,-.48)),
          ((-2.8,-2.45,2.1),(3.7,.95,.43),(.14,-.13,.12)),
          ((.8,2.12,2.8),(4.1,1.15,.55),(-.17,.20,-.26)),
          ((3.0,.15,2.15),(2.5,1.2,.47),(.20,.12,.34)),
          ((-2.8,1.75,3.75),(2.0,1.65,1.45),(.38,.24,.48))]
    for index,(p,size,rotation) in enumerate(cuts):
        bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_cube_add(size=1,location=p)
        cutter=bpy.context.object;cutter.scale=size;cutter.rotation_euler=rotation
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        bpy.context.view_layer.objects.active=rock
        mod=rock.modifiers.new('Geological fracture '+str(index),'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    bpy.context.view_layer.objects.active=rock;rock.select_set(True)
    mod=rock.modifiers.new('Weathered fracture edges','REMESH');mod.mode='VOXEL';mod.voxel_size=.052;mod.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod=rock.modifiers.new('Restrained weathering','SMOOTH');mod.factor=.46;mod.iterations=2
    bpy.ops.object.modifier_apply(modifier=mod.name)
    rock.data.update()
    for v in rock.data.vertices:
        p=v.co.copy();large=noise_vector(p*1.20+Vector((2.3,6.7,1.1))).x
        fine=noise_vector(p*5.7+Vector((7.2,2.4,9.3))).z
        # Mineral-scale relief does not replace the large planar fractures.
        v.co+=v.normal*(large*.055+fine*.008)
        v.co.x+=.16*noise_vector(p*.62+Vector((3.1,4.4,6.2))).x
        v.co.y+=.12*noise_vector(p*.71+Vector((5.1,8.4,2.2))).z
    lo=Vector(tuple(min(v.co[i] for v in rock.data.vertices) for i in range(3)))
    hi=Vector(tuple(max(v.co[i] for v in rock.data.vertices) for i in range(3)))
    for v in rock.data.vertices:
        v.co=Vector(tuple((v.co[i]-lo[i])/(hi[i]-lo[i])*dimensions[i] for i in range(3)))
        v.co.x-=dimensions[0]/2;v.co.y-=dimensions[1]/2
    for face in rock.data.polygons:face.use_smooth=True
    # Boolean cutters can create empty slots. Define the final slot only after
    # geometry is complete. Crevice growth uses an interpolated spatial mask.
    rock.data.materials.clear();rock.data.materials.append(mat);rock.data.update()
    moss_key=config['moss_texture_set']
    if moss_key not in config.get('additional_texture_sets',[]):
        raise ValueError('Moss texture dependency must be declared for source hashing')
    moss_maps=job['texture_library'][moss_key]
    src=Path(moss_maps['base']);dst=out/('crevice_base'+src.suffix);shutil.copy2(src,dst)
    moss_tex=nodes.new('ShaderNodeTexImage');moss_tex.image=bpy.data.images.load(str(dst));moss_tex.projection='BOX';moss_tex.projection_blend=.16
    links.new(mapping.outputs['Vector'],moss_tex.inputs['Vector'])
    moss_tint=[.12,.21,.07]
    multiply=nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1;multiply.inputs[2].default_value=(*moss_tint,1)
    links.new(moss_tex.outputs['Color'],multiply.inputs[1])
    attr=nodes.new('ShaderNodeVertexColor');attr.layer_name='GeologyWeather'
    separate=nodes.new('ShaderNodeSeparateColor');links.new(attr.outputs['Color'],separate.inputs[0])
    previous=bs.inputs['Base Color'].links[0].from_socket
    mixed=nodes.new('ShaderNodeMixRGB');links.new(previous,mixed.inputs[1]);links.new(multiply.outputs[0],mixed.inputs[2]);links.new(separate.outputs['Green'],mixed.inputs[0]);links.new(mixed.outputs[0],bs.inputs['Base Color'])
    binding['surface']='layered_ground';binding['layers']=[
        dict(texture_set=config['texture_set'],scale_cm=165,tint=binding['tint']),
        dict(texture_set=config['texture_set'],scale_cm=165,tint=binding['tint']),
        dict(texture_set=moss_key,scale_cm=165,tint=moss_tint)]
    mat['pipeline_binding']=json.dumps(binding)
    for face in rock.data.polygons:face.material_index=0
    bm=bmesh.new();bm.from_mesh(rock.data)
    remaining=set(bm.verts);components=[]
    while remaining:
        start=remaining.pop();stack=[start];component={start}
        while stack:
            for edge in stack.pop().link_edges:
                for v in edge.verts:
                    if v in remaining:remaining.remove(v);stack.append(v);component.add(v)
        components.append(component)
    components.sort(key=len,reverse=True);removed=sum(len(c) for c in components[1:])
    if removed/max(1,len(bm.verts))>.03:
        raise ValueError('Fracture detached a structural mass: '+str([len(c) for c in components]))
    if removed:bmesh.ops.delete(bm,geom=[v for c in components[1:] for v in c],context='VERTS')
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    bm.to_mesh(rock.data);bm.free();rock.data.update()
    if nonmanifold:raise ValueError('Outcrop is not closed: '+str(nonmanifold))
    color=rock.data.color_attributes.new(name='GeologyWeather',type='FLOAT_COLOR',domain='CORNER')
    rock.data.color_attributes.active_color=color
    weights=[]
    for v in rock.data.vertices:
        p=v.co;f=noise_vector(p*1.7+Vector((5.1,7.3,2.7))).y
        distance=min(abs(p.x+.6),abs(p.x-2.1))
        crease=math.exp(-distance/.19)*max(0,min(1,(p.z-.7)*1.5))
        ledge=math.exp(-abs(p.z-1.8)/.10)*max(0,v.normal.z)
        weights.append(min(.82,max(crease,ledge)*max(0,min(1,(f+.12)*2.5))))
    for loop in rock.data.loops:color.data[loop.index].color=(0,weights[loop.vertex_index],0,1)
    return dict(provider='blender_recipe',recipe='eroded_outcrop',components=1,removed_fracture_crumb_vertices=removed,
                nonmanifold_edges=nonmanifold,dimensions_m=dimensions,generated_geometry_reused=False,
                reason='Generated reference retained pillar topology after three preparations; broad joined rock planes are newly authored.',
                textures=binding['textures'])
