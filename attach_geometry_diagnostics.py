"""Attach verified supplemental geometry views to early and final review.

Run after scene construction stops. This never marks a review as approved.
"""
import argparse, datetime, json, sqlite3
from pathlib import Path
from game_pipeline.core import RunLock, StageError, read_json, write_json
from game_pipeline.review_evidence import geometry_evidence, diagnostic_views


def attach(root, paths):
    root=root.resolve();paths=[str(p.resolve()) for p in paths]
    with RunLock(root/'.run.lock'):
        with sqlite3.connect(f'file:{(root/"run.sqlite").as_posix()}?mode=ro',uri=True) as db:
            row=db.execute('select status,result from nodes where name="scene"').fetchone()
        if not row or row[0]!='complete':raise StageError('Complete the current scene before attaching diagnostics')
        report=json.loads(row[1])['report']
        geometry_evidence(paths,report);views=diagnostic_views(paths,report)
        spec_path=root/'game_spec.json';spec=read_json(spec_path)
        revision=root/'revisions'/('geometry_evidence_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        revision.mkdir(parents=True);(revision/'before_game_spec.json').write_bytes(spec_path.read_bytes())
        for name,adapter in [('scene_preflight','ue.scene_preflight'),('review','agent.review')]:
            override=spec.setdefault('adapters',{}).setdefault(name,{'adapter':adapter,'config':{}})
            if override['adapter']!=adapter:raise StageError('Custom review adapter requires its own diagnostic contract')
            cfg=override.setdefault('config',{})
            cfg['geometry_audits']=list(dict.fromkeys(cfg.get('geometry_audits',[])+paths))
            # Preserve default reference dependencies as well as user overrides.
            cfg['_source_files']=list(dict.fromkeys(spec.get('quality_benchmarks',[])+cfg.get('_source_files',[])+paths+[v['path'] for v in views]))
        write_json(spec_path,spec);(revision/'game_spec.json').write_bytes(spec_path.read_bytes())
        write_json(revision/'attachment.json',{'scene_report':report,'audits':paths,'images':views,
            'scope':'Additional verified evidence only; early and final visual gates still required.'})
        return revision


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    parser.add_argument('--audit',required=True,type=Path,action='append')
    args=parser.parse_args();print(attach(args.run_dir,args.audit))
