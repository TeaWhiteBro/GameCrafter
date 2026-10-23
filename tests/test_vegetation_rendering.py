import unittest,copy
from types import SimpleNamespace as NS
from adapters.unreal.vegetation_rendering import configure,preservation_property

class Mesh:
 def __init__(self):self.settings=NS(enabled=False,preserve_area=False,fallback_target='relative',fallback_percent_triangles=1.,fallback_relative_error=1.);self.writes=0
 def get_editor_property(self,key):return copy.copy(self.settings)
 def set_editor_property(self,key,value):self.settings=copy.copy(value);self.writes+=1

class FoliageRenderingTests(unittest.TestCase):
 def test_ue58_enum_binding_is_selected(self):
  api=NS(NaniteShapePreservation=NS(PRESERVE_AREA=2),NaniteFallbackTarget=NS(PERCENT_TRIANGLES='percent'),MaterialUsage=NS(MATUSAGE_NANITE='nanite'),MaterialEditingLibrary=NS(set_material_usage=lambda m,u:None))
  mesh=Mesh();del mesh.settings.preserve_area;mesh.settings.shape_preservation=0
  r=configure(api,mesh,'material',{'collision':False,'semantic_id':5,'triangles':20000,'material':'grass'},lambda o:None)
  self.assertEqual(mesh.settings.shape_preservation,2);self.assertTrue(r['preserve_area']);self.assertFalse(hasattr(mesh.settings,'preserve_area'))
 def test_unknown_sdk_is_an_explicit_failure(self):
  with self.assertRaisesRegex(RuntimeError,'no supported'):preservation_property(None,NS(enabled=False))
 def test_nonblocking_foliage_gets_area_preservation_and_no_duplicate_rebuild(self):
  api=NS(NaniteFallbackTarget=NS(PERCENT_TRIANGLES='percent'),MaterialUsage=NS(MATUSAGE_NANITE='nanite'),MaterialEditingLibrary=NS(set_material_usage=lambda m,u:None))
  mesh=Mesh();entry={'collision':False,'semantic_id':5,'triangles':12000000,'material':'leaves'};saved=[]
  r=configure(api,mesh,'material',entry,saved.append)
  self.assertTrue(r['nanite_enabled'] and r['preserve_area']);self.assertEqual(mesh.writes,1)
  self.assertFalse(configure(api,mesh,'material',entry,saved.append)['changed']);self.assertEqual(mesh.writes,1)
 def test_colliding_geometry_cannot_inherit_reduced_collision_fallback(self):
  mesh=Mesh()
  for sid,col in [(5,True),(1,True),(4,True),(6,False)]:
   self.assertIsNone(configure(None,mesh,None,{'collision':col,'semantic_id':sid,'triangles':900000},None))
  self.assertEqual(mesh.writes,0)
