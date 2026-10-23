import copy,unittest
from game_pipeline.contracts import normalize_design,ContractError
from adapters.blender import terrain_channels,lodge_details


class OutpostGeometryTests(unittest.TestCase):
    def test_through_terrace_preserves_two_open_ends_in_both_representations(self):
        from adapters.blender.destination_details import build
        item={'kind':'overlook_terrace','center':[0,0],'size':[8,7],'base_z':0,'timber_material':'wood','floor_material':'wood','rail_style':'timber','through_passage':True}
        for proxy in [False,True]:
            geometry=[]
            build({'cfg':{'destination_details':[item]},'spec':{'path_material':'stone'},'height':lambda x,y:0,'mesh':lambda name,vs,fs,mat,**kw:geometry.append((name,vs))},proxy)
            self.assertTrue(any('side rail' in name for name,_ in geometry))
            self.assertFalse(any('outer rail' in name or 'seat' in name for name,_ in geometry))
            for name,vs in geometry:
                xs=[p[0] for p in vs];ys=[p[1] for p in vs];zs=[p[2] for p in vs]
                if min(xs)<0<max(xs) and min(zs)<1<max(zs):
                    self.assertFalse(min(ys)<=-3.5<=max(ys),name)
                    self.assertFalse(min(ys)<=3.5<=max(ys),name)

    def test_nested_building_program_preserved_and_conflicts_rejected(self):
        item={'kind':'timber_hall','center':[2,5]}
        src={'scene':{'composition':{'exploration':{'destination_details':[item]}}}}
        normalized,repairs=normalize_design(src)
        self.assertEqual(normalized['scene']['composition']['destination_details'],[item])
        self.assertIn('destination_details',src['scene']['composition']['exploration'])
        self.assertNotIn('destination_details',normalized['scene']['composition']['exploration'])
        conflict=copy.deepcopy(src);conflict['scene']['composition']['destination_details']=[]
        with self.assertRaises(ContractError):normalize_design(conflict)

    def test_channel_surface_is_above_bed_and_faces_up(self):
        c={'points':[[0,-10],[0,0],[2,10]],'width':5,'bank_width':2,'bed_depth':.3,'surface_z':-.3,'material':'ice'}
        terrain_channels.validate([c])
        self.assertLess(terrain_channels.bed([c],0,0,.1),c['surface_z'])
        self.assertEqual(terrain_channels.bed([c],20,0,.1),.1)
        emitted=[]
        terrain_channels.build({'cfg':{'terrain_channels':[c]},'mesh':lambda *args,**kw:emitted.append(args)})
        _,vertices,faces,_=emitted[0]
        for face in faces:
            a,b,d=[vertices[i] for i in face[:3]]
            self.assertGreater((b[0]-a[0])*(d[1]-a[1])-(b[1]-a[1])*(d[0]-a[0]),0)

    def test_lodge_front_has_clear_human_portal_and_enclosed_rear(self):
        item={'size':[12,14],'height':3.9,'roof_rise':2.7,'timber_material':'wood','window_material':'light','roof_material':'snow'}
        boxes=[]
        def box(name,p,d,mat,*a,**kw):boxes.append((name,p,d))
        lodge_details.build(item,lambda x,y,z:(x,y,z),box,lambda *a,**kw:None,0,True)
        def blocked(x,y,z):
            return any(all(abs(v-p[i])<d[i]/2 for i,v in enumerate((x,y,z))) for _,p,d in boxes)
        for z in [.2,1.2,2.5]:
            for x in [-.6,0,.6]:self.assertFalse(blocked(x,7,z))
        self.assertTrue(blocked(0,-7,1.5))
        self.assertTrue(blocked(6,0,2))

if __name__=='__main__':unittest.main()
