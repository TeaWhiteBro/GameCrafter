"""Run with Blender --background --factory-startup --python this_file.

Checks actual Blender polygons after the production normal recalculation.
Boundary cells must retain an upward crown without self-intersection.
"""
import pathlib, random, sys
import bpy, bmesh
from mathutils import Vector, noise
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'adapters/blender'))
from courtyard import fitted_court
from landscape_routes import fitted_patch

count=0
def mesh(name,vertices,faces,material,**kwargs):
    global count
    data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.update()
    bm=bmesh.new();bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(data);bm.free();data.update()
    n=(len(vertices)-1)//2
    for face in list(data.polygons)[1:1+n]:
        assert face.normal.z>.65,(name,vertices[-1],tuple(face.normal))
    assert data.polygons[0].normal.z<-.65
    count+=1;bpy.data.meshes.remove(data)

def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)

for seed in [13,417,903]:
    api={'cfg':{'court_radii':[10,10],'court_base_z':.08,'scatter':{}},
        'rng':random.Random(seed),'center':[0,0],'court':lambda x,y:((x/10)**2+(y/10)**2)**.5,
        'mesh':mesh,'finish_stone':lambda ob,w:ob,'spec':{'path_material':'stone'},
        'n':lambda x,y,s=.2,z=1:noise.noise_vector(Vector((x*s,y*s,z)))[0],
        'smooth':smooth,'height':lambda x,y:.3+.04*y}
    fitted_court(api)
    fitted_patch(api,[[-2,-10],[2,-10],[2,10],[-2,10]],'stone')
assert count>1500
print('NATIVE_PAVING_NORMALS_PASSED',count)
