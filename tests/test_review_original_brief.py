"""Review scope must retain the original brief across both acceptance gates."""
import unittest
from game_pipeline import workflow
from game_pipeline.cli import graph
from game_pipeline.core import ROOT, read_json


class ReviewBriefTests(unittest.TestCase):
    def test_current_brief_reaches_both_reviews(self):
        spec = read_json(ROOT / 'examples/local_assets.spec.json')
        spec.update(prompt='Build a shallow tropical water temple.', full_playtest=True, review_agent=True)
        spec = workflow.configure(spec, source_policy='provided')
        nodes = {node.name: node for node in graph(spec, {})}
        for name in ['scene_preflight', 'review']:
            self.assertEqual(nodes[name].config['original_user_brief'], spec['prompt'])


if __name__ == '__main__':
    unittest.main()
