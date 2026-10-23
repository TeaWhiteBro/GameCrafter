"""Change camera configuration in an isolated project, preserving all content."""
import math
from pathlib import Path
from .core import ROOT, StageError, digest, read_json, write_json


def run(ctx, cfg):
    from .local_adapters import clone_project
    parent = Path(cfg['parent_project']).resolve()
    source = cfg['parent_content']
    if not source or any(not (parent.parent/p).is_file() or digest(parent.parent/p) != sha
                         for p, sha in source.items()):
        raise StageError('Camera revision parent content changed')
    camera = cfg['camera']
    limits = {'camera_yaw': (-180, 180), 'camera_pitch': (-80, -15), 'camera_width_cm': (1150, 3000)}
    if not camera or set(camera)-set(limits) or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        or not limits[k][0] <= v <= limits[k][1] for k, v in camera.items()):
        raise StageError('Invalid bounded camera configuration')
    project = Path(clone_project(ctx, parent, 'camera_revision', True))
    job = ctx.directory/'camera_job.json'
    native = ctx.directory/'camera_change.json'
    write_json(job, {'camera': camera, 'result': str(native)})
    editor = Path(ctx.machine['unreal_editor'])
    ctx.run([editor.with_name('UnrealEditor-Cmd.exe'), project, '-run=pythonscript',
             '-script='+str(ROOT/'adapters/unreal/revise_camera.py'), '-unattended',
             '-nullrhi', '-nosplash', '-NoLiveCoding', '-ddc=InstalledNoZenLocalFallback',
             '-abslog='+str(ctx.directory/'engine.log')],
            env={'GAMECRAFTER_CAMERA_JOB': str(job)}, timeout=240)
    change = read_json(native)
    if not change.get('passed') or change['camera_after'] != camera:
        raise StageError('Native camera properties were not applied')
    map_name = 'Content/Generated/Maps/Demo.umap'
    for name, sha in source.items():
        if digest(parent.parent/name) != sha:
            raise StageError('Camera update changed the original project')
        if name.replace('\\', '/') != map_name and digest(project.parent/name) != sha:
            raise StageError('Camera-only update changed another content file: '+name)
    report = read_json(cfg['parent_report'])
    report['camera_revision'] = {'parent_project': str(parent), 'camera': camera,
                                 'native_evidence': str(native), 'content_invariant_except_map': True}
    report_path = ctx.directory/'report.json'
    write_json(report_path, report)
    return {'project': str(project), 'map': '/Game/Generated/Maps/Demo',
            'report': str(report_path), '_files': [report_path, native, job]+
            [project.parent/name for name in source]}
