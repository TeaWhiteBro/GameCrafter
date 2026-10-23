"""Require an evidence-bound diagnosis before a fourth distinct refused review.

This checks the repair process, not the correctness of an artistic judgment.
The executing agent supplies the diagnosis; normal visual gates still decide.
"""
from pathlib import Path
from .core import StageError, digest, fingerprint, read_json, write_json


def refusal_streak(directory):
    paths=sorted(directory.parent.glob('*/review_state.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    seen=set();result=[]
    for path in paths:
        state=read_json(path);key=state.get('request_key')
        if state.get('status')!='complete' or key in seen:continue
        if state.get('review_sha256')!=fingerprint(state.get('review')):
            raise StageError('Refusal history receipt changed: '+str(path))
        seen.add(key);review=state['review']
        if review.get('approved') is True and review.get('exploration_variety_approved') is not False:break
        result.append({'path':str(path),'sha256':digest(path),'review':review})
    return result


def verified_files(items, label):
    if not isinstance(items,list) or not items:raise StageError('Repair plan needs '+label)
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get('path'),str):raise StageError('Invalid repair evidence file')
        path=Path(item['path'])
        if not path.is_file() or item.get('sha256')!=digest(path):raise StageError('Repair evidence is absent or stale: '+str(path))
    return [item['path'] for item in items]


def require_plan(directory, source, plan_path=None):
    history=refusal_streak(directory)
    if len(history)<3:return {'required':False,'distinct_refusals':len(history)}
    latest=history[0]
    required=[i for i in latest['review'].get('issues',[]) if i.get('severity') in ('blocker','diagnostic')]
    template={'schema_version':1,'against_review_sha256':latest['sha256'],
        'target_source_sha256':fingerprint(source),'previous_review':latest['path'],
        'actions':[{'issue_id':i['id'],'kind':'diagnostic' if i['severity']=='diagnostic' else 'repair',
                    'owner_stage':'','root_cause':'','changes':[],'evidence':[],
                    'expected_result':'','observed_result':''} for i in required],
        'instructions':'Fill a new file, then set spec.repair_plan to its absolute path. Preserve old receipts. File entries need path and sha256. Diagnostic actions need evidence; repair actions also need changed files. This does not waive visual acceptance.'}
    write_json(directory/'repair_plan_required.json',template)
    if not plan_path:raise StageError('Three distinct environmental refusals require a source-bound repair plan before further capture/review; see repair_plan_required.json')
    plan=read_json(plan_path)
    if plan.get('schema_version')!=1 or any(plan.get(k)!=template[k] for k in ('against_review_sha256','target_source_sha256')):
        raise StageError('Repair plan refers to a stale refusal or source revision')
    actions=plan.get('actions')
    if not required or not isinstance(actions,list) or len(actions)!=len(required):raise StageError('Repair plan must cover every current required issue')
    by_id={i.get('issue_id'):i for i in actions if isinstance(i,dict)}
    if len(by_id)!=len(actions) or set(by_id)!={i['id'] for i in required}:raise StageError('Repair issue coverage is incomplete or duplicated')
    files=[str(plan_path)]
    for issue in required:
        action=by_id[issue['id']]
        expected='diagnostic' if issue['severity']=='diagnostic' else 'repair'
        if action.get('kind')!=expected:raise StageError('Separate diagnostic uncertainty from confirmed reconstruction')
        for key in ('owner_stage','root_cause','expected_result','observed_result'):
            if not isinstance(action.get(key),str) or not action[key].strip():raise StageError('Repair plan lacks '+key)
        files.extend(verified_files(action.get('evidence'),'targeted verification evidence'))
        if expected=='repair':files.extend(verified_files(action.get('changes'),'changed files'))
    return {'required':True,'distinct_refusals':len(history),'plan':str(plan_path),'sha256':digest(plan_path),
            'evidence_files':list(dict.fromkeys(files)),
            'scope':'Process evidence verified; all normal visual and downstream gates remain required.'}
