"""A native unknown pixel must never disappear through exporter repair or tolerance."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from game_pipeline.dataset import process,validate_semantic_source

class UnknownLabelTests(unittest.TestCase):
    def fixture(self,folder,label,depth):
        p=Path(folder);(p/'raw').mkdir();eye=np.eye(4).reshape(-1).tolist()
        meta={'frame_id':0,'time_seconds':1.,'camera_mode':'first','width':8,'height':8,
              'orthographic':False,'projection':eye,'world_to_view':eye,'world_to_clip':eye,'actors':[]}
        (p/'capture_result.json').write_text(json.dumps({'ok':True,'frames':1,'width':8,'height':8}),encoding='utf-8')
        (p/'raw/000000.json').write_text(json.dumps(meta),encoding='utf-8')
        np.zeros((8,8,4),np.uint8).tofile(p/'raw/000000.bgra')
        z=np.full((8,8),3.,np.float32);z[0,0]=depth;z.tofile(p/'raw/000000.depth')
        ids=np.ones((8,8),np.uint8);ids[0,0]=label;ids.tofile(p/'raw/000000.ids')
        return p

    def reject_unknown(self,depth):
        with tempfile.TemporaryDirectory() as folder:
            p=self.fixture(folder,255,depth)
            with self.assertRaisesRegex(ValueError,'no_unknown_labels'):
                process(p,videos=False)
            report=json.loads((p/'validation.json').read_text())
            self.assertFalse(report['export_complete'])
            self.assertEqual(report['class_pixel_counts']['255'],1)
            self.assertEqual(np.fromfile(p/'raw/000000.ids',np.uint8)[0],255)
            self.assertEqual(np.asarray(Image.open(p/'semantic_ids/000000.png'))[0,0],255)

    def test_single_unknown_on_geometry_is_rejected(self):
        self.reject_unknown(3.)

    def test_clear_depth_does_not_silently_relabel_native_unknown(self):
        self.reject_unknown(100000006144.)

    def test_renderer_classified_sky_preserves_zero_and_invalid_depth(self):
        with tempfile.TemporaryDirectory() as folder:
            p=self.fixture(folder,0,100000006144.)
            self.assertTrue(process(p,videos=False)['passed'])
            self.assertEqual(np.asarray(Image.open(p/'semantic_ids/000000.png'))[0,0],0)
            self.assertTrue(np.isnan(np.load(p/'depth/000000.npy')[0,0]))

    def source(self):
        return ({'semantic_encoding':'scene_depth_clear_to_sky_v1','semantic_background_min_depth_m':1e10,'background_stencil_changes':1},
                np.array([[1e11,3.,4.]],np.float32),np.array([[0,255,6]],np.uint8),np.array([[255,255,6]],np.uint8))

    def test_native_sky_encoding_preserves_finite_unknowns(self):
        meta,depth,ids,stencil=self.source();validate_semantic_source(meta,depth,ids,stencil)
        self.assertEqual(ids[0,1],255)

    def test_native_finite_unknown_cannot_be_repaired_as_sky(self):
        meta,depth,ids,stencil=self.source();ids[0,1]=0
        with self.assertRaisesRegex(ValueError,'disagree'):validate_semantic_source(meta,depth,ids,stencil)

    def test_native_labels_cannot_change_class_on_finite_surfaces(self):
        meta,depth,ids,stencil=self.source();ids[0,2]=3
        with self.assertRaisesRegex(ValueError,'disagree'):validate_semantic_source(meta,depth,ids,stencil)

    def test_missing_or_untruthful_encoding_receipt_is_rejected(self):
        meta,depth,ids,stencil=self.source();meta['background_stencil_changes']=0
        with self.assertRaisesRegex(ValueError,'disagree'):validate_semantic_source(meta,depth,ids,stencil)

if __name__=='__main__':unittest.main()
