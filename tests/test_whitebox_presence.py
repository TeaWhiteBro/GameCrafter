import copy,unittest
import numpy as np
from game_pipeline.whitebox_presence import presence


class WhiteboxPresenceTests(unittest.TestCase):
    def sample(self):
        w,h=800,600;m=np.diag([.001,.001,.001,1.])
        capsules=[];image=np.full((h,w,3),235,np.uint8)
        for x in [-50.,50.]:
            a=[x,0.,0.];b=[x,30.,0.]
            capsules.append({'role':'player','a_cm':a,'b_cm':b,'radius_cm':4.})
            # Independent fixture: two narrow upright shaded proxy silhouettes.
            px=int(w*(.5+x*.0005)-.5)
            image[291:300,px-1:px+2]=205
        meta={'width':w,'height':h,'world_to_clip':m.reshape(-1).tolist(),
              'actors':[{'role':'player','camera_hidden':False}],
              'whitebox':{'capsules':capsules}}
        return meta,image

    def test_small_resolved_proxies_on_uniform_ground(self):
        meta,image=self.sample();self.assertLess(image.std(),2.)
        report=presence(meta,image);self.assertTrue(report['passed'])
        self.assertEqual(report['method'],'capsule_local_contrast')

    def test_uniform_gray_has_no_proxy_evidence(self):
        meta,image=self.sample();self.assertFalse(presence(meta,np.full_like(image,235))['passed'])

    def test_signal_at_unrelated_image_locations_is_rejected(self):
        meta,image=self.sample();self.assertFalse(presence(meta,np.roll(image,120,axis=1))['passed'])

    def test_single_pixel_noise_is_rejected(self):
        meta,image=self.sample();image[:]=235;image[298,379]=100
        self.assertFalse(presence(meta,image)['passed'])

    def test_hidden_actor_cannot_supply_raster_presence(self):
        meta,image=self.sample();meta['actors'][0]['camera_hidden']=True
        self.assertFalse(presence(meta,image)['passed'])

    def test_missing_extent_does_not_guess_projection(self):
        meta,image=self.sample();del meta['width']
        self.assertFalse(presence(meta,image)['passed'])

    def test_duplicate_probes_do_not_multiply_single_signal(self):
        meta,image=self.sample();image[:,400:]=235
        meta['whitebox']['capsules']=[copy.deepcopy(meta['whitebox']['capsules'][0]) for _ in range(11)]
        self.assertFalse(presence(meta,image)['passed'])
