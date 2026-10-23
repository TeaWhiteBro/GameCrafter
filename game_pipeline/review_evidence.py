"""Verify optional geometric diagnostics before showing them to a visual reviewer."""
from pathlib import Path
from .core import read_json,digest,StageError

def _row_status(row):
    """Only explicit measurement flags establish a labelled pass or failure."""
    flags=[v for k,v in row.items() if (k=='passed' or k.endswith('_passed')) and type(v) is bool]
    if row.get('whole_piece_detached') is True:return 'failed'
    if False in flags:return 'failed'
    return 'passed' if flags else 'unlabelled'


def _row_error(row):
    keys=('max_bottom_gap_m','max_error_m','p95_error_m','error_m')
    return max([abs(row[k]) for k in keys if type(row.get(k)) in (int,float)]+[0.])


def compact_audit(value, key=''):
    """Summarize measurements for context, never decide acceptance.

    Full audits stay authoritative. Image coverage is retained. Truncated
    tables explicitly expose all status counts, including omitted failures.
    """
    if isinstance(value,dict):return {k:compact_audit(v,k) for k,v in value.items()}
    if not isinstance(value,list):return value
    if key=='images' or len(value)<=8 or not all(isinstance(v,dict) for v in value):
        return [compact_audit(v) for v in value]
    ranked=sorted(enumerate(value),key=lambda item:(_row_status(item[1])=='failed',_row_error(item[1])),reverse=True)
    chosen=ranked[:8]
    counts={status:sum(_row_status(row)==status for row in value) for status in ['passed','failed','unlabelled']}
    return {'summary_only':True,'total_rows':len(value),'status_counts':counts,
            'omitted_rows':len(value)-len(chosen),
            'omitted_failed_rows':counts['failed']-sum(_row_status(row)=='failed' for _,row in chosen),
            'selected_rows':[{'source_index':index,'row':compact_audit(row)} for index,row in chosen],
            'selection':'Explicit failures first, then largest recorded error. Full source audit remains authoritative and unchanged.'}


def geometry_evidence(paths,scene_report):
    scene=read_json(scene_report);result=[]
    for path in paths:
        audit=read_json(path)
        if audit.get('source_report_sha256')!=digest(scene_report) or audit.get('source_blend_sha256')!=digest(scene['blend']):
            raise StageError('Geometry review evidence refers to an outdated scene: '+str(path))
        # The complete diagnostic remains a hashed stage artifact. Keep the
        # review payload bounded while retaining the worst support cases.
        summary=audit
        if 'components' in audit:
            components=audit['components']
            summary={k:v for k,v in audit.items() if k!='components'}
            summary.update(components=len(components),detached_components=sum(r.get('whole_piece_detached',False) for r in components),
                largest_undercuts=sorted(components,key=lambda r:r.get('max_bottom_gap_m',0),reverse=True)[:8])
        if 'source_snapshot' in summary:
            from .core import fingerprint
            summary={**summary,'source_snapshot':{'sha256':fingerprint(summary['source_snapshot']),
                'file_count':len(summary['source_snapshot'].get('files',{})),
                'scope':'Complete snapshot is validated separately against current native source before images are admitted.'}}
        result.append({'file':Path(path).name,'source_audit_sha256':digest(path),'audit':compact_audit(summary),
            'scope':'Measured geometric support; does not establish artistic quality or waive current visual defects.'})
    return result


def diagnostic_views(paths,scene_report):
    """Additional views resolve occluded geometry without replacing runtime art."""
    geometry_evidence(paths,scene_report)
    result=[]
    for path in paths:
        audit=read_json(path)
        for image in audit.get('images',[]):
            if image.get('evidence_type')=='ue_normal_runtime':continue
            if image.get('evidence_type') not in ('blender_geometry_diagnostic','ue_geometry_diagnostic') or not image.get('caption'):
                raise StageError('Geometry diagnostic image needs an explicit renderer/scope and caption')
            file=Path(image.get('path',''))
            if not file.is_file() or digest(file)!=image.get('sha256'):
                raise StageError('Geometry diagnostic image changed or is missing: '+str(file))
            result.append({'path':str(file),'caption':image['caption'],'evidence_type':image['evidence_type']})
    if len(result)>12:raise StageError('Keep supplementary geometry diagnostics bounded to twelve views')
    return result


def normal_runtime_views(paths,scene_report,project,editor,tool_versions=None):
    """Accept camera-only observations only with current complete native proof.

    Geometry-only hashes cannot promote a diagnostic into finished art. This
    additional contract binds the original map, materials, module, settings,
    renderer, camera proof and unchanged native actor render-state signatures.
    """
    from .preflight_cache import snapshot
    from .rendering import launch_args
    geometry_evidence(paths,scene_report)
    current=None;result=[]
    for path in paths:
        audit=read_json(path)
        images=[i for i in audit.get('images',[]) if i.get('evidence_type')=='ue_normal_runtime']
        if not images:continue
        if current is None:current=snapshot(project,scene_report,editor,tool_versions)
        if audit.get('normal_runtime_contract')!='camera_only_clone_v1' or audit.get('source_snapshot')!=current:
            raise StageError('Normal runtime evidence lacks the current complete project/rendering snapshot')
        proofs=audit.get('group_proofs',[])
        if not proofs:raise StageError('Normal runtime evidence lacks native observation proof')
        groups={}
        for proof in proofs:
            geometry=proof.get('geometry',{});camera=proof.get('camera',{})
            before=geometry.get('actor_render_signature_before')
            changed=geometry.get('changed_properties')
            allowed={'player.exploration_places','player.exploration_names','player.camera_yaw'}
            if (geometry.get('passed') is not True or not isinstance(before,str) or len(before)!=64
                or before!=geometry.get('actor_render_signature_after')
                or not changed or not set(changed)<=allowed
                or proof.get('rendering_args')!=launch_args()
                or proof.get('normal_rendering') is not True
                or camera.get('current_runtime_views') is not True
                or camera.get('view_centres_verified') is not True
                or camera.get('ground_camera_clearance_verified') is not True):
                raise StageError('Normal runtime observation changed scene/rendering state or lacks camera proof')
            groups[proof['group']]=camera['view_count']
        for group,count in groups.items():
            if sum(i.get('group')==group for i in images)!=count:
                raise StageError('Normal runtime observation image coverage differs from native proof')
        for item in images:
            file=Path(item.get('path',''))
            if (item.get('group') not in groups or not item.get('caption')
                or not file.is_file() or digest(file)!=item.get('sha256')):
                raise StageError('Normal runtime image changed, is missing, or has no proven camera group')
            result.append({'path':str(file),'caption':item['caption']})
    if len(result)>12:raise StageError('Keep additional normal observations bounded to twelve views')
    return result
