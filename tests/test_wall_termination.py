import sys,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from landscape_routes import wall_segments

class WallTerminationTests(unittest.TestCase):
    def segments(self,wall,nearest):
        class Field:
            config={'walls':[wall]}
        field=Field();field.nearest=nearest
        return list(wall_segments({'route_field':field,'height':lambda x,y:0.}))

    def test_crossing_remains_open_and_tapers_without_full_height_tail(self):
        wall={'points':[[-12,0],[12,0]],'height':1.,'enclosure':True,'taper_gap_m':4.}
        segments=self.segments(wall,lambda x,y:(abs(x),0.,4.))
        self.assertTrue(all(abs(p[0])>2.8 for _,p,*_ in segments))
        inner=min(segments,key=lambda s:abs(s[1][0]))
        outer=max(segments,key=lambda s:abs(s[1][0]))
        # The segment includes a buried footing; assess the visible crown.
        self.assertLess(inner[2]+inner[3],.2);self.assertGreater(outer[2]+outer[3],.8)

    def test_explicit_polyline_end_taper_preserves_middle_crown(self):
        wall={'points':[[0,0],[10,0],[10,10]],'height':1.,'enclosure':True,'taper_end_m':4.}
        segments=self.segments(wall,lambda x,y:(100.,0.,4.))
        self.assertLess(segments[0][2]+segments[0][3],.25);self.assertLess(segments[-1][2]+segments[-1][3],.25)
        self.assertGreater(max(s[2]+s[3] for s in segments),.8)
