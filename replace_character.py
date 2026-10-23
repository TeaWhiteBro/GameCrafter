"""Prepare a safe variant; then run/resume it with the standard pipeline command."""
import argparse
from pathlib import Path
from game_pipeline.core import ROOT, read_json
from game_pipeline.replacement import prepare_replacement

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-run',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--machine',type=Path,default=ROOT/'machine.local.json')
    p.add_argument('--role',choices=['player','boss'],required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--image',type=Path)
    group.add_argument('--mesh',type=Path)
    p.add_argument('--reference',type=Path,action='append',default=[])
    p.add_argument('--name');p.add_argument('--height',type=float)
    a=p.parse_args()
    prepare_replacement(a.from_run,a.run_dir,read_json(a.machine),a.role,a.image or a.mesh,
                        image=bool(a.image),name=a.name,height=a.height,references=a.reference)
    print('Prepared replacement. Continue with pipeline.py run --run-dir',a.run_dir)
