"""Explicit normalized clipping and infill for generated static sources."""
import math


def validate(config):
    smoothing=config.get('surface_smoothing')
    if smoothing:
        if type(smoothing.get('iterations')) is not int or not 1<=smoothing['iterations']<=32:
            raise ValueError('Surface smoothing needs 1-32 iterations')
        if not 0<=smoothing.get('min_height_fraction',0)<=.9 or not 0<smoothing.get('factor',.5)<=.8:
            raise ValueError('Invalid surface smoothing region or strength')
    scales=config.get('axis_scale',[1,1,1])
    if not isinstance(scales,list) or len(scales)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not .5<=v<=2.5 for v in scales):
        raise ValueError('Static axis scales must be finite and within 0.5-2.5')
    regions=config.get('duplicate_regions',[])
    if not isinstance(regions,list) or len(regions)>3:raise ValueError('At most three local detail copies are supported')
    for region in regions:
        for key in ['min','max','offset']:
            values=region.get(key)
            if not isinstance(values,list) or len(values)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not (-1 if key=='offset' else 0)<=v<=1 for v in values):
                raise ValueError('Invalid normalized detail-copy '+key)
        if any(a>=b for a,b in zip(region['min'],region['max'])):raise ValueError('Detail-copy bounds must have volume')
    low = config.get('crop_min_z', 0)
    if type(low) not in (int, float) or not math.isfinite(low) or not 0 <= low <= .45:
        raise ValueError('Static crop must preserve at least 55 percent of source height')
    boxes = config.get('infill_boxes', [])
    if not isinstance(boxes, list) or len(boxes) > 12:
        raise ValueError('Static infill needs at most twelve bounded boxes')
    for box in boxes:
        for key in ['center', 'size', 'color']:
            values = box.get(key)
            if not isinstance(values, list) or len(values) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError('Invalid normalized static infill ' + key)
        if min(box['size']) <= 0:
            raise ValueError('Static infill size must be positive')
    stretch=config.get('lower_height_scale',{})
    if stretch and (not .25<=stretch.get('split_z',0)<=.8 or not 1<=stretch.get('factor',0)<=1.5):
        raise ValueError('Invalid lower-body architectural stretch')
    for point in config.get('closure_probe_points',[]):
        if len(point)!=3 or any(type(v) not in (int,float) or not 0<=v<=1 for v in point):
            raise ValueError('Closure probes need normalized source coordinates')
    return config


def apply(ob, config):
    import bpy, bmesh
    from mathutils import Vector
    validate(config)
    lo = Vector([min(v.co[i] for v in ob.data.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in ob.data.vertices) for i in range(3)])
    span = hi-lo
    before = len(ob.data.polygons)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    cut_z = lo.z + span.z * config.get('crop_min_z', 0)
    cap_count = 0
    if config.get('crop_min_z', 0):
        result = bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            dist=span.z*1e-6, plane_co=(0,0,cut_z), plane_no=(0,0,1), clear_inner=True, clear_outer=False)
        edges=[e for e in result['geom_cut'] if isinstance(e,bmesh.types.BMEdge) and e.is_valid and e.is_boundary]
        if edges:
            caps=bmesh.ops.holes_fill(bm,edges=edges,sides=0)
            cap_count=len(caps['faces'])
    if not bm.faces:
        bm.free();raise ValueError('Static crop removed the entire source')
    bm.to_mesh(ob.data);bm.free();ob.data.update()
    copied=[]
    for region in config.get('duplicate_regions',[]):
        bm=bmesh.new();bm.from_mesh(ob.data)
        lower=Vector([lo[i]+span[i]*region['min'][i] for i in range(3)])
        upper=Vector([lo[i]+span[i]*region['max'][i] for i in range(3)])
        faces=[f for f in bm.faces if all(lower[i]<=f.calc_center_median()[i]<=upper[i] for i in range(3))]
        if not faces:bm.free();raise ValueError('Detail-copy selection is empty')
        result=bmesh.ops.duplicate(bm,geom=faces+list({v for f in faces for v in f.verts})+list({e for f in faces for e in f.edges}))
        delta=Vector([span[i]*region['offset'][i] for i in range(3)])
        vertices=[v for v in result['geom'] if isinstance(v,bmesh.types.BMVert)]
        bmesh.ops.translate(bm,verts=vertices,vec=delta)
        copied.append({'source_faces':len(faces),'vertices':len(vertices),'bounds':[region['min'],region['max']],'offset':region['offset']})
        bm.to_mesh(ob.data);bm.free();ob.data.update()
    crop_min=min(v.co.z for v in ob.data.vertices)
    if crop_min < cut_z-span.z*2e-6:
        raise ValueError('Static crop retained geometry below the declared plane')
    pieces=[ob]
    for index,box in enumerate(config.get('infill_boxes',[])):
        center=Vector([lo[i]+span[i]*box['center'][i] for i in range(3)])
        size=Vector([span[i]*box['size'][i] for i in range(3)])
        # A closure must never recreate the removed base.
        bottom=max(cut_z,center.z-size.z/2);top=center.z+size.z/2
        if top<=bottom:raise ValueError('Infill lies entirely below crop plane')
        center.z=(bottom+top)/2;size.z=top-bottom
        bpy.ops.mesh.primitive_cube_add(size=1,location=center)
        panel=bpy.context.object;panel.name='Authored recessed closure '+str(index);panel.scale=size
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        material=bpy.data.materials.new('Recessed closure material');material.use_nodes=True
        bs=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        bs.inputs['Base Color'].default_value=(*box['color'],1)
        bs.inputs['Roughness'].default_value=.63
        material.diffuse_color=(*box['color'],1);panel.data.materials.append(material);pieces.append(panel)
    bpy.ops.object.select_all(action='DESELECT')
    for piece in pieces:piece.select_set(True)
    bpy.context.view_layer.objects.active=ob
    if len(pieces)>1:bpy.ops.object.join()
    stretch=config.get('lower_height_scale',{})
    def stretched(z):
        if not stretch:return z
        split=lo.z+span.z*stretch['split_z'];factor=stretch['factor']
        return cut_z+(z-cut_z)*factor if z<=split else z+(split-cut_z)*(factor-1)
    for v in ob.data.vertices:v.co.z=stretched(v.co.z)
    ob.data.update()
    probes=[]
    if config.get('closure_probe_points'):
        from mathutils.bvhtree import BVHTree
        tree=BVHTree.FromPolygons([v.co for v in ob.data.vertices],[list(p.vertices) for p in ob.data.polygons])
        for point in config['closure_probe_points']:
            target=Vector([lo[i]+span[i]*point[i] for i in range(3)]);target.z=stretched(target.z)
            for sign in [-1,1]:
                eye=target.copy();eye.x=(hi.x+span.x) if sign==1 else lo.x-span.x
                hit,normal,index,distance=tree.ray_cast(eye,Vector((-sign,0,0)),span.x*3.1)
                probes.append({'sample_source_fraction':point,'direction':sign,'occluded':hit is not None,
                    'first_hit_material':ob.data.materials[ob.data.polygons[index].material_index].name if hit is not None else None})
        if not all(p['occluded'] for p in probes):raise ValueError('Declared doorway closure leaves an open probe ray')
    scales=config.get('axis_scale',[1,1,1])
    for v in ob.data.vertices:
        for axis in range(3):v.co[axis]=lo[axis]+(v.co[axis]-lo[axis])*scales[axis]
    smoothing=config.get('surface_smoothing')
    smoothed=0
    if smoothing:
        bm=bmesh.new();bm.from_mesh(ob.data)
        threshold=lo.z+span.z*smoothing.get('min_height_fraction',0)
        selected=[v for v in bm.verts if v.co.z>threshold and not v.is_boundary]
        smoothed=len(selected)
        for _ in range(smoothing['iterations']):
            bmesh.ops.smooth_vert(bm,verts=selected,factor=smoothing.get('factor',.5),use_axis_x=True,use_axis_y=True,use_axis_z=True)
        bm.to_mesh(ob.data);bm.free()
    ob.data.update()
    return {'source_faces':before,'result_faces':len(ob.data.polygons),'crop_plane_source_z':cut_z,
            'crop_min_z_fraction':config.get('crop_min_z',0),'capped_cut_loops':cap_count,
            'infill_boxes':len(config.get('infill_boxes',[])),'original_bounds':[list(lo),list(hi)],
            'lower_height_scale':stretch,'closure_ray_probes':probes,
            'axis_scale':scales,'detail_copies':copied,'surface_smoothing':smoothing,'smoothed_vertices':smoothed,
            'preserved_uvs':True,'source_file_unchanged':True}
