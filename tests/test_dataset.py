import unittest
import numpy as np
from game_pipeline.dataset import project,calibration_check,annotate

class DatasetTests(unittest.TestCase):
    def sample(self):
        ids=np.zeros((32,48),np.uint8);ids[8:24,10:38]=200
        depth=np.ones((32,48),np.float32)*10;depth[ids==200]=3
        rgb=np.zeros((32,48,3),np.uint8);rgb[ids==200]=(180,0,0)
        meta={'calibration':[{'class_id':200,'front_depth_m':3,'front_corners_px':[[9.5,7.5],[37.5,7.5],[9.5,23.5],[37.5,23.5]]}]}
        return meta,rgb,depth,ids
    def test_known_orthographic_pixel_center(self):
        actual=project([[0,0,0],[1,1,0]],np.eye(4),640,360)
        np.testing.assert_allclose(actual,[[319.5,179.5],[639.5,-.5]])
    def test_eye_plane_is_undefined_without_divide_warning(self):
        m=np.eye(4);m[3,3]=0;m[2,3]=1
        with np.errstate(divide='raise',invalid='raise'):
            actual=project([[0,0,0],[1,1,2]],m,640,360)
        self.assertTrue(np.isnan(actual[0]).all())
        self.assertTrue(np.isfinite(actual[1]).all())
    def test_undefined_joint_cannot_be_declared_in_front(self):
        m=np.eye(4);m[3,3]=0;m[2,3]=1
        meta={'world_to_clip':m.reshape(-1).tolist(),'actors':[{'class_id':10,'camera_hidden':False,
            'bones':[{'world_cm':[0,0,0],'in_front':True,'pixel_xy':[0,0],'parent':-1}]}]}
        with self.assertRaisesRegex(ValueError,'undefined projection'):
            annotate(meta,np.ones((10,10)),np.zeros((10,10)))
    def test_calibration_accepts_registered_metric_planes(self):
        self.assertTrue(calibration_check(*self.sample())['passed'])
    def test_shifted_semantics_rejected(self):
        m,r,d,i=self.sample();self.assertFalse(calibration_check(m,r,d,np.roll(i,3,axis=1))['passed'])
    def test_wrong_depth_scale_rejected(self):
        m,r,d,i=self.sample();self.assertFalse(calibration_check(m,r,d*100,i)['passed'])
    def test_wrong_depth_bias_rejected(self):
        m,r,d,i=self.sample();self.assertFalse(calibration_check(m,r,d+.02,i)['passed'])
    def test_rgb_from_different_frame_rejected(self):
        m,r,d,i=self.sample();self.assertFalse(calibration_check(m,np.roll(r,5,axis=1),d,i)['passed'])
    def test_missing_calibration_pixels_rejected(self):
        m,r,d,i=self.sample();self.assertFalse(calibration_check(m,r,d,np.zeros_like(i))['passed'])
    def test_nearer_surface_must_occlude_farther(self):
        m,r,d,i=self.sample();m['calibration'].append({'class_id':201,'front_depth_m':2,'front_corners_px':[[20,10],[31,10],[20,21],[31,21]]})
        self.assertFalse(calibration_check(m,r,d,i)['passed'])

if __name__=='__main__':unittest.main()
