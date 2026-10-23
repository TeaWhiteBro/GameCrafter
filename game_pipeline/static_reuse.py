"""Reuse only hash-verified static packages built from the same source contract."""
import ast,hashlib,shutil
from pathlib import Path
from .core import ROOT,read_json,write_json,digest

def contract():
    source=(ROOT/'adapters/unreal/assemble.py').read_text(encoding='utf-8')
    body=source.split('    # FRESH_STATIC_CONTRACT\n',1)[1].split('\ndef spawn',1)[0]
    return hashlib.sha256(body.encode()).hexdigest()

def eligible(entry,old,source_hash,package,package_hash,current_contract,donor_contract):
    return (current_contract==donor_contract and all(entry.get(k)==old.get(k) for k in ['material','collision','semantic_id','triangles'])
            and Path(entry['file']).is_file() and source_hash==digest(entry['file'])
            and Path(package).is_file() and package_hash==digest(package))

def prepare(ctx,project,scene):
    current=read_json(scene);result={};signature=contract();destination=Path(project).parent/'Content/Generated/Environment'
    source_receipts=[read_json(p) for p in (ctx.root/'stages/scene').glob('*/receipt.json')]
    for receipt_path in sorted((ctx.root/'stages/ue_assemble').glob('*/receipt.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        if receipt_path.parent==ctx.directory:continue
        receipt=read_json(receipt_path);report_path=Path(receipt['report'])
        if not report_path.is_file() or receipt['_artifacts'].get(str(report_path))!=digest(report_path):continue
        # Other valid providers (for example a camera-only map revision) can
        # occupy this node. They do not attest the original static import job.
        job_path=receipt_path.parent/'job.json'
        if not job_path.is_file():continue
        old_job=read_json(job_path);old_scene_path=old_job.get('scene')
        if not isinstance(old_scene_path,str):continue
        donor=read_json(report_path)
        attestation=receipt_path.parent/'static_reuse_attestation.json'
        donor_signature=donor.get('static_import_contract')
        if not donor_signature and attestation.is_file():
            a=read_json(attestation)
            if a.get('report_sha256')==digest(report_path) and Path(a['source_snapshot']).is_file() and digest(a['source_snapshot'])==a['source_snapshot_sha256']:donor_signature=a['contract']
        if donor_signature!=signature or not Path(old_scene_path).is_file():continue
        sr=next((s for s in source_receipts if s['report']==old_scene_path and s['_artifacts'].get(old_scene_path)==digest(old_scene_path)),None)
        if not sr:continue
        old_scene=read_json(old_scene_path)
        for i,entry in enumerate(current['environment']):
            if str(i) in result or i>=len(old_scene['environment']):continue
            old=old_scene['environment'][i];pkg=Path(receipt['project']).parent/f'Content/Generated/Environment/SM_Group_{i}.uasset'
            sh=sr['_artifacts'].get(old['file']);ph=receipt['_artifacts'].get(str(pkg))
            if not sh or not ph or not eligible(entry,old,sh,pkg,ph,signature,donor_signature):continue
            destination.mkdir(parents=True,exist_ok=True);target=destination/pkg.name;shutil.copy2(pkg,target)
            if digest(target)!=ph:raise RuntimeError('Copied static package hash changed')
            result[str(i)]={'source_sha256':sh,'package_sha256':ph,'package':str(target),'donor_receipt':str(receipt_path),'contract':signature}
        if len(result)==len(current['environment']):break
    write_json(ctx.directory/'static_reuse.json',{'contract':signature,'entries':result})
    return result,signature
