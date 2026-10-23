"""Reuse must tolerate valid non-import providers occupying the assembly node."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from game_pipeline.core import write_json, digest
from game_pipeline.static_reuse import contract, prepare


class StaticReuseProviderTransitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.donor = self.root/'stages/ue_assemble/donor'
        self.current = self.root/'stages/ue_assemble/current'
        self.donor.mkdir(parents=True)
        self.current.mkdir(parents=True)
        self.mesh = self.root/'mesh.fbx'
        self.mesh.write_bytes(b'verified same-run source')
        self.entry = dict(file=str(self.mesh), material='stone', collision=True,
                          semantic_id=3, triangles=100)
        self.scene = self.root/'current_scene.json'
        write_json(self.scene, {'environment': [self.entry]})
        self.report = self.donor/'report.json'
        write_json(self.report, {'static_import_contract': contract()})
        self.donor_project = self.root/'donor_game/Game.uproject'
        self.receipt = dict(project=str(self.donor_project), report=str(self.report),
                            _artifacts={str(self.report): digest(self.report)})
        write_json(self.donor/'receipt.json', self.receipt)
        self.ctx = SimpleNamespace(root=self.root, directory=self.current)
        self.target_project = self.root/'current_game/Game.uproject'

    def test_camera_receipt_without_import_job_is_not_a_donor(self):
        write_json(self.donor/'camera_job.json', {'camera_yaw': -15})
        entries, _ = prepare(self.ctx, self.target_project, self.scene)
        self.assertEqual(entries, {})
        self.assertFalse((self.target_project.parent/'Content').exists())

    def test_job_without_scene_contract_is_not_a_donor(self):
        write_json(self.donor/'job.json', {'mode': 'camera'})
        entries, _ = prepare(self.ctx, self.target_project, self.scene)
        self.assertEqual(entries, {})

    def test_verified_static_import_is_still_reused(self):
        write_json(self.donor/'job.json', {'scene': str(self.scene)})
        sr = self.root/'stages/scene/verified'
        sr.mkdir(parents=True)
        write_json(sr/'receipt.json', dict(report=str(self.scene), _artifacts={
            str(self.scene): digest(self.scene), str(self.mesh): digest(self.mesh)}))
        package = self.donor_project.parent/'Content/Generated/Environment/SM_Group_0.uasset'
        package.parent.mkdir(parents=True)
        package.write_bytes(b'verified native package')
        self.receipt['_artifacts'][str(package)] = digest(package)
        write_json(self.donor/'receipt.json', self.receipt)
        entries, signature = prepare(self.ctx, self.target_project, self.scene)
        self.assertEqual(set(entries), {'0'})
        self.assertEqual(signature, contract())
        copied = self.target_project.parent/'Content/Generated/Environment/SM_Group_0.uasset'
        self.assertEqual(copied.read_bytes(), package.read_bytes())
