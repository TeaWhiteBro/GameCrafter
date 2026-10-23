import copy,types,unittest
from unittest.mock import patch
from adapters.blender.modular_architecture import build,validate
from game_pipeline.contracts import normalize_design,ContractError,validate_scene_resources

class UrbanFrontageTests(unittest.TestCase):
    def item(self):
        return {'kind':'street_frontage','center':[13,-8],'size':[12,7],'height':12,
                'base_z':.08,'yaw_deg':90,'material':'concrete','timber_material':'frame',
                'roof_material':'metal','wall_material':'render','window_material':'glass',
                'lit_window_material':'lamp','letter_material':'type','sign_material':'sign',
                'urban_detail':True,'sign_text':'TRANSIT','balconies':True}

    def record(self,item,proxy):
        records=[]
        def mesh(label,vertices,faces,material):
            records.append((label,vertices,faces,material))
            return types.SimpleNamespace(data=types.SimpleNamespace(polygons=[]))
        with patch('adapters.blender.urban_frontage.lettering') as text:
            build({'cfg':{'modular_architecture':[item]},'height':lambda x,y:.2+.02*x,'mesh':mesh},proxy)
            calls=text.call_count
        return records,calls

    def test_proxy_preserves_rotated_solid_but_omits_small_services(self):
        item=self.item();detailed,letters=self.record(item,False);proxy,proxy_letters=self.record(item,True)
        d=next(x for x in detailed if x[0].endswith('urban building solid'))
        p=next(x for x in proxy if x[0].endswith('urban building solid'))
        self.assertEqual(d[1:3],p[1:3]);self.assertLess(len(proxy),len(detailed)*.7)
        self.assertGreater(letters,0);self.assertEqual(proxy_letters,0)
        self.assertAlmostEqual(max(v[0] for v in d[1])-min(v[0] for v in d[1]),7)
        self.assertTrue(any('roller shutter rib' in r[0] for r in detailed))
        self.assertFalse(any('roller shutter rib' in r[0] for r in proxy))

    def test_invalid_sign_is_rejected_before_blender(self):
        item=self.item();item['sign_text']='x'*29
        with self.assertRaisesRegex(ValueError,'28 characters'):validate([item])

    def test_wrong_owner_is_recovered_and_conflict_rejected(self):
        item=self.item();data={'scene':{'modular_architecture':[item]}}
        fixed,repairs=normalize_design(data)
        self.assertEqual(fixed['scene']['composition']['modular_architecture'],[item])
        self.assertNotIn('modular_architecture',fixed['scene']);self.assertTrue(repairs)
        conflicting=copy.deepcopy(data);conflicting['scene']['composition']={'modular_architecture':[]}
        with self.assertRaisesRegex(ContractError,'Conflicting'):normalize_design(conflicting)

    def test_footprint_failure_names_foundation_owner(self):
        material={'semantic_class':'paving'}
        scene={'materials':{'ground':{},'path':material},'floor_material':'ground','path_material':'path','objects':[],
               'composition':{'terrain_extent_m':100,'exploration':{'paving_material':'path','wall_material':'path',
               'rock_asset':'scan','plant_asset':'scan','play_bounds':{'min':[-20,-20],'max':[20,20]},
               'encounter_radius_m':10,'routes':[{'width':3,'points':[[0,0,0],[10,0,0]]}],
               'foundation_pads':[{'center':[0,7,0],'radius':3,'clear_outline':[[-2,5],[2,5],[2,9],[-2,9]]}]}}}
        machine={'mesh_library':{'scan':{}},'texture_library':{}}
        with self.assertRaisesRegex(ContractError,r'exploration.foundation_pads\[0\]'):
            validate_scene_resources(scene,machine)
        scene['composition']['exploration']['foundation_pads'][0]['surface']='none'
        validate_scene_resources(scene,machine)

if __name__=='__main__':unittest.main()
