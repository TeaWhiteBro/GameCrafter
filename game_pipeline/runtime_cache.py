"""Publish complete compiled runtime binaries under a cross-process lock."""
import contextlib,os,shutil,time
from pathlib import Path
from .core import StageError,digest,read_json,write_json,log

@contextlib.contextmanager
def locked(path,timeout=1800):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as f:
        if path.stat().st_size==0:f.write(b'0');f.flush()
        started=time.monotonic();last=started
        while True:
            try:
                f.seek(0)
                if os.name=='nt':
                    import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()-started>timeout:raise StageError('Timed out waiting for compiled-runtime cache')
                if time.monotonic()-last>25:log('Waiting for the shared runtime build to finish');last=time.monotonic()
                time.sleep(.25)
        try:yield
        finally:
            f.seek(0)
            if os.name=='nt':
                import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl;fcntl.flock(f,fcntl.LOCK_UN)

def materialize(runtime,destination,build):
    runtime=Path(runtime);destination=Path(destination);runtime.mkdir(parents=True,exist_ok=True)
    with locked(runtime/'.publish.lock'):
        marker=runtime/'binary_commit.json';valid=False
        if marker.exists():
            data=read_json(marker);files=data.get('files',{})
            valid=bool(files) and all((runtime/p).is_file() and digest(runtime/p)==sha for p,sha in files.items())
        if not valid:
            # A DLL can appear before the linker releases its PDB. Only the
            # successful build return plus a committed file set certifies reuse.
            build()
            dll=runtime/'Binaries/Win64/UnrealEditor-GameDemo.dll'
            if not dll.is_file():raise StageError('Runtime build returned without its expected module')
            files={str(p.relative_to(runtime)):digest(p) for p in (runtime/'Binaries').rglob('*') if p.is_file()}
            write_json(marker,{'schema_version':1,'files':files})
        shutil.copytree(runtime/'Binaries',destination/'Binaries',dirs_exist_ok=True)
