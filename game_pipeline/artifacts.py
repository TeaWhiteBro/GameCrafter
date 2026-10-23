"""Explicit immutable inheritance across different graph entry points."""
from pathlib import Path
from .core import StageError,digest,write_json

def inherit(ctx,cfg):
    files=cfg['artifacts']
    if not files or any(not Path(p).is_file() or digest(p)!=sha for p,sha in files.items()):
        raise StageError('Inherited accepted artifact changed; regenerate only through an explicit new revision')
    if cfg.get('rig'):
        from .contracts import validate_rig
        from .core import read_json
        validate_rig(read_json(cfg['result']['report']))
    path=ctx.directory/'inheritance.json'
    write_json(path,{'parent_run':cfg['parent_run'],'artifacts':files,'scope':'Accepted unchanged inputs; downstream projects remain independent.'})
    return {**cfg['result'],'_files':list(files)+[path]}
