import random,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from modular_paving import cells,patch,difference,uncovered

def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,list(poly[1:])+[poly[0]])))/2

def contains(poly,point):
    turns=[np.cross(np.asarray(b)-a,np.asarray(point)-a) for a,b in zip(poly,list(poly[1:])+[poly[0]])]
    return all(t>1e-7 for t in turns) or all(t<-1e-7 for t in turns)

class ModularPavingTests(unittest.TestCase):
    def test_mixed_routes_keep_raised_support_and_worn_terrain_with_owned_crossing(self):
        from exploration import RouteField
        from modular_paving import routes
        cfg={'composition_version':2,'paving_style':'modular','paving_material':'stone',
            'routes':[{'id':'forest','surface':'broken','paving_style':'cellular','coverage':.9,
                       'width':2,'points':[[-5,0,0],[5,0,0]]},
                      {'id':'water','surface':'broken','raised_surface':True,'width':2,
                       'points':[[-5,5,1],[5,5,1]]}],
            'places':[],'paving_exclusions':[[[-1.2,-2],[1.2,-2],[1.2,2],[-1.2,2]]]}
        emitted=[]
        def mesh(name,vs,fs,*args,**kw):emitted.append((name,np.asarray(vs),fs))
        api={'route_field':RouteField(cfg),'cfg':{},'height':lambda x,y:-.2,
             'finish_stone':lambda ob,b:None,'rng':random.Random(19),'mesh':mesh}
        routes(api)
        forest=[(n,v,f) for n,v,f in emitted if v[:,1].mean()<2]
        water=[(n,v,f) for n,v,f in emitted if v[:,1].mean()>2]
        self.assertTrue(forest and water)
        self.assertTrue(all(n=='Embedded paving' for n,v,f in forest))
        self.assertTrue(any('continuous support' in n for n,v,f in water))
        for n,v,f in forest:
            self.assertFalse(-1.199<v[:,0].mean()<1.199,'Authored crossing owns clipped area')
            self.assertAlmostEqual(v[:,2].max(),-.178)
        for n,v,f in water:
            self.assertGreater(v[:,2].max(),1.03,'Raised decks retain their measured elevation')
        # Missing cells expose the actual terrain instead of a hidden intact sheet.
        top_area=sum(area(v[[i for i in face],:2]) for n,v,faces in forest
                     for face in faces if len(face)==3 and all(v[i,2]>-.18 for i in face))
        self.assertLess(top_area,15.2*.98)
        self.assertGreater(top_area,15.2*.5)

    def test_unsupported_raised_cellular_route_is_rejected(self):
        from exploration import RouteField
        from modular_paving import routes
        cfg={'paving_material':'stone','routes':[{'id':'bad','surface':'broken','width':2,
             'paving_style':'cellular','raised_surface':True,'points':[[0,0,1],[5,0,1]]}], 'places':[]}
        with self.assertRaisesRegex(ValueError,'terrain-supported'):
            routes({'route_field':RouteField(cfg),'cfg':{},'height':lambda x,y:0})

    def test_authored_deck_excludes_both_detailed_and_structural_route_overlays(self):
        from exploration import RouteField
        from modular_paving import routes
        from landscape_routes import whitebox
        cfg={'composition_version':2,'paving_style':'modular','paving_material':'stone','routes':[{'id':'crossing','surface':'stone','width':2,'points':[[-5,0,0],[5,0,0]]}],
             'places':[],'paving_exclusions':[[[-2,-2],[2,-2],[2,2],[-2,2]]]}
        api={'route_field':RouteField(cfg),'cfg':{},'height':lambda x,y:0,'finish_stone':lambda ob,b:None,'rng':random.Random(2)}
        for builder in ['detail','structural']:
            emitted=[]
            def mesh(name,vs,fs,*args,**kw):emitted.append(np.asarray(vs))
            api['mesh']=mesh
            if builder=='detail':routes(api)
            else:whitebox(api,{'mesh':mesh,'wedge':lambda *args:None})
            self.assertTrue(emitted)
            for vs in emitted:
                self.assertFalse(-1.999<vs[:,0].mean()<1.999,'An independent deck must own the full crossing')

    def test_difference_has_exact_area_for_both_windings(self):
        subject=[[0,0],[10,0],[10,10],[0,10]];excluded=[[2,2],[8,2],[8,8],[2,8]]
        for a in [subject,subject[::-1]]:
            for b in [excluded,excluded[::-1]]:
                pieces=difference(a,b)
                self.assertAlmostEqual(sum(map(area,pieces)),64)
                self.assertTrue(all(area(p)>1e-10 for p in pieces))
        self.assertEqual(difference(subject,subject),[])
        self.assertAlmostEqual(sum(map(area,difference(subject,[[10,0],[12,0],[12,10],[10,10]]))),100)

    def test_crossing_routes_have_one_surface_owner_and_no_gaps(self):
        shapes=[[[0,0],[6,0],[6,6],[0,6]], [[-2,2],[9,2],[9,4],[-2,4]], [[2,-2],[4,-2],[4,9],[2,9]]]
        occupied=[];pieces=[]
        for shape in shapes:
            pieces.extend(uncovered(shape,occupied));occupied.append(shape)
        self.assertAlmostEqual(sum(map(area,pieces)),56)
        for x in np.arange(-1.87,9,.31):
            for y in np.arange(-1.79,9,.29):
                expected=any(contains(s,(x,y)) for s in shapes)
                self.assertEqual(sum(contains(p,(x,y)) for p in pieces),int(expected))

    def test_clipped_cells_cover_actual_convex_footprints_without_holes(self):
        for shape in [[[-8,0],[8,0],[8,16],[-8,16]],[[-1,-1],[3,2],[2,4],[-2,1]]]:
            expected=abs(sum(np.cross(shape[i],shape[(i+1)%len(shape)]) for i in range(len(shape))))/2
            polygons=list(cells(shape,(1.2,.6),0))
            area=sum(abs(sum(np.cross(p[i],p[(i+1)%len(p)]) for i in range(len(p))))/2 for p in polygons)
            self.assertAlmostEqual(area,expected,places=6)
            reverse=list(cells(shape[::-1],(1.2,.6),0))
            self.assertEqual(len(polygons),len(reverse))

    def test_sloped_stone_has_planar_crown_and_continuous_shallow_bedding(self):
        emitted=[]
        def mesh(name,vs,fs,mat,**kwargs):emitted.append((name,np.array(vs),fs));return None
        api={'height':lambda x,y:.13*x+.07*y,'mesh':mesh,'finish_stone':lambda ob,b:None,'rng':random.Random(2)}
        patch(api,[[-1,-1],[2,-1],[2,2],[-1,2]],'stone')
        for name,vs,fs in emitted:
            surface=vs if 'support' in name else vs[len(vs)//2:]
            offset=.037 if 'support' in name else .045
            self.assertLess(np.max(np.abs(surface[:,2]-(surface[:,0]*.13+surface[:,1]*.07+offset))),1e-8)
        self.assertTrue(any('support' in n for n,_,_ in emitted))

    def test_joint_removal_is_bounded_instead_of_missing_random_slabs(self):
        outline=[[0,0],[12,0],[12,6],[0,6]]
        area=sum(abs(sum(np.cross(p[i],p[(i+1)%len(p)]) for i in range(len(p))))/2 for p in cells(outline))
        self.assertGreater(area/72,.97)
        self.assertLess(area,72)

    def test_single_sided_bedding_retains_upward_winding(self):
        for outline in [[[-1,-1],[2,-1],[3,2],[-2,2]],[[-2,2],[3,2],[2,-1],[-1,-1]]]:
            emitted=[]
            def mesh(name,vs,fs,mat,**kwargs):
                if 'support' in name:emitted.append((np.asarray(vs),fs,kwargs))
            api={'height':lambda x,y:.08*x-.11*y,'mesh':mesh,'finish_stone':lambda ob,b:None,'rng':random.Random(2)}
            patch(api,outline,'stone')
            self.assertTrue(emitted)
            for vs,fs,kw in emitted:
                self.assertTrue(kw.get('preserve_winding'))
                # Newell area normal avoids collinear leading clipped corners.
                normal=sum((np.cross(a,b) for a,b in zip(vs,np.roll(vs,-1,axis=0))),np.zeros(3))
                self.assertGreater(normal[2],0)

if __name__=='__main__':unittest.main()
