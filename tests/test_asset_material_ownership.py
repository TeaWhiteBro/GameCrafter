import copy,unittest
from game_pipeline.core import ROOT,read_json
from game_pipeline.contracts import validate_spec,ContractError


class MaterialOwnershipTests(unittest.TestCase):
    def test_imported_asset_can_use_its_own_material_bindings(self):
        spec=read_json(ROOT/'examples/local_assets.spec.json')
        item={'kind':'asset','asset':'provided_tree','position':[0,0,0],'scale':[4,4,6]}
        spec['scene']['objects']=[item]
        validate_spec(spec)
        item['kind']='box'
        with self.assertRaises(ContractError):validate_spec(spec)
        item['kind']='asset';item['material']='undefined_override'
        with self.assertRaises(ContractError):validate_spec(spec)
