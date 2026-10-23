import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/unreal'))
from material_slots import material_index


class MaterialSlotTests(unittest.TestCase):
    def test_reordered_meshes_keep_body_and_detail_materials(self):
        source=[{'name':'Body-Texture'},{'name':'Tail'},{'name':'Tuft'}]
        imported=['Tail','Tuft','Body_Texture']
        self.assertEqual([material_index(n,n,source) for n in imported],[1,2,0])

    def test_missing_or_colliding_names_fail_instead_of_using_slot_order(self):
        for source,name in [([{'name':'Body'}],'Unknown'),([{'name':'body-a'},{'name':'body_a'}],'body_a')]:
            with self.assertRaisesRegex(ValueError,'uniquely match'):material_index(name,name,source)
