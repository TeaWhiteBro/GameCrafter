import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from game_pipeline.preflight_cache import commit,restore,load_valid,snapshot
from game_pipeline.core import read_json,write_json


class PreflightCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.old=self.root/'first/runtime_capture';self.old.mkdir(parents=True)
        (self.old/'view.png').write_bytes(b'original runtime image')
        (self.old/'route.json').write_text('{"passed":true}')
        self.source={'runtime':'one','render':'one','camera':'all-three'}
        self.payload={'views':['view.png'],'labels':['CURRENT third-person'],'evidence':{'route':{'passed':True}}}
        commit(self.old,self.source,self.payload)
    def test_rejected_art_observations_can_be_reused_but_no_approval(self):
        write_json(self.old.parent/'review.json',{'approved':False})
        out=self.root/'second/runtime_capture'
        result=restore(self.root,out,self.source)
        self.assertEqual(result,self.payload)
        self.assertNotIn('approved',read_json(out/'capture_commit.json'))
        self.assertEqual((out/'view.png').read_bytes(),b'original runtime image')
    def test_any_source_change_forces_new_capture(self):
        for field in self.source:
            with self.subTest(field=field):
                self.assertIsNone(restore(self.root,self.root/'new'/field,{**self.source,field:'changed'}))
    def test_corrupt_and_missing_evidence_are_not_reused(self):
        (self.old/'view.png').write_bytes(b'altered')
        self.assertIsNone(load_valid(self.old,self.source))
        (self.old/'view.png').unlink()
        self.assertIsNone(load_valid(self.old,self.source))
    def test_uncommitted_legacy_capture_is_not_adopted(self):
        (self.old/'capture_commit.json').unlink()
        self.assertIsNone(restore(self.root,self.root/'new/runtime_capture',self.source))
    def test_manifest_traversal_is_rejected(self):
        manifest=read_json(self.old/'capture_commit.json')
        manifest['files']['../../outside.txt']='irrelevant'
        write_json(self.old/'capture_commit.json',manifest)
        self.assertIsNone(load_valid(self.old,self.source))
    def test_unlisted_view_is_rejected(self):
        manifest=read_json(self.old/'capture_commit.json');manifest['payload']['views']=['missing.png']
        write_json(self.old/'capture_commit.json',manifest)
        self.assertIsNone(load_valid(self.old,self.source))
    def test_source_inventory_detects_added_deleted_and_changed_content(self):
        base=self.root/'project'
        for name in ['GameDemo.uproject','Binaries/Win64/UnrealEditor-GameDemo.dll','Config/DefaultEngine.ini','Content/Generated/Maps/Demo.umap']:
            p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture')
        scene=self.root/'scene.json';scene.write_text('{}');editor=self.root/'UnrealEditor.exe';editor.write_bytes(b'fixture')
        args=[base/'GameDemo.uproject',scene,editor]
        initial=snapshot(*args)
        new=base/'Content/material.uasset';new.write_bytes(b'new')
        self.assertNotEqual(snapshot(*args),initial)
        second=snapshot(*args);new.write_bytes(b'changed')
        self.assertNotEqual(snapshot(*args),second)
        new.unlink();self.assertEqual(snapshot(*args),initial)

