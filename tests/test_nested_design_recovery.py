import copy
import unittest
from game_pipeline.contracts import normalize_design, ContractError

class NestedDesignRecovery(unittest.TestCase):
    def test_recovers_root_then_scene_without_mutating_response(self):
        value={'art_direction':{'summary':'Marine station','concept_prompt':'Interior',
            'concept':{'provider':'gpt_image'},'characters':{'player':{},'boss':{}},
            'scene':{'size_m':30,'spawns':{'player':[0,-4,0],'boss':[0,4,0]},'lighting':{'sky_intensity':.5},'gameplay':{'target_fps':60}}}}
        original=copy.deepcopy(value)
        result,repairs=normalize_design(value)
        self.assertEqual(value,original)
        self.assertEqual(set(result['characters']),{'player','boss'})
        self.assertEqual(result['spawns'],original['art_direction']['scene']['spawns'])
        self.assertEqual(set(result['art_direction']),{'summary','concept_prompt'})
        self.assertEqual(result['scene'],{'size_m':30})
        self.assertEqual(len(repairs),6)
        self.assertEqual(normalize_design(result),(result,[]))

    def test_rejects_competing_root_value(self):
        with self.assertRaises(ContractError):
            normalize_design({'characters':{'player':{}},'art_direction':{'characters':{'boss':{}}}})

    def test_does_not_create_missing_roles(self):
        result,_=normalize_design({'art_direction':{'summary':'No schema supplied'}})
        self.assertNotIn('characters',result)

if __name__=='__main__':unittest.main()
