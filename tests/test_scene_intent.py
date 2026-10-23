import unittest
from game_pipeline.scene_intent import validate
from game_pipeline.local_lights import validate as validate_lights
from game_pipeline.contracts import ContractError

class SceneIntentTests(unittest.TestCase):
    def data(self):
        return {'scene':{'floor_material':'earth','path_material':'path',
            'materials':{'earth':{'semantic_class':'terrain'},'path':{'semantic_class':'paving'}},
            'composition':{'exploration':{'paving_material':'path','routes':[
                {'id':'approach','points':[[0,0,0],[10,0,0]],'width':3}]}}},'lighting':{}}

    def test_solid_tower_at_route_endpoint_fails_before_mesh_build(self):
        data=self.data();data['scene']['composition']['destination_details']=[{'kind':'bell_tower','center':[10,0],'width':3.4}]
        with self.assertRaisesRegex(ContractError,'overlaps route'):validate(data)
        data['scene']['composition']['destination_details'][0]['center']=[10,8];validate(data)

    def test_ignored_texture_and_wrong_floor_semantics_are_reported_together(self):
        data=self.data();data['scene']['materials']['path'].update(surface='metal',texture_set='real_scan',semantic_class='architecture')
        with self.assertRaises(ContractError) as context:validate(data)
        self.assertIn('ignores texture_set',str(context.exception));self.assertIn('requires semantic_class paving',str(context.exception))

    def test_roof_cannot_begin_at_body_height_over_route(self):
        data=self.data();data['scene']['composition']['destination_details']=[{'kind':'vault_liner','center':[5,0],'radius':4,'base_z':.14}]
        with self.assertRaisesRegex(ContractError,'head clearance'):validate(data)
        data['scene']['composition']['destination_details'][0]['base_z']=4;validate(data)

    def test_practical_lights_have_explicit_physical_units(self):
        light={'position':[1,2,3],'color':[1,.5,.2],'intensity_lm':1200,'range_m':6}
        self.assertEqual(validate_lights({'local_lights':[light]}),[light])
        for delta in [{'intensity':8},{'range_m':-1},{'intensity_lm':None},{'color':[1,2,3]}]:
            with self.subTest(delta=delta),self.assertRaises(ValueError):validate_lights({'local_lights':[{**light,**delta}]})

    def test_partial_wetness_has_bounded_pbr_contract(self):
        data=self.data();material=data['scene']['materials']['path'];material.update(surface='pbr',wetness=.7,wetness_scale_m=2)
        validate(data)
        for key,value in [('wetness',1.1),('wetness',float('nan')),('wetness_scale_m',0),('surface','metal')]:
            original=dict(material);material[key]=value
            with self.assertRaisesRegex(ContractError,'wetness'):validate(data)
            material.clear();material.update(original)

if __name__=='__main__':unittest.main()
