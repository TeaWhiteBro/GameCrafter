from __future__ import annotations
import contextlib, hashlib, json, os, sqlite3, subprocess, sys, time, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT=Path(__file__).resolve().parents[1]
class StageError(RuntimeError): pass
class PendingExternal(StageError): pass

def now(): return datetime.now(timezone.utc).isoformat()
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def fingerprint(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.part');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)
def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def log(message): print(time.strftime('[%H:%M:%S] ')+message,flush=True)

def implementation_inventory(root=ROOT):
    """Fingerprint framework code without installed packages or generated projects."""
    root=Path(root);sources={}
    for directory,folders,files in os.walk(root):
        folders[:]=[name for name in folders if name not in
                    ['runs','builds','inputs','reports','.venv','venv','node_modules','.git','__pycache__']]
        for name in files:
            path=Path(directory)/name
            if path.suffix.lower() in ['.py','.cpp','.h','.cs']:
                sources[str(path.relative_to(root))]=digest(path)
    return sources

@dataclass
class Node:
    name: str
    adapter: str
    config: dict
    deps: list[str]=field(default_factory=list)
    attempts: int=1

class RunLock:
    """OS file lock: released on crash; no stale-PID heuristics or double runners."""
    def __init__(self,path): self.path=path
    def __enter__(self):
        self.f=open(self.path,'a+b');self.f.seek(0);self.f.write(b'0');self.f.flush();self.f.seek(0)
        try:
            if os.name=='nt':
                import msvcrt;msvcrt.locking(self.f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl;fcntl.flock(self.f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.f.close();raise StageError('Another process owns this run.') from None
        return self
    def __exit__(self,*exc):
        self.f.seek(0)
        if os.name=='nt':
            import msvcrt;msvcrt.locking(self.f.fileno(),msvcrt.LK_UNLCK,1)
        self.f.close()

class Context:
    def __init__(self,root,machine,db,node,inputs,signature='manual'):
        self.root,self.machine,self.db,self.node,self.inputs=root,machine,db,node,inputs
        self.directory=root/'stages'/node.name/signature[:16];self.directory.mkdir(parents=True,exist_ok=True)
    def event(self,event,detail):
        self.db.execute('insert into events(ts,node,event,detail) values(?,?,?,?)',(now(),self.node.name,event,json.dumps(detail)));self.db.commit()
    def spend(self,kind):
        limit=self.machine.get('budgets',{}).get(kind,0)
        count=self.db.execute('select count(*) from events where event=?',('reserve_'+kind,)).fetchone()[0]
        if count>=limit: raise StageError(f'{kind} call budget reached ({limit}); raise the configured limit deliberately to continue.')
        self.event('reserve_'+kind,{'ordinal':count+1,'limit':limit})
    def run(self,args,timeout=900,env=None,cwd=None,log_name='process.log'):
        args=[str(x) for x in args];path=self.directory/log_name
        merged=os.environ.copy();merged['PYTHONIOENCODING']='utf-8';merged.update(env or {})
        startup=None
        if os.name=='nt':
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        process_id=uuid.uuid4().hex
        self.event('process_start',{'process_id':process_id,'executable':Path(args[0]).name,'log':str(path.relative_to(self.root))})
        with path.open('w',encoding='utf-8') as output:
            p=subprocess.Popen(args,stdout=output,stderr=subprocess.STDOUT,env=merged,cwd=cwd,startupinfo=startup)
            started=time.monotonic();last=started
            try:
                while p.poll() is None:
                    if time.monotonic()-started>timeout: raise StageError(f'{self.node.name} exceeded {timeout}s; inspect {path}')
                    if time.monotonic()-last>25:
                        log(f'{self.node.name}: running ({int(time.monotonic()-started)}s), log: {path.name}');last=time.monotonic()
                    time.sleep(.5)
            except BaseException:
                p.terminate()
                try:p.wait(15)
                except subprocess.TimeoutExpired:p.kill();p.wait(15)
                raise
            finally:
                self.event('process_end',{'process_id':process_id,'elapsed_seconds':time.monotonic()-started,
                    'returncode':p.returncode,'log':str(path.relative_to(self.root))})
        if p.returncode: raise StageError(f'{self.node.name} process exited {p.returncode}; inspect {path}')
        return path

class Engine:
    def __init__(self,root,machine,registry):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.machine,self.registry=machine,registry
        self.db=sqlite3.connect(self.root/'run.sqlite');self.db.execute('pragma journal_mode=WAL')
        self.db.executescript('''create table if not exists nodes(name text primary key,fingerprint text,status text,result text,updated text);
        create table if not exists implementations(name text primary key,digest text);
        create table if not exists events(id integer primary key,ts text,node text,event text,detail text);''')
        self.db.commit()
    def execute(self,nodes,replay=False,until=None):
        from .implementation import implementation_digest
        results={};code_hash=fingerprint(implementation_inventory())
        execution_implementations={n.name:implementation_digest(n.adapter,n.config.get('_implementation_files',[])) for n in nodes}
        from .timing import observe_execution
        with RunLock(self.root/'.run.lock'), observe_execution(self.root,self.db,replay,until):
            for n in nodes:
                if n.adapter not in self.registry:raise StageError('Unregistered adapter '+n.adapter)
                missing=set(n.deps)-set(results)
                if missing:raise StageError(f'{n.name}: dependency order error {missing}')
                inputs={d:results[d] for d in n.deps}
                config=json.loads(json.dumps(n.config))
                # Hash explicitly declared source files. Content changes invalidate consumers.
                declared=config.pop('_source_files',[])
                missing_files=[p for p in declared if not Path(p).is_file()]
                if missing_files:raise StageError('Declared stage inputs are missing: '+str(missing_files))
                source_hashes={p:digest(p) for p in declared}
                signature=fingerprint({'adapter':n.adapter,'revision':n.config.get('_adapter_revision',1),'config':config,'sources':source_hashes,'inputs':inputs,'tools':self.machine.get('tool_versions',{})})
                row=self.db.execute('select fingerprint,status,result from nodes where name=?',(n.name,)).fetchone()
                impl=implementation_digest(n.adapter,n.config.get('_implementation_files',[]))
                if impl!=execution_implementations[n.name]:raise StageError('Adapter implementation changed during this process; resume in a fresh process before '+n.name)
                previous_impl=self.db.execute('select digest from implementations where name=?',(n.name,)).fetchone()
                impl_valid=not impl or (previous_impl and previous_impl[0]==impl)
                if row and row[0]==signature and row[1]=='complete' and impl_valid:
                    saved=json.loads(row[2])
                    if all(Path(p).is_file() and digest(p)==sha for p,sha in saved.get('_artifacts',{}).items()):
                        results[n.name]=saved;log(n.name+': cached')
                        if until==n.name:break
                        continue
                if replay:raise StageError(f'Replay requires a valid completed artifact: {n.name}')
                # Separate immutable directories for different adapter implementations.
                execution_signature=fingerprint([signature,impl]) if impl else signature
                self.db.execute('insert or replace into nodes values(?,?,?,?,?)',(n.name,signature,'running',None,now()));self.db.commit()
                ctx=Context(self.root,self.machine,self.db,n,inputs,execution_signature);ctx.event('started',{'fingerprint':signature,'adapter':n.adapter,'implementation_sha256':code_hash,'scoped_implementation_sha256':impl})
                for attempt in range(n.attempts):
                    try:
                        if attempt:ctx.event('retry_started',{'attempt':attempt+1})
                        log(n.name+': '+n.adapter)
                        result=self.registry[n.adapter](ctx,n.config)
                        if implementation_digest(n.adapter,n.config.get('_implementation_files',[]))!=impl:
                            raise StageError('Adapter implementation changed while running '+n.name+'; output is preserved but not accepted. Resume in a fresh process.')
                        files=result.pop('_files',[])
                        if not files:raise StageError('Adapter must declare its output files: '+n.adapter)
                        for p in files:
                            if not Path(p).is_file():raise StageError('Missing adapter output '+str(p))
                        result['_artifacts']={str(Path(p).resolve()):digest(p) for p in files}
                        self.db.execute('update nodes set status=?,result=?,updated=? where name=?',('complete',json.dumps(result),now(),n.name));self.db.commit()
                        self.db.execute('insert or replace into implementations values(?,?)',(n.name,impl));self.db.commit()
                        ctx.event('complete',{'artifacts':len(files)});results[n.name]=result
                        write_json(ctx.directory/'receipt.json',result);break
                    except BaseException as exc:
                        status='waiting_external' if isinstance(exc,PendingExternal) else 'failed'
                        self.db.execute('update nodes set status=?,updated=? where name=?',(status,now(),n.name));self.db.commit()
                        ctx.event(status,{'type':type(exc).__name__,'message':str(exc)[:1000]})
                        if attempt+1>=n.attempts or isinstance(exc,(KeyboardInterrupt,PendingExternal)):raise
                        log(f'{n.name}: retry {attempt+2}/{n.attempts}');time.sleep(2)
                if until==n.name:break
            write_json(self.root/'run_summary.json',{'updated':now(),'nodes':{n: {k:v for k,v in r.items() if k!='_artifacts'} for n,r in results.items()}})
        return results
