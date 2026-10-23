import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from geometry_batches import partition

class GeometryBatchTests(unittest.TestCase):
    def test_dense_repeated_foliage_is_bounded_without_losing_instances(self):
        items=[{'i':i,'n':131540,'xy':[(i%17)*3,(i//17)*3]} for i in range(253)]
        groups=partition(items,lambda a:a['n'],lambda a:a['xy'])
        self.assertGreater(len(groups),1)
        self.assertEqual(sorted(a['i'] for g in groups for a in g),list(range(253)))
        self.assertEqual(sum(a['n'] for g in groups for a in g),253*131540)
        self.assertTrue(all(sum(a['n'] for a in g)<=4000000 for g in groups))

    def test_small_groups_preserve_source_order(self):
        self.assertEqual(partition([3,1,2],lambda a:1000,lambda a:[a,0]),[[3,1,2]])

    def test_an_oversized_single_source_must_not_silently_bypass_budget(self):
        with self.assertRaisesRegex(ValueError,'single source'):
            partition([1],lambda a:10000000,lambda a:[0,0])

if __name__=='__main__':unittest.main()
