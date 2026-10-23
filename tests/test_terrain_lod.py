import math,unittest
from adapters.blender.terrain_lod import refine,probe_regions

class TerrainLodTests(unittest.TestCase):
    def test_curved_surface_refines_without_relaxing_error(self):
        extent=10
        height=lambda x,y:.4*(x*x+y*y)
        points=[(-4.7+i*.31,-4.8+j*.37) for i in range(30) for j in range(26)]
        def evaluate(vs,fs):
            n=round(math.sqrt(len(vs)))-1;step=extent/n;errors=[]
            for x,y in points:
                a=(x+extent/2)/step;b=(y+extent/2)/step;i=int(a);j=int(b);u=a-i;v=b-j
                z00=vs[j*(n+1)+i][2];z10=vs[j*(n+1)+i+1][2];z01=vs[(j+1)*(n+1)+i][2];z11=vs[(j+1)*(n+1)+i+1][2]
                z=z00*(1-u-v)+z10*u+z01*v if u+v<=1 else z11*(u+v-1)+z10*(1-v)+z01*(1-u)
                errors.append(abs(z-height(x,y)))
            return errors
        _,_,audit=refine(extent,2,.5,height,evaluate)
        self.assertTrue(audit['passed']);self.assertGreater(len(audit['attempts']),1)
        self.assertGreater(audit['attempts'][0]['p95_error_m'],.18);self.assertLessEqual(audit['p95_error_m'],.18)
    def test_exhausted_refinement_stays_failed(self):
        _,_,audit=refine(5,1,.5,lambda x,y:0,lambda vs,fs:[.3]*100)
        self.assertFalse(audit['passed']);self.assertEqual(audit['attempts'][-1]['step_m'],.5)
    def test_missing_or_nonfinite_probes_cannot_pass(self):
        for values in [[],[float('nan')]]:
            with self.assertRaises(ValueError):refine(5,1,.5,lambda x,y:0,lambda vs,fs:values)

    def test_regional_error_cannot_hide_behind_sparse_global_probes(self):
        height=lambda x,y:.4*(x*x+y*y)
        global_points=[(x,y) for x in [-3,-1,1,3] for y in [-3,-1,1,3]]
        local_points=[(-2.8+i*.31,-2.6+j*.27) for i in range(10) for j in range(10)]
        def errors(vs,points):
            n=round(math.sqrt(len(vs)))-1;step=10/n;result=[]
            for x,y in points:
                a,b=(x+5)/step,(y+5)/step;i,j=int(a),int(b);u,v=a-i,b-j
                z00=vs[j*(n+1)+i][2];z10=vs[j*(n+1)+i+1][2]
                z01=vs[(j+1)*(n+1)+i][2];z11=vs[(j+1)*(n+1)+i+1][2]
                z=z00*(1-u-v)+z10*u+z01*v if u+v<=1 else z11*(u+v-1)+z10*(1-v)+z01*(1-u)
                result.append(abs(z-height(x,y)))
            return result
        _,_,audit=refine(10,2,.5,height,lambda vs,fs:errors(vs,global_points),
                        evaluate_regions=lambda vs,fs:{'bank':errors(vs,local_points)})
        first=audit['attempts'][0]
        self.assertLess(first['p95_error_m'],1e-9)
        self.assertGreater(first['regions']['bank']['p95_error_m'],.18)
        self.assertGreater(len(audit['attempts']),1)
        self.assertTrue(audit['passed'])
        self.assertLessEqual(audit['regions']['bank']['p95_error_m'],.18)

    def test_failed_or_invalid_local_evidence_cannot_pass(self):
        _,_,audit=refine(5,1,.5,lambda x,y:0,lambda vs,fs:[0]*1000,
                        evaluate_regions=lambda vs,fs:{'small_bank':[.3]*10})
        self.assertFalse(audit['passed'])
        for bad in [[],[float('nan')],[-1]]:
            with self.assertRaises(ValueError):
                refine(5,1,.5,lambda x,y:0,lambda vs,fs:[0],evaluate_regions=lambda vs,fs:{'bank':bad})

    def test_authored_regions_extend_beyond_combat_floor(self):
        regions=probe_regions(260,{'terrain_grid_m':.5,'exploration':{
            'play_bounds':{'min':[-52,-18],'max':[52,58]},
            'route_banks':[{'center':[25,40],'radii':[12,10]}]}})
        self.assertGreater(max(y for x,y in regions['playable_extent']),50)
        self.assertGreater(len(regions['route_bank_0']),1000)
        self.assertGreater(len(regions['route_bank_0_lattice']),1000)
        self.assertNotEqual(regions['route_bank_0'],regions['route_bank_0_lattice'])
        self.assertTrue(all(((x-25)/12)**2+((y-40)/10)**2<1 for x,y in regions['route_bank_0']))
        with self.assertRaises(ValueError):probe_regions(20,{'exploration':{'route_banks':[{'center':[15,0],'radii':[4,4]}]}})

if __name__=='__main__':unittest.main()
