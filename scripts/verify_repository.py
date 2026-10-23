"""Offline release checks: portable source, complete exports and dependency graph."""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_release import source_files, SECRET, PRIVATE
from game_pipeline.core import read_json
from game_pipeline.cli import graph
from game_pipeline.workflow import configure


def verify():
    selected = source_files()
    for path in selected:
        if not path.is_file():
            raise ValueError('Missing exported source: ' + str(path.relative_to(ROOT)))
        text = path.read_text(encoding='utf-8-sig')
        if SECRET.search(text) or PRIVATE.search(text):
            raise ValueError('Credential or private path: ' + str(path.relative_to(ROOT)))
        private_names = ['zhiyang' + 'deng', 'tea' + 'white', 'ZHI' + 'YAN~1']
        if any(re.search(r'(?i)\b' + re.escape(name) + r'\b', text) for name in private_names):
            raise ValueError('Machine-specific identity: ' + str(path.relative_to(ROOT)))
        if path.suffix == '.py':
            ast.parse(text, filename=str(path.relative_to(ROOT)))
    benchmark = read_json(ROOT / 'examples/benchmark_prompts.json')
    assert [c['id'] for c in benchmark['cases']] == [f'{i:02d}' for i in range(1, 11)]
    for profile, expected_activities in [('world_demo', ['combat', 'exploration']), ('arena_demo', ['combat'])]:
        spec = read_json(ROOT / 'examples/local_assets.spec.json')
        spec.update(full_playtest=True, review_agent=True)
        spec['concept'] = {'provider': 'gpt_image'}
        for role in ('player', 'boss'):
            spec['characters'][role]['source'] = {'provider': 'tripo', 'mode': 'text', 'prompt': 'Complete upright humanoid with separated limbs'}
        spec = configure(spec, profile=profile)
        nodes = graph(spec, {})
        by_name = {n.name: n for n in nodes}
        assert len(by_name) == len(nodes)
        for node in nodes:
            assert set(node.deps) <= set(by_name), node.name
        completed = set()
        while len(completed) < len(nodes):
            ready = {n.name for n in nodes if n.name not in completed and set(n.deps) <= completed}
            assert ready, 'Dependency cycle'
            completed.update(ready)
        assert spec['dataset']['activities'] == expected_activities
        assert len(spec['dataset']['cameras']) == 3 and len(spec['dataset']['channels']) == 5
        assert by_name['capture_probe'].config['probe_scope'] == 'all_requested'
        assert {'review', 'playtest', 'scene_preflight', 'capture_probe', 'camera_validation', 'calibration', 'pair_validation'} <= set(by_name['delivery'].deps)
    documentation = sorted(ROOT.glob('*.md')) + sorted((ROOT / 'docs').glob('*.md'))
    for document in documentation:
        filename = document.relative_to(ROOT).as_posix()
        text = (ROOT / filename).read_text(encoding='utf-8')
        text = re.sub(r'```.*?```', '', text, flags=re.S)
        for target in re.findall(r'\]\(([^)\s]+)\)', text):
            if target.startswith(('https:', 'http:', '#', 'mailto:')):
                continue
            path = (ROOT / filename).parent / target.split('#')[0]
            if not path.exists():
                raise ValueError('Missing documentation target in ' + filename + ': ' + target)
    return {'passed': True, 'exported_source_files': len(selected), 'profiles': ['world_demo', 'arena_demo'],
            'scope': 'Offline source, documentation and stage-contract checks; no provider requests or native UE production.'}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
