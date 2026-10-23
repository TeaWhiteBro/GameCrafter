"""Read-only repair guidance and conservative implementation impact previews."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
from .core import ROOT,StageError,read_json
from .implementation import SCOPE


def descendants(nodes,seeds):
    by_name={n['name']:n for n in nodes}
    if set(seeds)-set(by_name):raise StageError('Unknown stage: '+', '.join(sorted(set(seeds)-set(by_name))))
    affected=set(seeds)
    while True:
        added={n['name'] for n in nodes if set(n['dependencies'])&affected}-affected
        if not added:return affected
        affected.update(added)


def impact(nodes,changed_files):
    changed=[Path(p.replace('\\','/')) for p in changed_files]
    changed=[(p if p.is_absolute() else ROOT/p).resolve() for p in changed]
    direct={};matched=set()
    for node in nodes:
        sources=SCOPE.get(node['adapter'],[])+node.get('implementation_files',[])
        for entry in sources:
            source=Path(entry.split('.py:')[0]+'.py' if '.py:' in entry else entry)
            source=(source if source.is_absolute() else ROOT/source).resolve()
            for path in changed:
                if path==source or source in path.parents:
                    direct.setdefault(node['name'],set()).add(entry);matched.add(path)
    affected=descendants(nodes,direct)
    return {'read_only':True,'direct':{k:sorted(v) for k,v in direct.items()},
            'downstream':[n['name'] for n in nodes if n['name'] in affected and n['name'] not in direct],
            'unaffected':[n['name'] for n in nodes if n['name'] not in affected],
            'untracked_files':[str(p) for p in changed if p not in matched],
            'scope':'Conservative file-level implementation impact, not an execution/skip plan. Spec, source-file and tool-version changes are fingerprinted separately. Paid submission intent stays protected. Untracked changes require owner/dependency audit.'}


def diagnose(run_dir):
    from .timing import audit
    root=Path(run_dir).resolve();db_path=root/'run.sqlite'
    with closing(sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True)) as db:
        rows=[{'stage':n,'status':s,'updated':t} for n,s,t in db.execute('select name,status,updated from nodes order by updated desc')]
        failures=[]
        for row in rows:
            if row['status'] not in ('failed','waiting_external','running'):continue
            event=db.execute('select detail from events where node=? and event in ("failed","waiting_external") order by id desc limit 1',(row['stage'],)).fetchone()
            failures.append({**row,'last_failure':json.loads(event[0]) if event else None})
    timing=audit(root)
    repairs=[]
    for failure in failures:
        files=sorted((root/'stages'/failure['stage']).glob('*/repair_worklist.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        if files:repairs.append({'stage':failure['stage'],'path':str(files[0]),'worklist':read_json(files[0]),
            'evidence_status':'Latest saved worklist for this stage; verify its source revision before applying.'})
    convergence=[]
    for failure in failures:
        files=sorted((root/'stages'/failure['stage']).glob('*/repair_plan_required.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        if files:convergence.append({'stage':failure['stage'],'template':str(files[0]),'action':'Complete a new source-bound repair plan; set spec.repair_plan and resume. The template is not an accepted repair.'})
    hotspots=sorted(({'stage':k,**v} for k,v in timing['stages'].items()),key=lambda x:x['closed_seconds'],reverse=True)[:5]
    return {'read_only':True,'failures':failures,'repair_worklists':repairs,'convergence_contracts':convergence,'timing_hotspots':hotspots,
            'recorded_elapsed_minutes':timing['elapsed_seconds']/60,
            'unattributed_minutes':timing['unattributed_seconds']/60,
            'next_action':'Recover saved external task/response; do not resubmit an uncertain paid request.' if any(f['status']=='waiting_external' for f in failures) else
                'Read current failure and source-matched evidence; preview implementation impact before batching repairs.' if failures else
                'No active failed stage recorded; preserve accepted artifacts and run remaining required gates.',
            'timing_notes':timing['notes']}
