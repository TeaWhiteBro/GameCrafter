import types,unittest,copy
from adapters.blender.modular_architecture import build,validate

class UrbanSystemsTests(unittest.TestCase):
    def item(self,kind):
        return {'kind':kind,'center':[7,-3],'size':[4,6],'height':1.2,'base_z':.8,'yaw_deg':0,
                'material':'concrete','timber_material':'frame','roof_material':'metal','window_material':'graphic'}

    def collect(self,item,proxy=False):
        rows=[]
        def mesh(name,vertices,faces,material,**kwargs):
            uv=types.SimpleNamespace(data=[types.SimpleNamespace(uv=None) for _ in range(sum(len(f) for f in faces))])
            loops=[types.SimpleNamespace(index=i,vertex_index=v) for i,v in enumerate(v for f in faces for v in f)]
            ob=types.SimpleNamespace(data=types.SimpleNamespace(polygons=[],loops=loops,uv_layers=types.SimpleNamespace(new=lambda **k:uv)))
            rows.append({'name':name,'vertices':vertices,'faces':faces,'uv':uv,'options':kwargs,'material':material})
            return ob
        build({'cfg':{'modular_architecture':[item]},'height':lambda x,y:.2+.01*x,'mesh':mesh},proxy)
        return rows

    def test_graphic_plane_has_readable_uv_and_separate_noncolliding_geometry(self):
        detailed=self.collect(self.item('graphic_panel'));proxy=self.collect(self.item('graphic_panel'),True)
        face=next(r for r in detailed if r['name'].endswith('graphic display'))
        self.assertEqual(face['options'],{'collision':False,'preserve_winding':True})
        self.assertEqual([v.uv for v in face['uv'].data],[(1,0),(0,0),(0,1),(1,1)])
        self.assertEqual(detailed[0]['vertices'],proxy[0]['vertices'])
        self.assertEqual(len(proxy),1)

    def test_access_ramp_has_continuous_planar_surface_and_matching_proxy(self):
        item=self.item('access_ramp');d=self.collect(item);p=self.collect(item,True)
        self.assertEqual(d[0]['vertices'],p[0]['vertices']);self.assertEqual(len(p),1)
        for x,y,z in d[0]['vertices'][4:]:self.assertAlmostEqual(z,.8+((y+3)/6+.5)*1.2)
        self.assertTrue(any('handrail' in row['name'] for row in d))

    def test_assembly_preserves_rotated_structural_solids_and_omits_only_small_trim(self):
        item=self.item('box_assembly');item['parts']=[
            {'position':[1,2,.4],'scale':[2,4,3],'yaw_deg':90,'material':'concrete'},
            {'position':[0,0,3.2],'scale':[2,.04,.04],'material':'lamp'}]
        d=self.collect(item);p=self.collect(item,True)
        self.assertEqual(d[0]['vertices'],p[0]['vertices']);self.assertEqual(len(d),2);self.assertEqual(len(p),1)
        vs=d[0]['vertices'];self.assertAlmostEqual(max(v[0] for v in vs)-min(v[0] for v in vs),4)
        self.assertAlmostEqual(min(v[2] for v in vs),.4)

    def test_invalid_assemblies_and_missing_graphics_rejected(self):
        item=self.item('graphic_panel');item.pop('window_material')
        with self.assertRaisesRegex(ValueError,'window_material'):validate([item])
        item=self.item('box_assembly');item['parts']=[]
        with self.assertRaisesRegex(ValueError,'1-128'):validate([item])
        item['parts']=[{'position':[0,0,0],'scale':[1,1,float('nan')],'material':'x'}]
        with self.assertRaisesRegex(ValueError,'finite'):validate([item])

    def test_roof_equipment_keeps_authored_elevation_and_major_proxy_geometry(self):
        for service,elevation in [('tank',14),('hvac',45),('antenna',60)]:
            item=self.item('roof_service');item.update(base_z=elevation,service_type=service,height=3.6,yaw_deg=57)
            detailed=self.collect(item);proxy=self.collect(item,True)
            self.assertGreater(len(detailed),len(proxy))
            self.assertGreaterEqual(min(p[2] for row in detailed for p in row['vertices']),elevation-1e-6)
            mapping={row['name']:row for row in detailed}
            for row in proxy:
                self.assertIn(row['name'],mapping)
                a=row['vertices'];b=mapping[row['name']]['vertices']
                for axis in [2]:
                    self.assertAlmostEqual(min(v[axis] for v in a),min(v[axis] for v in b))
                    self.assertAlmostEqual(max(v[axis] for v in a),max(v[axis] for v in b))

    def test_roof_equipment_rejects_unknown_layout_and_undersized_platform(self):
        item=self.item('roof_service');item['service_type']='unimplemented'
        with self.assertRaisesRegex(ValueError,'service_type'):validate([item])
        item['service_type']='tank';item['size']=[1,3]
        with self.assertRaisesRegex(ValueError,'two metres'):validate([item])
        item['size']=[4,6];item.update(base_z=79,height=3.6)
        with self.assertRaisesRegex(ValueError,'80m world envelope'):validate([item])
        item['kind']='access_ramp';item['base_z']=45
        with self.assertRaisesRegex(ValueError,'base_z'):validate([item])

if __name__=='__main__':unittest.main()
