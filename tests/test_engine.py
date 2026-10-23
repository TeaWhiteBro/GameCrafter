import copy, json, tempfile, unittest, sys
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_pipeline.core import Engine,Node,RunLock,StageError,PendingExternal,write_json,read_json
from game_pipeline.cli import repair
from game_pipeline.local_adapters import clone_project

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.calls=[]
        def adapter(ctx,cfg):
            self.calls.append(ctx.node.name);p=ctx.directory/'asset.txt'
            text=Path(cfg['source']).read_text() if 'source' in cfg else cfg.get('value','output')
            p.write_text(text);return {'asset':str(p),'_files':[p]}
        self.registry={'work':adapter};self.machine={'budgets':{'mesh_calls':1}}
    def engine(self):
        engine=Engine(self.root,self.machine,self.registry);self.addCleanup(engine.db.close);return engine
    def test_role_replacement_invalidates_only_its_consumers(self):
        a=self.root/'player.txt';b=self.root/'boss.txt';a.write_text('A');b.write_text('B')
        nodes=[Node('player','work',{'source':str(a),'_source_files':[str(a)]}),Node('boss','work',{'source':str(b),'_source_files':[str(b)]}),Node('integration','work',{},['player','boss'])]
        e=self.engine();e.execute(nodes);self.calls.clear();e.execute(nodes);self.assertEqual(self.calls,[])
        a.write_text('NEW PLAYER');e.execute(nodes);self.assertEqual(self.calls,['player','integration'])
    def test_corrupt_artifact_is_rebuilt(self):
        e=self.engine();nodes=[Node('mesh','work',{})];r=e.execute(nodes)
        Path(r['mesh']['asset']).write_text('tampered');e.execute(nodes);self.assertEqual(self.calls,['mesh','mesh'])
    def test_code_change_rebuilds_consumers_without_repeating_asset_provider(self):
        code=self.root/'adapter.py';code.write_text('version=1')
        nodes=[Node('paid_mesh','work',{}),Node('runtime','work',{'_implementation_files':[str(code)]},['paid_mesh']),Node('qa','work',{},['runtime'])]
        e=self.engine();old=e.execute(nodes);self.calls.clear();e.execute(nodes,replay=True);self.assertEqual(self.calls,[])
        code.write_text('version=2');e.execute(nodes)
        self.assertEqual(self.calls,['runtime','qa'])
        self.assertEqual(Path(old['runtime']['asset']).read_text(),'output')
    def test_uncertain_paid_submission_does_not_silently_retry(self):
        def paid(ctx,cfg):
            marker=ctx.directory/'remote.json'
            if marker.exists():raise PendingExternal('Recover task ID')
            ctx.spend('mesh_calls');write_json(marker,{'status':'submitted'});raise PendingExternal('Interrupted response')
        self.registry['paid']=paid;e=self.engine();n=[Node('paid','paid',{},attempts=3)]
        for _ in range(2):
            with self.assertRaises(PendingExternal):e.execute(n)
        count=e.db.execute('select count(*) from events where event="reserve_mesh_calls"').fetchone()[0]
        self.assertEqual(count,1)
    def test_resume_skips_completed_predecessors(self):
        def failing(ctx,cfg):raise StageError('Tool failed')
        self.registry['fail']=failing;e=self.engine()
        with self.assertRaises(StageError):e.execute([Node('one','work',{}),Node('two','fail',{},['one'])])
        self.calls.clear();e.execute([Node('one','work',{}),Node('two','work',{},['one'])]);self.assertEqual(self.calls,['two'])
    def test_replay_never_calls_generation(self):
        e=self.engine();nodes=[Node('one','work',{})];e.execute(nodes);self.calls.clear();e.execute(nodes,replay=True);self.assertEqual(self.calls,[])
        with self.assertRaises(StageError):e.execute([Node('one','work',{'value':'changed'})],replay=True)
    def test_output_paths_cannot_reuse_previous_remote_intent(self):
        e=self.engine();a=e.execute([Node('one','work',{'value':'A'})])['one']['asset'];b=e.execute([Node('one','work',{'value':'B'})])['one']['asset']
        self.assertNotEqual(a,b);self.assertEqual(Path(a).read_text(),'A')
    def test_two_processes_cannot_own_run(self):
        with RunLock(self.root/'lock'):
            with self.assertRaises(StageError):
                with RunLock(self.root/'lock'):pass
    def test_repair_agent_cannot_inject_commands_or_unbounded_values(self):
        spec={'lighting':{'exposure_bias':0}}
        candidate={'suggested_repairs':[{'field':'shell','value':'delete files'},{'field':'lighting.exposure_bias','value':1000},{'field':'lighting.exposure_bias','value':.5}]}
        fixed,applied=repair(spec,candidate);self.assertEqual(fixed['lighting_overrides'],{'exposure_bias':.5});self.assertEqual(len(applied),1);self.assertEqual(spec,{'lighting':{'exposure_bias':0}})
    def test_unreal_downstream_save_cannot_mutate_animation_artifact(self):
        source=self.root/'source';(source/'Content/Generated').mkdir(parents=True)
        (source/'GameDemo.uproject').write_text('{}');asset=source/'Content/Generated/animation.uasset';asset.write_bytes(b'animation-v1')
        ctx=SimpleNamespace(machine={'build_root':str(self.root/'build')},root=self.root/'run',directory=self.root/'stage'/'abc')
        project=Path(clone_project(ctx,str(source/'GameDemo.uproject'),'assembled',True))
        (project.parent/'Content/Generated/animation.uasset').write_bytes(b'UE reserialized package')
        self.assertEqual(asset.read_bytes(),b'animation-v1')

if __name__=='__main__':unittest.main(verbosity=2)
