import unittest,copy
from adapters.blender.material_variants import binding

class MaterialVariants(unittest.TestCase):
 def setUp(self):self.source={'file':'source.glb','material_id':'tree','materials':{'0':{'name':'bark','color':[.1,.1,.1]},'1':{'name':'flower','color':[1,.4,.7]}}}
 def test_palette_reuses_source_without_mutating_binding_or_slot_identity(self):
  before=copy.deepcopy(self.source);result=binding(self.source,{'white':{'1':{'color':[1,1,1]}}},'white')
  self.assertEqual(self.source,before);self.assertEqual(result['file'],before['file']);self.assertEqual(result['materials']['0'],before['materials']['0'])
  self.assertEqual(result['materials']['1']['name'],'flower');self.assertEqual(result['materials']['1']['color'],[1,1,1]);self.assertNotEqual(result['material_id'],before['material_id'])
 def test_unknown_slots_and_invalid_parameters_reject(self):
  for patch in [{'2':{'color':[1,1,1]}},{'1':{'color':[float('nan'),0,0]}},{'1':{'textures':{}}}]:
   with self.assertRaises(ValueError):binding(self.source,{'bad':patch},'bad')
