"""Bound FBX/UE construction memory without changing geometry or source detail."""
import math

def join_objects(objects):
    import bpy
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    active=objects[0]
    # Generated atlas parts share mesh templates across every instance. A
    # partial batch must own its active mesh before joining or baking transforms.
    if active.data.users>1:active.data=active.data.copy()
    bpy.context.view_layer.objects.active=active
    if len(objects)>1:
        result=bpy.ops.object.join()
        if 'FINISHED' not in result:raise ValueError('Geometry batch join failed')
    ob=bpy.context.object
    if ob.data.users>1:raise ValueError('Geometry batch still shares mutable source data')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    return ob

def partition(items,triangles,position,limit=4000000):
    if type(limit) is not int or not 10000<=limit<=8000000:raise ValueError('Export batch limit must be an integer in 10,000-8,000,000 triangles')
    records=[(item,int(triangles(item))) for item in items]
    if any(n>limit for _,n in records):raise ValueError('A single source object exceeds the export batch budget; subdivide it spatially before assembly')
    if sum(n for _,n in records)<=limit:return [list(items)] if records else []
    def key(record):
        p=position(record[0]);return (math.floor(p[0]/16),math.floor(p[1]/16),p[0],p[1])
    records.sort(key=key)
    batches=[];current=[];count=0
    for item,n in records:
        if current and count+n>limit:batches.append(current);current=[];count=0
        current.append(item);count+=n
    if current:batches.append(current)
    return batches

def build(groups,limit=4000000):
    batches=[];audit=[]
    def triangles(ob):return sum(len(p.vertices)-2 for p in ob.data.polygons)
    for key,objects in groups.items():
        counts={ob.as_pointer():triangles(ob) for ob in objects}
        chunks=partition(objects,lambda ob:counts[ob.as_pointer()],lambda ob:ob.matrix_world.translation,limit)
        for chunk in chunks:
            batches.append((key,chunk));audit.append({'material':key[0],'collision':key[1],'objects':len(chunk),'source_triangles':sum(counts[ob.as_pointer()] for ob in chunk)})
    return batches,{'max_source_triangles_per_batch':limit,'original_material_groups':len(groups),'export_batches':len(batches),'geometry_decimated':False,'batches':audit}
