"""Replace coarse pale generated canopy surfaces with measured, attached flower sprays.

This optional static-asset operation uses its actual UV albedo and retained woody
geometry. It creates mesh geometry, never particles or unrelated floating cards.
"""
import bpy,bmesh,math,random
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

def refine(ob,settings,image):
    rng=random.Random(settings.get('seed',421));height=max(v.co.z for v in ob.data.vertices)
    pixels=np.asarray(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
    uv=ob.data.uv_layers.active
    if uv is None:raise ValueError('Botanical refinement requires source UVs and albedo')
    selected=[];samples=[];wood_indices=set()
    for face in ob.data.polygons:
        coord=sum((uv.data[i].uv for i in face.loop_indices),Vector((0,0)))/len(face.loop_indices)
        pixel=pixels[min(image.size[1]-1,int((coord.y%1)*image.size[1])),min(image.size[0]-1,int((coord.x%1)*image.size[0]))]
        bright=float(min(pixel[:3]))>settings.get('pale_threshold',.42)
        if bright and face.center.z>height*.22:
            selected.append(face.index);samples.append(face.center.copy())
        else:wood_indices.update(face.vertices)
    if len(selected)<100 or len(wood_indices)<100:raise ValueError('No reliable canopy/wood separation; inspect current atlas')
    wood=KDTree(len(wood_indices))
    for index,vi in enumerate(wood_indices):wood.insert(ob.data.vertices[vi].co,index)
    wood.balance()
    cell=settings.get('cluster_spacing_m',.34);cells={}
    for p in samples:
        key=tuple(round(v/cell) for v in p)
        if key not in cells or rng.random()<.12:cells[key]=p
    bm=bmesh.new();bm.from_mesh(ob.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[bm.faces[i] for i in selected],context='FACES')
    orphan=[v for v in bm.verts if not v.link_faces]
    if orphan:bmesh.ops.delete(bm,geom=orphan,context='VERTS')
    bm.to_mesh(ob.data);bm.free();ob.data.update()
    verts=[];faces=[];material_indices=[];colors=[]
    def add(vs,fs,mi):
        offset=len(verts);verts.extend(vs);faces.extend([tuple(offset+i for i in f) for f in fs]);material_indices.extend([mi]*len(fs))
    def stem(a,b,r=.005):
        z=(b-a).normalized();x=z.cross(Vector((0,0,1)))
        if x.length<.01:x=Vector((1,0,0))
        x.normalize();y=z.cross(x)
        vs=[p+(x*math.cos(i*math.tau/5)+y*math.sin(i*math.tau/5))*r for p in [a,b] for i in range(5)]
        add(vs,[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)],0)
    colors=settings.get('petal_colors',[[.94,.38,.58],[1,.59,.71],[.97,.73,.8],[.86,.29,.48]])
    materials=[]
    for index,color in enumerate([[.11,.045,.027]]+colors+[[.075,.23,.027]]):
        mat=bpy.data.materials.new('Botanical_'+str(index));mat.use_nodes=True;mat.diffuse_color=(*color,1)
        mat['pipeline_collision']=False
        bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.68
        if index:mat['pipeline_surface']='botanical'
        materials.append(mat)
    count=0;attached=0
    for key,center in sorted(cells.items()):
        root,_,distance=wood.find(center)
        if distance>settings.get('max_attachment_m',1.1):continue
        attached+=1;stem(root,center,.007)
        for i in range(settings.get('flowers_per_cluster',18)):
            direction=Vector((rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(-.35,1))).normalized()
            p=center+direction*rng.uniform(.018,.17);stem(center,p,.002)
            normal=(direction+Vector((0,0,.35))).normalized();xx=normal.cross(Vector((0,0,1)))
            if xx.length<.03:xx=Vector((1,0,0))
            xx.normalize();yy=normal.cross(xx);size=rng.uniform(*settings.get('flower_radius_m',[.022,.036]));phase=rng.uniform(0,math.tau)
            mi=rng.choices(range(1,len(colors)+1),weights=[.3,.4,.22,.08])[0]
            for petal in range(5):
                a=phase+petal*math.tau/5;axis=xx*math.cos(a)+yy*math.sin(a);side=normal.cross(axis)
                points=[p,p+axis*size*.48-side*size*.35+normal*size*.12,p+axis*size*.94-side*size*.30+normal*size*.20,
                    p+axis*size*1.04+normal*size*.12,p+axis*size*.94+side*size*.30+normal*size*.20,p+axis*size*.48+side*size*.35+normal*size*.12]
                add(points,[(0,1,2),(0,2,3),(0,3,4),(0,4,5)],mi)
            if i%9==0:
                q=p-direction*.02;leaf_axis=direction*.10;side=normal.cross(direction)
                if side.length<.05:side=xx
                side=side.normalized()*.025
                add([q,q+leaf_axis*.5-side,q+leaf_axis,q+leaf_axis*.5+side],[(0,1,2),(0,2,3)],len(materials)-1)
            count+=1
    me=bpy.data.meshes.new('Fine botanical sprays');me.from_pydata(verts,[],faces);me.update()
    for mat in materials:me.materials.append(mat)
    for p,index in zip(me.polygons,material_indices):p.material_index=index;p.use_smooth=True
    spray=bpy.data.objects.new('Fine botanical sprays',me);bpy.context.collection.objects.link(spray)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);spray.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
    return {'method':'source UV canopy segmentation + nearest woody support + explicit flower geometry',
        'replaced_faces':len(selected),'attached_sprays':attached,'flowers':count,'max_stem_distance_m':settings.get('max_attachment_m',1.1),
        'flower_radius_m':settings.get('flower_radius_m',[.022,.036]),
        'particle_systems':0,'source_bark_material_preserved':True}
