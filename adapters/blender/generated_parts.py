"""Keep an imported assembly's atlas slots and one shared structural proxy."""
import json
import bpy,bmesh
from pathlib import Path
PARTS={}

def register(conf,materials):
    if conf.get('materials'):
        for key,value in conf['materials'].items():materials[conf['material_id']+'_'+key]=value
    else:materials[conf['material_id']]=conf['material']

def group_instance(ob,conf,groups,collision):
    bindings=conf.get('materials')
    if not bindings:
        groups.setdefault((conf['material_id'],collision),[]).append(ob);return ob
    by_name={v['name']:k for k,v in bindings.items()}
    identity=ob.data.get('pipeline_source_key')
    if identity in PARTS:
        pieces=[]
        for key,mesh in PARTS[identity]:
            part=ob.copy();part.data=mesh;bpy.context.collection.objects.link(part)
            part['whitebox_instance']=not pieces
            effective=collision and bindings[key].get('collision',True)
            groups.setdefault((conf['material_id']+'_'+key,effective),[]).append(part);pieces.append(part)
        bpy.data.objects.remove(ob,do_unlink=True)
        return pieces[0]
    used=sorted({p.material_index for p in ob.data.polygons});parts=[]
    cached=[]
    for index in used:
        source_name=ob.data.materials[index].name
        if source_name not in by_name:raise ValueError('Generated material mapping missing: '+source_name)
        key=by_name[source_name]
        part=ob.copy();part.data=ob.data.copy();bpy.context.collection.objects.link(part)
        bm=bmesh.new();bm.from_mesh(part.data)
        remove=[f for f in bm.faces if f.material_index!=index]
        if remove:bmesh.ops.delete(bm,geom=remove,context='FACES')
        isolated=[v for v in bm.verts if not v.link_faces]
        if isolated:bmesh.ops.delete(bm,geom=isolated,context='VERTS')
        bm.to_mesh(part.data);bm.free();part.data.update()
        part['whitebox_instance']=not parts
        part.data['pipeline_proxy_file']=conf['structural_proxy']
        effective=collision and bindings[key].get('collision',True)
        groups.setdefault((conf['material_id']+'_'+key,effective),[]).append(part);parts.append(part)
        cached.append((key,part.data))
    PARTS[identity]=cached
    bpy.data.objects.remove(ob,do_unlink=True)
    return parts[0]

def proxy_mesh(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    mesh=bpy.data.meshes.new('Generated structural proxy')
    mesh.from_pydata(data['vertices'],[],data['faces']);mesh.update();return mesh
