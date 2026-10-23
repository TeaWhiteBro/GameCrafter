"""Optional DAG stage for calibrated RGB/depth/semantics/skeleton datasets."""
from pathlib import Path
import shutil
from .core import ROOT,read_json,write_json,digest,StageError

def reuse_raw(ctx,key,out,project,camera,calibration,frames,width,height,whitebox):
    """Reuse only committed, checksum-verified native frames of this exact project.

    Exporter revisions do not need another UE simulation. Never reuse pending
    files, captures of an older module/map/material, or mismatched settings.
    """
    for stage in sorted(ctx.directory.parent.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True):
        receipt=stage/'receipt.json';candidate=stage/key
        if stage==ctx.directory or not receipt.is_file() or not (candidate/'validation.json').is_file():continue
        validation=read_json(candidate/'validation.json')
        if not validation.get('passed') or not validation.get('export_complete'):continue
        result=read_json(candidate/'capture_result.json');source=read_json(candidate/'source.json')
        if source.get('project')!=str(Path(project).resolve()) or source.get('camera')!=camera:continue
        if (result.get('frames'),result.get('width'),result.get('height'),result.get('calibration_only'))!=(frames,width,height,calibration):continue
        if whitebox and not result.get('whitebox'):continue
        base=Path(project).parent
        if any(not (base/p).is_file() or digest(base/p)!=sha for p,sha in source['files'].items()):continue
        files=[candidate/'source.json',candidate/'capture_result.json']+list((candidate/'raw').glob('*'))
        artifacts=read_json(receipt).get('_artifacts',{})
        if any(artifacts.get(str(p.resolve()))!=digest(p) for p in files):continue
        if len(list((candidate/'raw').glob('*.json')))!=frames:continue
        out.mkdir(parents=True)
        for path in files:
            dest=out/path.relative_to(candidate);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        write_json(out/'raw_reuse.json',{'source':str(candidate),'receipt_sha256':digest(receipt),'policy':'same project content and capture settings; all copied native frame checksums verified'})
        return True
    return False

def dataset(ctx,cfg):
    project=ctx.inputs['ue_assemble']['project'];collections={}
    if not isinstance(cfg.get('whitebox',False),bool):raise StageError('dataset.whitebox must be a boolean')
    modes=cfg.get('cameras',['first','third','isometric'])
    if not modes or not set(modes)<=set(['first','third','isometric']):raise StageError('Unsupported dataset camera')
    frames=int(cfg.get('frames',360));width=int(cfg.get('width',640));height=int(cfg.get('height',360))
    if frames<2 or not (64<=width<=4096 and 64<=height<=4096) or width%2 or height%2:raise StageError('Invalid capture dimensions or frame count')
    for calibration in [True,False]:
        for camera in modes:
            key=('calibration_' if calibration else '')+camera;out=ctx.directory/key
            if (out/'validation.json').exists() and read_json(out/'validation.json').get('passed') and read_json(out/'validation.json').get('export_complete'):
                source=read_json(out/'source.json');base=Path(project).parent
                if any(digest(base/p)!=sha for p,sha in source['files'].items()):raise StageError('Completed capture belongs to an earlier project revision')
            else:
                if out.exists():
                    # Preserve incomplete evidence and choose a fresh attempt directory.
                    i=1
                    while out.with_name(key+'_attempt_'+str(i)).exists():i+=1
                    out=out.with_name(key+'_attempt_'+str(i))
                args=[ctx.machine['python'],ROOT/'capture_dataset.py','--project',project,'--out',out,'--camera',camera,'--width',str(width),'--height',str(height),'--frames',str(4 if calibration else frames)]
                if calibration:args+=['--calibration','--no-videos']
                elif cfg.get('autoplay',True):args+=['--autoplay']
                if cfg.get('whitebox',False):args+=['--whitebox']
                if reuse_raw(ctx,key,out,project,camera,calibration,4 if calibration else frames,width,height,cfg.get('whitebox',False)):
                    args+=['--process-only']
                ctx.run(args,timeout=max(900,frames*12),log_name=key+'.log')
            report=read_json(out/'validation.json')
            if not report['passed']:raise StageError('Dataset gate failed: '+key)
            if cfg.get('whitebox') and not read_json(out/'dataset.json').get('whitebox'):raise StageError('Requested whitebox channel missing')
            collections[key]={'directory':str(out),'validation':report}
    record=ctx.directory/'collections.json';write_json(record,{'passed':True,'cameras':modes,'sequences':collections,'project':project})
    files=[p for p in ctx.directory.rglob('*') if p.is_file() and p.name not in ['engine.log','process.log']]
    return {'passed':True,'collections':str(record),'_files':files}
