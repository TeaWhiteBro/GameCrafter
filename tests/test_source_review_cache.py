import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from game_pipeline.environment_assets import equivalent_review_evidence
from game_pipeline.implementation import environment_preparation_digest


class SourceReviewCacheTests(unittest.TestCase):
    def test_geology_repair_invalidates_its_recipe_only(self):
        version={'geological_recipe.py':'old'}
        assets=[{}, {'construction':{'recipe':'carved_lantern'}}, {'construction':{'recipe':'eroded_outcrop'}}]
        with patch('game_pipeline.implementation.digest',side_effect=lambda p:version.get(p.name,'stable')):
            before=[environment_preparation_digest(a) for a in assets]
            version['geological_recipe.py']='new'
            after=[environment_preparation_digest(a) for a in assets]
        self.assertEqual(before[:2],after[:2])
        self.assertNotEqual(before[2],after[2])

    def test_unused_texture_helper_does_not_invalidate_plain_asset(self):
        version={'texture_regions.py':'old'}
        with patch('game_pipeline.implementation.digest',side_effect=lambda p:version.get(p.name,'stable')):
            plain=environment_preparation_digest({})
            edited=environment_preparation_digest({'texture_regions':[{}]})
            version['texture_regions.py']='new'
            self.assertEqual(plain,environment_preparation_digest({}))
            self.assertNotEqual(edited,environment_preparation_digest({'texture_regions':[{}]}))

    def test_render_roundoff_reuses_same_model_but_visible_change_does_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'source.glb';model.write_bytes(b'same actual GLB')
            a=root/'a.png';b=root/'b.png';Image.new('RGB',(400,400),(90,100,110)).save(a)
            im=Image.open(a);im.putpixel((50,50),(91,100,110));im.save(b)
            old={'geometry':{'triangles':5},'binding':{'file':str(model)},'views':[str(a)]}
            new=copy.deepcopy(old);new['views']=[str(b)]
            self.assertTrue(equivalent_review_evidence({'id':'tree'},new,{'id':'tree'},old))
            im.putpixel((50,50),(93,100,110));im.save(b)
            self.assertFalse(equivalent_review_evidence({'id':'tree'},new,{'id':'tree'},old))
            self.assertFalse(equivalent_review_evidence({'id':'different'},old,{'id':'tree'},old))
            other=root/'changed.glb';other.write_bytes(b'changed geometry')
            new=copy.deepcopy(old);new['binding']['file']=str(other)
            self.assertFalse(equivalent_review_evidence({'id':'tree'},new,{'id':'tree'},old))
