import tempfile
import unittest
from pathlib import Path
from game_pipeline.bounded_import import batches, valid_checkpoint
from game_pipeline.core import StageError, digest, write_json


class BoundedImportTests(unittest.TestCase):
    def test_process_budget_retains_each_mesh_once(self):
        entries=[{'triangles':n} for n in [4_000_000,3_950_000,3_900_000,3_900_000,100_000]]
        groups=batches(entries)
        self.assertEqual([i for group in groups for i in group],list(range(len(entries))))
        self.assertTrue(all(sum(entries[i]['triangles'] for i in group)<=8_000_000 for group in groups))
        self.assertEqual(groups,[[0,1],[2,3,4]])
        with self.assertRaises(StageError):batches([{'triangles':8_000_001}])

    def test_checkpoint_needs_exact_policy_report_and_saved_package(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);project=root/'Demo.uproject'
            package=root/'Content/Generated/Environment/SM_Group_2.uasset'
            package.parent.mkdir(parents=True);package.write_bytes(b'complete mesh')
            report=root/'report.json';write_json(report,{'ok':True,'imported_indices':[2]})
            receipt=root/'batch_receipt.json'
            write_json(receipt,{'signature':'current-source-and-policy','report':str(report),
                'report_sha256':digest(report),'entries':{'2':{'package_sha256':digest(package)}}})
            self.assertEqual(set(valid_checkpoint(receipt,'current-source-and-policy',project)),{'2'})
            self.assertIsNone(valid_checkpoint(receipt,'changed-source-or-policy',project))
            package.write_bytes(b'partial or changed mesh')
            self.assertIsNone(valid_checkpoint(receipt,'current-source-and-policy',project))
            package.write_bytes(b'complete mesh');write_json(report,{'ok':False})
            self.assertIsNone(valid_checkpoint(receipt,'current-source-and-policy',project))

    def test_missing_checkpoint_cannot_authorize_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(valid_checkpoint(Path(td)/'missing.json','key',Path(td)/'Demo.uproject'))
