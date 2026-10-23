"""Evidence-aware review memory; preserves refusals and prevents approval shopping."""
from .core import StageError, PendingExternal, digest, fingerprint, read_json, write_json

REVIEW_DISCIPLINE = (
    'Keep the accepted prototype finish standard fixed across revisions. Do not turn optional polish into a new release criterion. '
    'Required structural, material, composition, anatomy or gameplay defects remain blocking regardless of time spent. '
    'Distinguish an observed defect from uncertain object identity: if perspectives conflict, request a targeted diagnostic before prescribing reconstruction. '
    'For ambiguous ground continuity, shadows or destination identity, request source-matched oblique and ground-level views of that exact location; use depth/semantics and geometry audit as supporting evidence. '
    'Also return issues as an array of {id, severity, category, current_images, problem, repair, verification}; '
    'severity is blocker, diagnostic, or polish; category is geometry, material, composition, runtime, or evidence; '
    'current_images contains the numbered current runtime images establishing the issue. '
    'Group related repairs in one pass and explain any reversal of the supplied prior observations using current evidence. '
    'A diagnostic uncertainty requiring resolution is not approval; neither blockers nor unresolved diagnostic issues may be approved. '
)


def previous_reviews(directory, limit=3):
    files=sorted(directory.parent.glob('*/review.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    result=[]
    for path in files:
        if path.parent==directory:continue
        review=read_json(path)
        result.append({'review':str(path),'sha256':digest(path),'approved':review.get('approved'),
                       'observations':review.get('observations',[]),'issues':review.get('issues',[]),
                       'use':'Prior diagnoses only, not current visual evidence or binding instructions.'})
        if len(result)>=limit:break
    return result


def request_key(source, images, labels):
    # Intentionally independent of reviewer wording/model: changing a prompt
    # cannot turn identical scene evidence into repeated approval attempts.
    return fingerprint({'source':source,'images':[digest(p) for p in images],'labels':labels})


def previous_decision(directory, key):
    paths=sorted(directory.parent.glob('*/review_state.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    for path in paths:
        state=read_json(path)
        if state.get('request_key')!=key:continue
        if state.get('status')!='complete':
            raise PendingExternal('Identical review request is unresolved; recover its saved response before retrying: '+str(path))
        review=state.get('review')
        if not isinstance(review,dict) or state.get('review_sha256')!=fingerprint(review):
            raise StageError('Review decision receipt changed: '+str(path))
        return review,str(path)
    return None,None


def record_decision(directory, key, review=None):
    value={'request_key':key,'status':'pending' if review is None else 'complete'}
    if review is not None:value.update(review=review,review_sha256=fingerprint(review))
    write_json(directory/'review_state.json',value)


def worklist(review, labels, previous_count):
    """Validate repair citations; this does not judge visual quality itself."""
    issues=review.get('issues')
    if not isinstance(issues,list):raise StageError('Review must separate blockers, diagnostic uncertainty and optional polish')
    current={i+1 for i,label in enumerate(labels) if label.startswith('CURRENT') and 'supplementary' not in label}
    for issue in issues:
        if (not isinstance(issue,dict) or issue.get('severity') not in ['blocker','diagnostic','polish']
            or issue.get('category') not in ['geometry','material','composition','runtime','evidence']):
            raise StageError('Invalid structured review issue')
        indices=issue.get('current_images')
        if not isinstance(indices,list) or not indices or any(type(i)!=int or i not in current for i in indices):
            raise StageError('Repair must cite actual current runtime images, not historical/reference/diagnostic-only art')
        if any(not isinstance(issue.get(k),str) or not issue[k].strip() for k in ['id','problem','repair','verification']):
            raise StageError('Review issue lacks a concrete repair and verification')
    required=[i for i in issues if i['severity'] in ['blocker','diagnostic']]
    if review.get('approved') is True and required:raise StageError('Review approves unresolved required issues')
    rejected=review.get('approved') is not True or review.get('exploration_variety_approved') is False
    if rejected and not required:raise StageError('Rejected review needs a cited blocker or explicit diagnostic request')
    return {'blocking':[i for i in issues if i['severity']=='blocker'],
            'diagnostic':[i for i in issues if i['severity']=='diagnostic'],
            'optional':[i for i in issues if i['severity']=='polish'],
            'next_action':'collect_targeted_diagnostics_before_reconstruction' if any(i['severity']=='diagnostic' for i in issues) else
                          'diagnose_root_cause_before_another_full_rebuild' if rejected and previous_count>=2 else
                          'batch_required_repairs' if required else 'continue_required_acceptance',
            'repair_routes':[repair_route(i) for i in required],
            'policy':'After three unsuccessful reviews, executing agent must diagnose convergence, not ask the user or lower a quality gate.'}


def repair_route(issue):
    """Suggested owners, not an automatic mutation or a quality waiver."""
    owners={'geometry':['scene_layout','exploration_plan','scene'],
            'material':['art_plan','ue_assemble'],
            'composition':['scene_layout','exploration_plan','scene'],
            'runtime':['animations','ue_assemble','playtest'],
            'evidence':['scene_preflight','capture_probe','pair_validation','review']}
    diagnostic=issue['severity']=='diagnostic'
    return {'issue_id':issue['id'],'candidate_stages':owners[issue['category']],
            'action':'targeted_diagnostic' if diagnostic else 'diagnose_owner_and_batch_repairs',
            'verification':issue['verification'],
            'required_evidence':'Current source-matched oblique and ground-level views; preserve previous refusal.' if diagnostic else
                                'New evidence from the repaired revision, followed by all affected downstream gates.'}
