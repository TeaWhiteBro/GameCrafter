import json,tempfile,unittest,sys
from pathlib import Path
from game_pipeline.timing import analyze,union_seconds,audit
from game_pipeline.core import Engine,Node


def event(sec,node,kind):
    return {'ts':f'2026-09-18T00:00:{sec:02d}+00:00','node':node,'event':kind,'detail':'{}'}


class TimingTests(unittest.TestCase):
    def test_nested_llm_is_not_added_twice(self):
        r=analyze([event(0,'a','started'),event(2,'a','reserve_llm_calls'),event(6,'a','llm_result'),event(10,'a','complete'),
                   event(20,'b','started'),event(30,'b','failed')])
        self.assertEqual(r['closed_stage_union_seconds'],20)
        self.assertEqual(r['unattributed_seconds'],10)
        self.assertEqual(r['llm_union_seconds'],4)
    def test_killed_stage_is_censored_not_attributed_to_next_start(self):
        r=analyze([event(0,'a','started'),event(2,'child','remote_task'),event(25,'b','started'),event(30,'b','complete')])
        self.assertEqual(r['stages']['a']['censored'],1)
        self.assertEqual(r['stages']['a']['closed_seconds'],0)
        self.assertEqual(r['unattributed_seconds'],25)
    def test_union_does_not_double_count_overlap(self):
        self.assertEqual(union_seconds([(0,10),(5,20),(30,40)]),30)
    def test_retry_and_execution_boundaries(self):
        r=analyze([event(0,'__engine__','execution_start'),event(1,'a','started'),event(3,'a','failed'),
                   event(5,'a','retry_started'),event(8,'a','complete'),event(9,'__engine__','execution_end')])
        self.assertEqual(r['stages']['a']['attempts'],2)
        self.assertEqual(r['stages']['a']['closed_seconds'],5)
    def test_real_subprocess_telemetry_and_readonly_audit(self):
        with tempfile.TemporaryDirectory() as t:
            def adapter(ctx,cfg):
                p=ctx.run([sys.executable,'-c','print(42)'])
                return {'ok':True,'_files':[p]}
            e=Engine(t,{}, {'fixture':adapter})
            try:
                e.execute([Node('one','fixture',{})])
                events=e.db.execute('select event,detail from events').fetchall()
                starts=[json.loads(d) for k,d in events if k=='process_start']
                ends=[json.loads(d) for k,d in events if k=='process_end']
                self.assertEqual(ends[0]['process_id'],starts[0]['process_id'])
                self.assertEqual(ends[0]['returncode'],0)
                self.assertGreater(ends[0]['elapsed_seconds'],0)
                self.assertEqual(audit(t)['stages']['one']['complete'],1)
                self.assertTrue((Path(t)/'timing.json').is_file())
            finally:e.db.close()

