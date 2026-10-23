"""Replace source roof sheets with one bounded, thick accumulation surface."""
import math
import numpy as np
import bpy,bmesh

def refine(ob,cfg,image):
    # Explicit measured dimensions are preparation data, not per-asset branches.
    ridge=float(cfg['ridge_z']);slope=float(cfg['slope']);length=float(cfg['length']);width=float(cfg['width'])
    if min(ridge,slope,length,width)<=0:raise ValueError('Invalid snow-cap measurements')
    coords=np.asarray([v.co[:] for v in ob.data.vertices]);high=coords[coords[:,2]>cfg['chimney_above_z']]
    if not len(high):raise ValueError('Missing independently measured chimney region')
    low_xy=high[:,:2].min(0)-.12;high_xy=high[:,:2].max(0)+.12
    pixels=np.asarray(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
    uv=ob.data.uv_layers.active;selected=[]
    for face in ob.data.polygons:
        x,y,z=face.center
        if z<cfg['remove_above_z']:continue
        if low_xy[0]<=x<=high_xy[0] and low_xy[1]<=y<=high_xy[1] and z>ridge-.35:continue
        t=sum((uv.data[i].uv for i in face.loop_indices),uv.data[face.loop_start].uv*0)/len(face.loop_indices)
        rgb=pixels[int(t.y%1*(image.size[1]-1)),int(t.x%1*(image.size[0]-1)),:3]
        roof_line=ridge-slope*math.sqrt(y*y+.0225)
        if (min(rgb)>.38 and max(rgb)-min(rgb)<.15) or z>roof_line-.14:selected.append(face.index)
    if len(selected)<100:raise ValueError('Snow mask did not identify source sheets')
    bm=bmesh.new();bm.from_mesh(ob.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[bm.faces[i] for i in selected],context='FACES')
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bm.to_mesh(ob.data);bm.free()
    mat=bpy.data.materials.new('Continuous roof snow');mat.diffuse_color=(.66,.72,.77,1);mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=mat.diffuse_color;bs.inputs['Roughness'].default_value=.87
    ob.data.materials.append(mat);material=len(ob.data.materials)-1
    bm=bmesh.new();bm.from_mesh(ob.data);nx=48;ny=48;rings=[]
    for lower in [False,True]:
        ring=[]
        for j in range(ny+1):
            row=[]
            for i in range(nx+1):
                x=(i/nx-.5)*length
                edge=.08*math.sin(x*1.6)+.04*math.sin(x*3.3)
                y=(j/ny-.5)*(width+edge)
                z=ridge-slope*math.sqrt(y*y+.04)+.055*math.sin(x*1.35+y*.8)+.032*math.cos(x*2.5-y*1.7)
                z-=.06*max(abs(x)/(length/2),abs(y)/(width/2))**12
                if lower:z-=.18
                row.append(bm.verts.new((x,y,z)))
            ring.append(row)
        rings.append(ring)
    created=[]
    def face(vertices):
        f=bm.faces.new(vertices);f.material_index=material;f.smooth=True;created.append(f)
    for k,r in enumerate(rings):
        for j in range(ny):
            for i in range(nx):
                vs=[r[j][i],r[j][i+1],r[j+1][i+1],r[j+1][i]]
                face(list(reversed(vs)) if k else vs)
    for i in range(nx):
        for j in [0,ny]:face([rings[0][j][i],rings[0][j][i+1],rings[1][j][i+1],rings[1][j][i]])
    for j in range(ny):
        for i in [0,nx]:face([rings[0][j][i],rings[0][j+1][i],rings[1][j+1][i],rings[1][j][i]])
    bmesh.ops.recalc_face_normals(bm,faces=created);bm.to_mesh(ob.data);bm.free();ob.data.update()
    return {'removed_source_faces':len(selected),'cap_quads':len(created),'cap_thickness_m':.18,'preserved_chimney_bounds_xy':[low_xy.tolist(),high_xy.tolist()],'measurements':cfg}
