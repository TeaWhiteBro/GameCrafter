import unittest
from types import SimpleNamespace
from adapters.blender.mesh_complexity import triangle_count

class Mesh:
    def __init__(self,faces): self.faces=faces; self.reads=0
    def as_pointer(self): return id(self)
    @property
    def polygons(self):
        self.reads+=1
        return [SimpleNamespace(vertices=list(range(n))) for n in self.faces]

class MeshComplexityTests(unittest.TestCase):
    def test_shared_and_independent_instances_keep_expanded_triangle_count(self):
        mesh=Mesh([3,4,7]); other=Mesh([3,4,7])
        self.assertEqual(triangle_count([SimpleNamespace(data=mesh)]*1000+[SimpleNamespace(data=other)]),8008)
        self.assertEqual((mesh.reads,other.reads),(1,1))

    def test_each_call_observes_current_geometry(self):
        mesh=Mesh([4]); objects=[SimpleNamespace(data=mesh)]*3
        self.assertEqual(triangle_count(objects),6)
        mesh.faces.append(5)
        self.assertEqual(triangle_count(objects),15)
        self.assertEqual(triangle_count([]),0)

if __name__=='__main__':unittest.main()
