"""Optional multi-stem botanical assembly preserving whole source branches and UVs."""
import math
import bpy
from mathutils import Matrix,Vector

def build(ob,settings,height):
    stems=settings.get('stems',[])
    if not 2<=len(stems)<=9:raise ValueError('A botanical clump requires 2-9 measured whole stems')
    original=ob.data.copy();parts=[]
    for i,stem in enumerate(stems):
        scale=stem['scale'];offset=stem['offset'];yaw=stem['yaw_deg']
        if not .3<=scale<=1 or len(offset)!=2 or any(not math.isfinite(v) or abs(v)>2 for v in offset):raise ValueError('Invalid whole-stem clump transform')
        part=ob if i==0 else ob.copy()
        part.data=original.copy()
        if i:bpy.context.collection.objects.link(part)
        part.data.transform(Matrix.Translation(Vector((*offset,0)))@Matrix.Rotation(math.radians(yaw),4,'Z')@Matrix.Scale(scale,4))
        parts.append(part)
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:part.select_set(True)
    bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
    # Preserve canopy proportions while giving all rooted stems a natural
    # widening into soil. The lowest 12 cm belongs below the planting surface.
    if settings.get('root_flare'):
        for v in ob.data.vertices:
            if v.co.z<.16:
                nearest=min(stems,key=lambda s:(v.co.x-s['offset'][0])**2+(v.co.y-s['offset'][1])**2)
                t=max(0,1-v.co.z/.16);x,y=nearest['offset']
                v.co.x=x+(v.co.x-x)*(1+.65*t);v.co.y=y+(v.co.y-y)*(1+.65*t)
        for polygon in ob.data.polygons:polygon.use_smooth=True
    lo=Vector(tuple(min(v.co[i] for v in ob.data.vertices) for i in range(3)));hi=Vector(tuple(max(v.co[i] for v in ob.data.vertices) for i in range(3)))
    origin=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    ob.data.transform(Matrix.Scale(height/(hi.z-lo.z),4)@Matrix.Translation(-origin));ob.data.update()
    return {'method':'Whole-source multi-stem botanical assembly with preserved UVs and rooted transforms','stems':stems,'source_parts_split':False,'output_height_m':height,'root_flare':bool(settings.get('root_flare'))}
