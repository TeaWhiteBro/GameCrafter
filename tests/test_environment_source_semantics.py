import unittest
from game_pipeline.environment_semantics import validate_sources

class EnvironmentSourceSemanticsTests(unittest.TestCase):
    def test_nested_planting_missing_label_fails_before_blender(self):
        scene={'composition':{'exploration':{'planting_regions':[{'palette':[{'asset':'plant'}]}]}}}
        library={'plant':{'material':{'surface':'foliage'}}}
        with self.assertRaisesRegex(ValueError,'plant.*semantic_class'):validate_sources(scene,library)
        library['plant']['material']['semantic_class']='vegetation'
        self.assertEqual(validate_sources(scene,library),['plant'])

    def test_each_generated_slot_and_all_placement_forms_are_checked(self):
        scene={'objects':[{'asset':'building'}], 'composition':{'destination_details':[{'plant_asset':'plant'}], 'exploration':{'rock_clusters':[{'assets':['rock']}]} }}
        library={'building':{'materials':{'0':{'semantic_class':'architecture'},'1':{}}},
                 'plant':{'material':{'semantic_class':'vegetation'}},'rock':{'material':{'semantic_class':'rock'}}}
        with self.assertRaisesRegex(ValueError,'building, slot 1'):validate_sources(scene,library)
        library['building']['materials']['1']['semantic_class']='prop'
        self.assertEqual(validate_sources(scene,library),['building','plant','rock'])

    def test_unused_library_entries_do_not_fail_a_scene(self):
        self.assertEqual(validate_sources({'objects':[]},{'unused':{}}),[])

if __name__=='__main__':unittest.main()
