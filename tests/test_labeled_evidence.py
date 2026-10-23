import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from game_pipeline.core import StageError,digest
from game_pipeline.labeled_evidence import prepare

class EvidenceIdentityTests(unittest.TestCase):
    def test_current_and_reference_remain_bound_to_original_files(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);a=p/'now.png';b=p/'old.png'
            Image.new('RGB',(80,60),'red').save(a);Image.new('RGB',(80,60),'blue').save(b)
            hashes=[digest(a),digest(b)]
            output=prepare(p,[a,b],['CURRENT third-person ravine','ACCEPTED PARENT ONLY; NOT current'])
            records=json.loads((p/'labeled_evidence/manifest.json').read_text())['images']
            self.assertEqual([r['role'] for r in records],['CURRENT','REFERENCE'])
            self.assertEqual([r['index'] for r in records],[1,2])
            self.assertEqual([r['source_sha256'] for r in records],hashes)
            self.assertEqual([digest(a),digest(b)],hashes)
            for i,path in enumerate(output):
                with Image.open(path) as image:
                    self.assertEqual(image.height,184)
                    centre=image.getpixel((image.width//2,150))
                    self.assertGreater(centre[i*2],240)
    def test_mismatched_image_and_label_counts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StageError):prepare(directory,['unused.png'],[])

if __name__=='__main__':unittest.main()
