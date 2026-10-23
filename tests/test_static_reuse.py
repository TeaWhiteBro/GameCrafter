import unittest,tempfile,copy
from pathlib import Path
from game_pipeline.static_reuse import eligible
from game_pipeline.core import digest
class StaticReuseTests(unittest.TestCase):
 def test_requires_source_package_settings_and_import_contract(self):
  with tempfile.TemporaryDirectory() as td:
   source=Path(td)/'mesh.fbx';source.write_bytes(b'fbx-v1');package=Path(td)/'mesh.uasset';package.write_bytes(b'asset-v1')
   entry={'file':str(source),'material':'stone','collision':True,'semantic_id':3,'triangles':12000};old=copy.deepcopy(entry);sh,ph=digest(source),digest(package)
   self.assertTrue(eligible(entry,old,sh,package,ph,'import-v1','import-v1'))
   self.assertFalse(eligible(entry,old,sh,package,ph,'import-v2','import-v1'))
   for key,value in [('material','wood'),('collision',False),('semantic_id',4),('triangles',12)]:
    changed={**entry,key:value};self.assertFalse(eligible(changed,old,sh,package,ph,'import-v1','import-v1'))
 def test_tampered_source_is_not_reused(self):
  with tempfile.TemporaryDirectory() as td:
   source=Path(td)/'mesh.fbx';source.write_bytes(b'a');package=Path(td)/'mesh.uasset';package.write_bytes(b'b');entry={'file':str(source)};sh=digest(source);source.write_bytes(b'changed')
   self.assertFalse(eligible(entry,entry,sh,package,digest(package),'v1','v1'))
 def test_tampered_package_is_not_reused(self):
  with tempfile.TemporaryDirectory() as td:
   source=Path(td)/'mesh.fbx';source.write_bytes(b'a');package=Path(td)/'mesh.uasset';package.write_bytes(b'b');entry={'file':str(source)};ph=digest(package);package.write_bytes(b'changed')
   self.assertFalse(eligible(entry,entry,digest(source),package,ph,'v1','v1'))
