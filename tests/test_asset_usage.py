import unittest
from game_pipeline.asset_usage import consumed_texture_sets,summarize

class AssetUsageTests(unittest.TestCase):
    def test_unused_definitions_and_procedural_names_are_not_usage(self):
        report={'environment':[{'material':'floor','triangles':20},{'material':'trim','triangles':8}],
            'materials':{'floor':{'surface':'pbr','texture_set':'brick'},'trim':{'surface':'metal','texture_set':'unused_iron'},
                'unused':{'surface':'pbr','texture_set':'snow'}}}
        audit=summarize(report,{})
        self.assertEqual(audit['texture_sets'],['brick'])
        self.assertEqual(audit['unused_material_definitions'],['unused'])

    def test_layered_material_uses_layers_not_unused_base_alias(self):
        self.assertEqual(consumed_texture_sets({'surface':'layered_ground','texture_set':'unused',
            'layers':[{'texture_set':x} for x in ['earth','stone','litter']]}),{'earth','stone','litter'})

    def test_aliases_need_real_instance_evidence(self):
        report={'environment':[{'material':'shared','triangles':25}],'materials':{'shared':{'surface':'scan'}},
            'asset_instances':{'whole_plant':{'count':4}}}
        machine={'mesh_library':{'whole_plant':{'material_id':'shared'},'plant_alias':{'material_id':'shared'}}}
        plan={'regions':[{'meshes':['whole_plant','plant_alias'],'textures':[]}]}
        audit=summarize(report,machine,plan)
        self.assertEqual(audit['planned_not_observed']['meshes'],['plant_alias'])
        self.assertEqual(audit['legacy_material_candidates'],{})

if __name__=='__main__':unittest.main()
