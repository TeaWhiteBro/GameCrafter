import copy,tempfile,unittest
from pathlib import Path
from game_pipeline.core import write_json,digest,StageError
from game_pipeline.review_evidence import geometry_evidence,diagnostic_views,compact_audit,normal_runtime_views
from unittest.mock import patch
from game_pipeline.rendering import launch_args

class EvidenceTests(unittest.TestCase):
    def normal_fixture(self,root):
        blend=root/'scene.blend';blend.write_bytes(b'geometry')
        report=root/'report.json';write_json(report,{'blend':str(blend)})
        image=root/'view.png';image.write_bytes(b'native image')
        audit=root/'audit.json'
        data={'source_report_sha256':digest(report),'source_blend_sha256':digest(blend),
            'normal_runtime_contract':'camera_only_clone_v1','source_snapshot':{'version':'actual source'},
            'group_proofs':[{'group':'arrival','normal_rendering':True,'rendering_args':launch_args(),
                'geometry':{'passed':True,'actor_render_signature_before':'a'*64,'actor_render_signature_after':'a'*64,
                            'changed_properties':['player.exploration_places','player.camera_yaw']},
                'camera':{'current_runtime_views':True,'view_centres_verified':True,'ground_camera_clearance_verified':True,'view_count':1}}],
            'images':[{'path':str(image),'sha256':digest(image),'evidence_type':'ue_normal_runtime','group':'arrival','caption':'Current approach'}]}
        write_json(audit,data)
        return report,audit,data

    def test_normal_runtime_requires_complete_native_proof(self):
        with tempfile.TemporaryDirectory() as temp, patch('game_pipeline.preflight_cache.snapshot',return_value={'version':'actual source'}):
            report,audit,data=self.normal_fixture(Path(temp))
            self.assertEqual(len(normal_runtime_views([audit],report,'project','editor')),1)
            self.assertEqual(diagnostic_views([audit],report),[])
            data.pop('source_snapshot');write_json(audit,data)
            with self.assertRaisesRegex(StageError,'complete project'):normal_runtime_views([audit],report,'project','editor')

    def test_changed_light_or_hidden_foliage_is_not_normal_art_evidence(self):
        with tempfile.TemporaryDirectory() as temp, patch('game_pipeline.preflight_cache.snapshot',return_value={'version':'actual source'}):
            report,audit,data=self.normal_fixture(Path(temp))
            for mutation in ['light','hidden','args','camera']:
                changed=copy.deepcopy(data);proof=changed['group_proofs'][0]
                if mutation=='light':proof['geometry']['actor_render_signature_after']='b'*64
                if mutation=='hidden':proof['geometry']['changed_properties'].append('foliage.hidden')
                if mutation=='args':proof['rendering_args'].append('-NoLighting')
                if mutation=='camera':proof['camera']['view_centres_verified']=False
                write_json(audit,changed)
                with self.assertRaisesRegex(StageError,'observation changed'):normal_runtime_views([audit],report,'project','editor')

    def test_normal_runtime_preserves_all_native_views_and_image_bytes(self):
        with tempfile.TemporaryDirectory() as temp, patch('game_pipeline.preflight_cache.snapshot',return_value={'version':'actual source'}):
            report,audit,data=self.normal_fixture(Path(temp))
            data['group_proofs'][0]['camera']['view_count']=2;write_json(audit,data)
            with self.assertRaisesRegex(StageError,'coverage'):normal_runtime_views([audit],report,'project','editor')
            data['group_proofs'][0]['camera']['view_count']=1;write_json(audit,data)
            Path(data['images'][0]['path']).write_bytes(b'edited')
            with self.assertRaisesRegex(StageError,'image changed'):normal_runtime_views([audit],report,'project','editor')

    def test_late_failed_measurement_cannot_disappear_in_summary(self):
        samples=[{'passed':True,'error_m':.001,'id':i} for i in range(144)]
        samples[-1].update(passed=False,error_m=.9)
        result=compact_audit({'samples':samples})['samples']
        self.assertEqual(result['status_counts'],{'passed':143,'failed':1,'unlabelled':0})
        self.assertEqual(result['selected_rows'][0]['source_index'],143)
        self.assertEqual(result['omitted_failed_rows'],0)

    def test_more_failures_than_context_budget_remain_explicit(self):
        result=compact_audit([{'passed':False,'error_m':i} for i in range(20)])
        self.assertEqual(result['selected_rows'][0]['source_index'],19)
        self.assertEqual(result['status_counts']['failed'],20)
        self.assertEqual(result['omitted_failed_rows'],12)

    def test_unlabelled_measurements_are_not_inferred_to_pass(self):
        result=compact_audit([{'z':i} for i in range(12)])
        self.assertEqual(result['status_counts'],{'passed':0,'failed':0,'unlabelled':12})

    def test_image_coverage_and_original_audit_are_preserved(self):
        audit={'images':[{'path':str(i)} for i in range(12)],
               'samples':[{'passed':True,'max_error_m':i*.01} for i in range(50)]}
        before=copy.deepcopy(audit);result=compact_audit(audit)
        self.assertEqual(audit,before)
        self.assertEqual(result['images'],audit['images'])
        self.assertEqual(result['samples']['selected_rows'][0]['source_index'],49)

    def test_stale_geometry_diagnostic_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);blend=root/'scene.blend';blend.write_bytes(b'geometry-v1')
            report=root/'report.json';write_json(report,{'blend':str(blend)})
            audit=root/'audit.json';write_json(audit,{'source_report_sha256':digest(report),'source_blend_sha256':digest(blend),'components':[]})
            self.assertEqual(geometry_evidence([audit],report)[0]['audit']['components'],0)
            blend.write_bytes(b'geometry-v2')
            with self.assertRaisesRegex(StageError,'outdated'):geometry_evidence([audit],report)

    def test_diagnostic_images_need_current_source_and_unchanged_pixels(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);blend=root/'scene.blend';blend.write_bytes(b'geometry-v1')
            report=root/'report.json';write_json(report,{'blend':str(blend)})
            image=root/'side.png';image.write_bytes(b'fixture-image')
            audit=root/'audit.json'
            record={'source_report_sha256':digest(report),'source_blend_sha256':digest(blend),
                    'images':[{'path':str(image),'sha256':digest(image),'evidence_type':'blender_geometry_diagnostic','caption':'Side view; vegetation hidden.'}]}
            write_json(audit,record)
            self.assertEqual(diagnostic_views([audit],report)[0]['path'],str(image))
            image.write_bytes(b'changed-pixels')
            with self.assertRaisesRegex(StageError,'changed or is missing'):diagnostic_views([audit],report)
            record['images'][0]['sha256']=digest(image);write_json(audit,record)
            blend.write_bytes(b'different-geometry')
            with self.assertRaisesRegex(StageError,'outdated'):diagnostic_views([audit],report)

    def test_diagnostic_cannot_be_mislabelled_as_normal_runtime_art(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);blend=root/'scene.blend';blend.write_bytes(b'geometry')
            report=root/'report.json';write_json(report,{'blend':str(blend)})
            image=root/'side.png';image.write_bytes(b'image');audit=root/'audit.json'
            record={'source_report_sha256':digest(report),'source_blend_sha256':digest(blend),
                    'images':[{'path':str(image),'sha256':digest(image),'evidence_type':'approved_runtime','caption':'A side view'}]}
            write_json(audit,record)
            with self.assertRaisesRegex(StageError,'renderer/scope'):diagnostic_views([audit],report)
