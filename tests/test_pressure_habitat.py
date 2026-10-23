import copy,unittest
from adapters.blender.pressure_habitat import build,validate
from game_pipeline.contracts import validate_scene_resources,ContractError

class PressureHabitatTests(unittest.TestCase):
    def room(self):return {'id':'room','center':[0,0],'size':[12,16],'base_z':0,'wall_height':4.2,'roof_rise':3,
        'deck_material':'deck','frame_material':'frame','shell_material':'shell','glass_material':'glass','trim_material':'trim','light_material':'lamp',
        'doors':[{'side':'south','offset':0,'width':4,'height':3.8}]}
    def geometry(self,proxy=False):
        records=[];portals=[]
        api={'cfg':{'pressure_habitat':{'rooms':[self.room()]}},'height':lambda x,y:-6,
             'mesh':lambda name,vs,fs,material,**kw:records.append((name,vs,fs,material)), 'portal_tests':portals}
        build(api,proxy);return records,portals
    def test_proxy_preserves_floor_and_portal_but_omits_transmitting_glass(self):
        detailed,portals=self.geometry();simple,_=self.geometry(True)
        self.assertTrue(any(m=='glass' for _,_,_,m in detailed))
        self.assertFalse(any(m=='glass' for _,_,_,m in simple))
        self.assertTrue(any('dry structural deck' in n for n,_,_,_ in simple))
        self.assertEqual(len(portals),1);self.assertAlmostEqual(portals[0]['clear_width_m'],3.8)
        self.assertLess(len(simple),len(detailed))
    def test_real_door_gap_is_not_filled_by_lower_hull(self):
        records,_=self.geometry()
        for name,vs,_,_ in records:
            if 'lower pressure hull' not in name:continue
            xs=[p[0] for p in vs];ys=[p[1] for p in vs]
            self.assertFalse(min(xs)<0<max(xs) and min(ys)<-8<max(ys))
    def test_invalid_clearances_rejected(self):
        r=self.room();r['doors'][0]['width']=13
        with self.assertRaises(ValueError):validate({'rooms':[r]})
        r=self.room();r['roof_glass_fraction']=1.2
        with self.assertRaises(ValueError):validate({'rooms':[r]})
    def test_cladded_roof_is_retained_in_structural_companion(self):
        for proxy in [False,True]:
            r=self.room();r.update(roof_glass_fraction=.6,rounded_pressure_portals=True)
            rows=[];build({'cfg':{'pressure_habitat':{'rooms':[r]}},'height':lambda x,y:-6,'mesh':lambda name,vs,fs,material,**kw:rows.append((name,vs,fs,material))},proxy)
            self.assertTrue(any('insulated pressure roof panel' in n for n,_,_,_ in rows))
            self.assertTrue(any('rounded pressure-door flange' in n for n,_,_,_ in rows))
            if proxy:self.assertFalse(any(m=='glass' for _,_,_,m in rows))
        r=self.room();r['slope_y']=.4
        with self.assertRaises(ValueError):validate({'rooms':[r]})
    def test_glass_requires_bounded_non_refractive_capture_contract(self):
        material={'surface':'thin_glass','semantic_class':'architecture','capture_policy':'opaque_surface_behind_glass_v1','opacity':.04}
        validate_scene_resources({'materials':{'glass':material}}, {})
        for change in [{'refraction':1.2},{'opacity':.9},{'capture_policy':'unknown'}]:
            with self.subTest(change=change),self.assertRaises(ContractError):
                validate_scene_resources({'materials':{'glass':{**material,**change}}}, {})

    def test_flanged_ribs_preserve_structural_envelope_in_proxy(self):
        outputs=[]
        for proxy in [False,True]:
            r=self.room();r['flanged_ribs']=True
            rows=[];build({'cfg':{'pressure_habitat':{'rooms':[r]}},'height':lambda x,y:-6,
                'mesh':lambda name,vs,fs,material,**kw:rows.append((name,vs,fs,material))},proxy)
            ribs=[row for row in rows if 'vault pressure rib' in row[0]]
            self.assertTrue(ribs)
            self.assertEqual(any('flange' in row[0] for row in ribs),not proxy)
            # The companion simplifies each I-section, retaining the room span
            # and roof elevation instead of introducing an unrelated roof.
            points=[p for _,vs,_,_ in ribs for p in vs]
            outputs.append((min(p[0] for p in points),max(p[0] for p in points),max(p[2] for p in points)))
        for detailed,simple in zip(*outputs):self.assertAlmostEqual(detailed,simple,delta=.05)
        r=self.room();r['flanged_ribs']='false'
        with self.assertRaises(ValueError):validate({'rooms':[r]})

    def test_bulkhead_hardware_does_not_fill_the_actual_pressure_door(self):
        for proxy in [False,True]:
            r=self.room();r.update(bulkhead_services=True,opaque_panel_span_m=4.2,glazed_sides=['west'])
            rows=[];build({'cfg':{'pressure_habitat':{'rooms':[r]}},'height':lambda x,y:-6,
                'mesh':lambda name,vs,fs,material,**kw:rows.append((name,vs,fs,material))},proxy)
            for name,vs,_,_ in rows:
                lo=[min(p[i] for p in vs) for i in range(3)];hi=[max(p[i] for p in vs) for i in range(3)]
                self.assertFalse(all(lo[i]<point<hi[i] for i,point in enumerate([0,-8,1.2])),name)
        r=self.room();r['opaque_panel_span_m']=100
        with self.assertRaises(ValueError):validate({'rooms':[r]})

if __name__=='__main__':unittest.main()
