"""Build large scene meshes in bounded UE processes with verified checkpoints.

Checkpoints accelerate import only. They never replace a scene receipt, current
UE review, gameplay test or dataset gate.
"""
import copy
from pathlib import Path
from .core import StageError, digest, fingerprint, read_json, write_json, log
from .implementation import implementation_digest


def batches(entries, maximum=8_000_000):
    if not isinstance(maximum, int) or not 1_000_000 <= maximum <= 16_000_000:
        raise StageError('UE import batch budget must be 1–16 million triangles')
    groups=[];current=[];count=0
    for i, entry in enumerate(entries):
        triangles=entry.get('triangles',0)
        if not isinstance(triangles,int) or triangles<0 or triangles>maximum:
            raise StageError(f'Environment entry {i} exceeds the UE import batch budget')
        if current and count+triangles>maximum:
            groups.append(current);current=[];count=0
        current.append(i);count+=triangles
    if current:groups.append(current)
    return groups


def valid_checkpoint(receipt_path, signature, project):
    if not receipt_path.is_file():return None
    receipt=read_json(receipt_path)
    if receipt.get('signature')!=signature:return None
    report=Path(receipt['report'])
    if not report.is_file() or digest(report)!=receipt.get('report_sha256'):return None
    if not read_json(report).get('ok'):return None
    result={}
    for index, entry in receipt.get('entries',{}).items():
        package=Path(project).parent/f'Content/Generated/Environment/SM_Group_{index}.uasset'
        if not package.is_file() or digest(package)!=entry['package_sha256']:return None
        result[index]={**entry,'package':str(package),'batch_receipt':str(receipt_path)}
    return result


def build(ctx,project,job,run_unreal):
    scene=read_json(job['scene']);entries=scene['environment']
    groups=batches(entries,ctx.machine.get('ue_import_batch_triangles',8_000_000))
    source_hashes={str(i):digest(e['file']) for i,e in enumerate(entries)}
    policy=implementation_digest('ue.assemble')
    imported={};receipts=[]
    for ordinal,indices in enumerate(groups):
        key=fingerprint({'implementation':policy,'contract':job['static_import_contract'],
            'entries':[{**entries[i],'source_sha256':source_hashes[str(i)]} for i in indices],
            'indices':indices})
        directory=ctx.directory/'import_batches'/f'{ordinal:03d}_{key[:16]}'
        receipt_path=directory/'batch_receipt.json'
        cached=valid_checkpoint(receipt_path,key,project)
        if cached is not None and set(cached)==set(map(str,indices)):
            log(f'UE import batch {ordinal+1}/{len(groups)}: verified checkpoint')
            imported.update(cached);receipts.extend([str(receipt_path),read_json(receipt_path)['report']]);continue
        directory.mkdir(parents=True,exist_ok=True)
        # Preserve failed attempts and their logs; no fabricated completion.
        attempts=list(directory.glob('attempt_*'))
        worker=copy.copy(ctx);worker.directory=directory/f'attempt_{len(attempts)+1:03d}'
        worker.directory.mkdir(parents=True,exist_ok=False)
        work={**job,'mode':'static_assets','out':str(worker.directory),'import_indices':indices}
        log(f'UE import batch {ordinal+1}/{len(groups)}: entries {indices}')
        report=run_unreal(worker,project,work)
        if read_json(report).get('imported_indices')!=indices:
            raise StageError('UE import batch returned an incomplete index list')
        assets={}
        for i in indices:
            entry=entries[i];package=Path(project).parent/f'Content/Generated/Environment/SM_Group_{i}.uasset'
            if digest(entry['file'])!=source_hashes[str(i)]:raise StageError('Source changed during static import')
            if not package.is_file():raise StageError('Completed UE import omitted its static package')
            assets[str(i)]={'source_sha256':source_hashes[str(i)],'package_sha256':digest(package),
                'package':str(package),'contract':job['static_import_contract']}
        write_json(receipt_path,{'signature':key,'report':str(report),'report_sha256':digest(report),'entries':assets})
        checked=valid_checkpoint(receipt_path,key,project)
        if checked is None:raise StageError('Just-written UE import checkpoint failed validation')
        imported.update(checked);receipts.extend([str(receipt_path),str(report)])
    write_json(ctx.directory/'bounded_import.json',{'batch_count':len(groups),
        'maximum_source_triangles':ctx.machine.get('ue_import_batch_triangles',8_000_000),
        'source_triangles':sum(e.get('triangles',0) for e in entries),'receipts':receipts})
    return imported,[str(ctx.directory/'bounded_import.json')]+receipts
