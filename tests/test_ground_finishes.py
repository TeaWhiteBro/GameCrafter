import copy,unittest
from adapters.unreal.ground_finishes import apply
from adapters.unreal.surface_wetness import evaluate_unreal

class GroundFinishTests(unittest.TestCase):
    def setUp(self):
        self.scene={'materials':{'ground':{'surface':'layered_ground','semantic_class':'terrain'}},'environment':[{'file':'fixed.fbx','collision':True}],'whitebox':{'file':'fixed_whitebox.fbx'}}
        self.library={'surface':{'base':'base.png','normal':'normal.png','roughness':'rough.png'}}
        self.finish={'ground':{'vertex_wear_surface':{'texture_set':'surface','paint_color':[.3,.4,.5],'paint_detail':.2,'scale_cm':230,'roughness':.7},'wear_zones':[{'center':[-18,-12],'radii':[8,3],'strength':.8}]}}
    def test_finish_preserves_geometry_semantics_and_source(self):
        before=copy.deepcopy(self.scene);out=apply(self.scene,self.finish,self.library)
        self.assertEqual(self.scene,before);self.assertEqual(out['environment'],before['environment']);self.assertEqual(out['whitebox'],before['whitebox'])
        self.assertEqual(out['materials']['ground']['semantic_class'],'terrain')
        self.assertEqual(evaluate_unreal(out['materials']['ground']['wear_zones'],-1800,-1200),.8)
        self.assertEqual(evaluate_unreal(out['materials']['ground']['wear_zones'],-1800,1200),0)
    def test_invalid_finish_cannot_change_geometry_or_source_path(self):
        for key,value in [('surface','pbr'),('semantic_class','paving'),('file','other.fbx')]:
            bad=copy.deepcopy(self.finish);bad['ground'][key]=value
            with self.assertRaises(ValueError):apply(self.scene,bad,self.library)
        bad=copy.deepcopy(self.finish);bad['ground']['vertex_wear_surface']['texture_set']='unknown'
        with self.assertRaises(ValueError):apply(self.scene,bad,self.library)
    def test_nonfinite_or_unbounded_surface_rejected(self):
        for key,value in [('roughness',float('nan')),('scale_cm',0),('paint_color',[1,1,9])]:
            bad=copy.deepcopy(self.finish);bad['ground']['vertex_wear_surface'][key]=value
            with self.assertRaises(ValueError):apply(self.scene,bad,self.library)
    def test_pbr_finish_keeps_existing_track_normal_and_texture(self):
        self.scene['materials']['ground'].update(surface='pbr',texture_set='surface',vertex_wear_surface={'normal_strength':.7})
        self.finish['ground']['wear_zones']=[]
        out=apply(self.scene,self.finish,self.library)
        self.assertEqual(out['materials']['ground']['vertex_wear_surface']['normal_strength'],.7)
        self.assertEqual(out['environment'],self.scene['environment'])
        self.finish['ground']['wear_zones']=[{'center':[0,0],'radii':[2,3]}]
        with self.assertRaises(ValueError):apply(self.scene,self.finish,self.library)
