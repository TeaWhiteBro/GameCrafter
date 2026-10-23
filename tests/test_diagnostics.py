import tempfile
import unittest
import io
import sqlite3
from contextlib import redirect_stdout,closing
from pathlib import Path
from unittest.mock import patch
from game_pipeline.core import StageError,ROOT,read_json,write_json,digest
from game_pipeline.diagnostics import descendants,impact
from game_pipeline.implementation import SCOPE,implementation_digest
from game_pipeline.cli import graph,main
from game_pipeline import workflow
from game_pipeline.review_cycle import worklist


class DiagnosticsTests(unittest.TestCase):
    def test_diagnose_cli_needs_no_machine_and_preserves_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);database=root/'run.sqlite'
            with closing(sqlite3.connect(database)) as db:
                db.executescript('create table nodes(name text,status text,updated text); create table events(id integer primary key,ts text,node text,event text,detail text);')
                db.execute('insert into nodes values(?,?,?)',('scene','failed','2026-01-01T00:01:00+00:00'))
                db.executemany('insert into events values(?,?,?,?,?)',[(1,'2026-01-01T00:00:00+00:00','scene','started','{}'),(2,'2026-01-01T00:01:00+00:00','scene','failed','{"message":"Missing floor"}')])
                db.commit()
            before=digest(database)
            with patch('sys.argv',['pipeline.py','diagnose','--run-dir',str(root)]),patch('game_pipeline.machine.load') as machine,redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(),0);machine.assert_not_called()
            self.assertIn('Missing floor',stdout.getvalue());self.assertEqual(digest(database),before)

    def test_published_graph_matches_current_source(self):
        base=read_json(ROOT/'examples/local_assets.spec.json');base.update(full_playtest=True,review_agent=True,concept={'provider':'gpt_image'})
        for role in ['player','boss']:base['characters'][role]['source']={'provider':'tripo','mode':'text','prompt':'Complete humanoid'}
        actual=[(n.name,n.adapter,n.deps) for n in graph(workflow.configure(base),{})]
        saved=read_json(ROOT/'docs/workflow_graph.json')
        expected=[(n['name'],n['adapter'],n['dependencies']) for n in saved['nodes'] if n['name']!='design']
        self.assertEqual(actual,expected)

    def test_transitive_closure_ignores_input_order(self):
        nodes=[{'name':'release','dependencies':['qa']},{'name':'qa','dependencies':['scene']},{'name':'scene','dependencies':[]},{'name':'paid','dependencies':[]}]
        self.assertEqual(descendants(nodes,{'scene'}),{'scene','qa','release'})
        with self.assertRaises(StageError):descendants(nodes,{'typo'})

    def test_surface_fix_preserves_paid_sources_but_requires_downstream_gates(self):
        base=read_json(ROOT/'examples/local_assets.spec.json');base.update(full_playtest=True,review_agent=True)
        nodes=[{'name':n.name,'adapter':n.adapter,'dependencies':n.deps} for n in graph(workflow.configure(base,source_policy='provided'),{})]
        result=impact(nodes,['adapters/unreal/surfaces.py'])
        self.assertEqual(set(result['direct']),{'ue_assemble'})
        self.assertTrue({'capture_probe','playtest','pair_validation','delivery'}<=set(result['downstream']))
        self.assertTrue({'mesh_player','mesh_boss','environment_assets'}<=set(result['unaffected']))
        self.assertEqual(impact(nodes,['unregistered_helper.py'])['untracked_files'],[str((ROOT/'unregistered_helper.py').resolve())])

    def test_missing_scoped_symbol_fails_instead_of_silent_cache_hit(self):
        with patch.dict(SCOPE,{'fixture':['game_pipeline/workflow.py:does_not_exist']}):
            with self.assertRaisesRegex(ValueError,'Missing declared implementation'):implementation_digest('fixture')

    def test_all_declared_implementation_scopes_resolve(self):
        for adapter in SCOPE:
            with self.subTest(adapter=adapter):self.assertTrue(implementation_digest(adapter))

    def test_ambiguous_first_review_requests_evidence_before_rebuild(self):
        issue={'id':'floor','severity':'diagnostic','category':'geometry','current_images':[1],
               'problem':'Dark patch may be a shadow','repair':'Inspect that location','verification':'Oblique and ground-level views'}
        result=worklist({'approved':False,'issues':[issue]},['CURRENT runtime'],0)
        self.assertEqual(result['next_action'],'collect_targeted_diagnostics_before_reconstruction')
        self.assertEqual(result['repair_routes'][0]['action'],'targeted_diagnostic')
        self.assertEqual(result['diagnostic'],[issue])
