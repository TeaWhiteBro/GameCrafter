"""Refresh documentation dependencies from the current fresh-production DAG."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game_pipeline import __version__,workflow
from game_pipeline.cli import graph
from game_pipeline.core import read_json,write_json


def synchronize():
    path=ROOT/'docs/workflow_graph.json';prior=read_json(path)
    metadata={n['name']:n for n in prior['nodes']}
    metadata['capture_probe']={'title':'Early all-condition coverage','owner':'Validator',
        'detail':'All requested camera/activity jobs are captured at their full final settings and validated before long gameplay QA; exploration player occlusion is checked. Immutable verified exports may be reused later; calibration and final pair validation remain mandatory.'}
    spec=read_json(ROOT/'examples/local_assets.spec.json')
    spec.update(full_playtest=True,review_agent=True,concept={'provider':'gpt_image'})
    for role in ['player','boss']:
        spec['characters'][role]['source']={'provider':'tripo','mode':'text','prompt':'A complete new humanoid with separated limbs'}
    nodes=graph(workflow.configure(spec),{})
    records=[metadata['design']]
    for node in nodes:
        if node.name not in metadata:raise ValueError('Describe new stage before drawing: '+node.name)
        records.append({**metadata[node.name],'name':node.name,'adapter':node.adapter,'dependencies':node.deps})
    write_json(path,{**prior,'version':__version__,'nodes':records})
    print('Synchronized '+str(len(nodes))+' production stages plus design bootstrap.')


if __name__=='__main__':synchronize()
