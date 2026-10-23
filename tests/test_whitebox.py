import unittest,copy
import numpy as np
from game_pipeline.dataset import whitebox_check,calibration_check

class WhiteboxTests(unittest.TestCase):
    def sample(self):
        bones=[{'name':str(i),'world_cm':[i*10.,0.,100.]} for i in range(12)]
        capsules=[{'role':'boss','from_bone':str(i),'to_bone':str(i+1),'a_cm':bones[i]['world_cm'][:],'b_cm':bones[i+1]['world_cm'][:],'radius_cm':3.,'head_extension':False} for i in range(11)]
        m={'simulation_step':9,'world_to_clip':np.eye(4).reshape(-1).tolist(),'actors':[{'role':'boss','bones':bones}]}
        m['whitebox']={'simulation_step':9,'world_to_clip':m['world_to_clip'][:],'capsules':capsules}
        image=np.full((24,32,3),180,np.uint8);image[:8]=130
        return m,image
    def test_valid_articulated_pair(self):self.assertTrue(whitebox_check(*self.sample())['passed'])
    def test_camera_offset_is_rejected(self):
        m,w=self.sample();m['whitebox']['world_to_clip'][12]=.3;self.assertFalse(whitebox_check(m,w)['passed'])
    def test_different_simulation_step_is_rejected(self):
        m,w=self.sample();m['whitebox']['simulation_step']=8;self.assertFalse(whitebox_check(m,w)['passed'])
    def test_stale_capsule_pose_is_rejected(self):
        m,w=self.sample();m['whitebox']['capsules'][3]['a_cm'][0]+=5;self.assertFalse(whitebox_check(m,w)['passed'])
    def test_empty_capture_is_rejected(self):
        m,w=self.sample();self.assertFalse(whitebox_check(m,w*0)['passed'])
    def test_uniform_clear_target_is_rejected(self):
        m,w=self.sample();self.assertFalse(whitebox_check(m,w*0+255)['passed'])
    def test_missing_role_is_rejected(self):
        m,w=self.sample();m['actors'].append({'role':'player','bones':[]});self.assertFalse(whitebox_check(m,w)['passed'])
    def test_missing_limb_is_rejected(self):
        m,w=self.sample();m['whitebox']['capsules'].pop();self.assertFalse(whitebox_check(m,w)['passed'])
    def test_head_extension_is_anchored(self):
        m,w=self.sample();c=m['whitebox']['capsules'][-1];c.update(head_extension=True,a_cm=[110.,0,100],b_cm=[111.5,0,100])
        self.assertTrue(whitebox_check(m,w)['passed'])

if __name__=='__main__':unittest.main()
