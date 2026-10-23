import unittest,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_pipeline.pixel_trace import unproject,candidates

class PixelTraceTests(unittest.TestCase):
    def perspective(self):
        return {'width':640,'height':360,'world_to_clip':[[1,0,0,0],[0,1,0,0],[0,0,1,1],[0,0,0,-200]],'world_to_camera_cv_m':[[1,0,0,0],[0,-1,0,0],[0,0,1,-2],[0,0,0,1]]}
    def test_perspective_depth_returns_metric_world_point(self):
        np.testing.assert_allclose(unproject(self.perspective(),[639.5,269.5],2),[2,-1,4],atol=1e-9)
    def test_orthographic_uses_parallel_rays(self):
        m=self.perspective();m['world_to_clip']=[[.001,0,0,0],[0,1/600,0,0],[0,0,0,0],[0,0,0,1]]
        np.testing.assert_allclose(unproject(m,[383.5,209.5],2),[2,-1,4],atol=1e-9)
    def test_invalid_depth_and_wrong_semantic_candidate_rejected(self):
        for pixel,z in [([640,0],1),([0,0],float('nan')),([0,0],0)]:
            with self.assertRaises(ValueError):unproject(self.perspective(),pixel,z)
        audit={'components':[{'environment':11,'component':1,'semantic_id':4,'bounds_m':{'min':[0,0,0],'max':[2,2,2]}},{'environment':14,'component':2,'material':'rooted_scan','semantic_id':5,'bounds_m':{'min':[0,0,0],'max':[2,2,2]}}]}
        self.assertEqual([r['environment'] for r in candidates([1,1,1],5,audit)],[14])
