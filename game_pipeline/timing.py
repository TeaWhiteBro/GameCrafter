"""Read-only run accounting. Unknown gaps are never called model/idle time."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import json
import sqlite3
from contextlib import contextmanager,closing
from datetime import timezone
import time
import uuid


@contextmanager
def observe_execution(root, db, replay=False, until=None):
    """Telemetry only; neither a time limit nor permission to skip a gate."""
    session = uuid.uuid4().hex
    def emit(kind, detail):
        db.execute('insert into events(ts,node,event,detail) values(?,?,?,?)',
                   (datetime.now(timezone.utc).isoformat(),'__engine__',kind,json.dumps({'session':session,**detail})))
        db.commit()
    emit('execution_start',{'replay':replay,'until':until})
    started = time.monotonic()
    status = 'failed'
    try:
        yield
        status = 'complete'
    finally:
        emit('execution_end',{'status':status,'elapsed_seconds':time.monotonic()-started})
        # Failure to write supplemental telemetry must not hide the real stage failure.
        try:
            db.row_factory = sqlite3.Row
            report = analyze(db.execute('select * from events order by id'))
            report['run'] = str(Path(root).resolve())
            target = Path(root)/'timing.json'
            temporary = target.with_suffix('.json.part')
            temporary.write_text(json.dumps(report,indent=2),encoding='utf-8')
            temporary.replace(target)
        except (OSError,ValueError,sqlite3.Error) as error:
            print('Supplemental timing report unavailable: '+type(error).__name__,flush=True)
        finally:
            db.row_factory = None


def union_seconds(intervals):
    total = 0.0
    right = None
    for start, end in sorted(intervals):
        if end < start:
            raise ValueError('Clock moved backwards; duration cannot be inferred')
        total += max(0.0, end - max(start, right if right is not None else start))
        right = max(end, right if right is not None else end)
    return total


def analyze(rows):
    attempts, pending, calls = [], {}, []
    events = []
    for row in rows:
        data = dict(row)
        data['time'] = datetime.fromisoformat(data['ts']).timestamp()
        data['detail'] = json.loads(data['detail']) if isinstance(data['detail'], str) else data['detail']
        events.append(data)
    # Engine stages are serial; child source/preparation events belong to the
    # current parent window. Explicit execution boundaries improve new logs.
    current = None
    for event in events:
        node, kind, at = event['node'], event['event'], event['time']
        if kind in ('started', 'retry_started'):
            if current:
                current.update(status='censored',upper_end=at)
                attempts.append(current)
            current = {'node': node, 'start': at, 'last_observed': at}
        elif kind in ('execution_start','execution_end') and current:
            current.update(status='censored',upper_end=at)
            attempts.append(current)
            current = None
        if current:
            current['last_observed'] = at
        if kind in ('complete','failed','waiting_external') and current and current['node'] == node:
            current.update(end=at,status=kind)
            attempts.append(current)
            current = None
        if kind == 'reserve_llm_calls':
            pending[node] = at
        if kind == 'llm_result' and node in pending:
            calls.append({'node':node,'start':pending.pop(node),'end':at})
    if current:
        current.update(status='censored',upper_end=None)
        attempts.append(current)
    stages = defaultdict(lambda: {'attempts':0,'complete':0,'failed':0,'waiting_external':0,'censored':0,'closed_seconds':0.0})
    intervals = []
    for item in attempts:
        stage = stages[item['node']]
        stage['attempts'] += 1
        stage[item['status']] += 1
        if 'end' in item:
            duration = item['end'] - item['start']
            if duration < 0: raise ValueError('Clock moved backwards')
            item['seconds'] = duration
            stage['closed_seconds'] += duration
            intervals.append((item['start'],item['end']))
    llm = defaultdict(lambda: {'calls':0,'window_seconds':0.0})
    for item in calls:
        llm[item['node']]['calls'] += 1
        llm[item['node']]['window_seconds'] += item['end'] - item['start']
    elapsed = max((e['time'] for e in events),default=0) - min((e['time'] for e in events),default=0)
    occupied = union_seconds(intervals)
    closed_sum = sum(s['closed_seconds'] for s in stages.values())
    return {'schema_version':1,'event_count':len(events),
            'start':events[0]['ts'] if events else None,'end':events[-1]['ts'] if events else None,
            'elapsed_seconds':elapsed,'closed_stage_union_seconds':occupied,
            'closed_stage_sum_seconds':closed_sum,'overlap_seconds':closed_sum-occupied,
            'unattributed_seconds':elapsed-occupied,'stages':dict(stages),'attempts':attempts,
            'llm_windows':dict(llm),'llm_union_seconds':union_seconds((x['start'],x['end']) for x in calls),
            'unpaired_llm_reservations':len(pending),
            'notes':['Only matched stage start/end windows enter stage totals.',
                     'LLM reservation-to-result windows include preparation/transport and are nested within stage times; do not add them again.',
                     'Unattributed time includes agent editing, diagnostics, external work and censored processes, not established idle time.',
                     'Historical stage starts count attempts, not distinct design revisions. Cached stages do not count as executed attempts.']}


def audit(run_dir):
    db_path = Path(run_dir).resolve()/'run.sqlite'
    with closing(sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory = sqlite3.Row
        result = analyze(db.execute('select * from events order by id'))
    result['run'] = str(Path(run_dir).resolve())
    return result


def markdown(report):
    lines = ['# Production timing audit','',f"Run: `{Path(report['run']).name}`",'',
             f"Recorded elapsed: {report['elapsed_seconds']/60:.2f} min; closed stages: {report['closed_stage_union_seconds']/60:.2f} min; unattributed/censored: {report['unattributed_seconds']/60:.2f} min.",'',
             '| Stage | Attempts | Complete | Failed | Censored | Closed minutes |',
             '|---|---:|---:|---:|---:|---:|']
    for name, data in report['stages'].items():
        lines.append(f"| {name} | {data['attempts']} | {data['complete']} | {data['failed']} | {data['censored']} | {data['closed_seconds']/60:.2f} |")
    lines += ['',f"LLM call windows (already included above): {report['llm_union_seconds']/60:.2f} min.",'']
    lines += ['- '+note for note in report['notes']]
    return '\n'.join(lines)+'\n'
