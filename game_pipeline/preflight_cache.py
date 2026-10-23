"""Exact-content reuse of completed runtime evidence, including rejected art.

This cache never contains an approval. A changed map, material, DLL, scene
contract, render profile, camera or capture implementation forces recapture.
"""
from pathlib import Path
import shutil
from .core import ROOT, StageError, digest, read_json, write_json
from .rendering import profile, launch_args


def snapshot(project, scene_report, editor, tool_versions=None):
    project, editor = Path(project).resolve(), Path(editor).resolve()
    base = project.parent
    required = [project,base/'Binaries/Win64/UnrealEditor-GameDemo.dll',
                base/'Config/DefaultEngine.ini',base/'Content/Generated/Maps/Demo.umap']
    if any(not p.is_file() for p in required):
        raise StageError('Preflight source snapshot lacks project/runtime/config/map')
    files = set(required)
    for folder in ['Content','Config','Binaries','Plugins']:
        for path in (base/folder).rglob('*'):
            if path.is_file() and (folder in ['Content','Config'] or path.suffix.lower() in
                                  ['.dll','.modules','.target','.ini','.uplugin','.uasset','.umap','.uexp','.ubulk']):
                files.add(path)
    return {'schema_version':1,'project':str(project),'files':{p.relative_to(base).as_posix():digest(p) for p in sorted(files)},
            'scene_report_sha256':digest(scene_report),'engine':{'path':str(editor),'sha256':digest(editor)},
            'tool_versions':tool_versions or {},'rendering_profile':profile(),'rendering_args':launch_args(),
            'capture_implementation':{name:digest(ROOT/'game_pipeline'/name) for name in
                                      ['preflight_capture.py','preflight_cache.py','rendering.py','core.py']}}


def safe_file(folder, name):
    path = (folder/name).resolve()
    if not path.is_relative_to(folder.resolve()) or path == folder.resolve():
        raise ValueError('Capture manifest path escapes its folder')
    return path


def load_valid(folder, source):
    try:
        manifest = read_json(folder/'capture_commit.json')
        if manifest.get('source') != source or not manifest.get('files'):
            return None
        for name, sha in manifest['files'].items():
            file = safe_file(folder,name)
            if not file.is_file() or digest(file) != sha: return None
        payload = manifest['payload']
        if not payload['views'] or len(payload['views']) != len(payload['labels']):return None
        if any(v not in manifest['files'] for v in payload['views']):return None
        return manifest
    except (OSError,ValueError,KeyError,TypeError):
        return None


def commit(folder, source, payload):
    if not payload['views'] or len(payload['views']) != len(payload['labels']):
        raise StageError('Cannot commit incomplete preflight views')
    files = {p.relative_to(folder).as_posix():digest(p) for p in folder.rglob('*')
             if p.is_file() and p.name not in ['capture_commit.json']}
    if any(v not in files for v in payload['views']):raise StageError('Missing preflight image')
    write_json(folder/'capture_commit.json',{'source':source,'files':files,'payload':payload})


def restore(stage_parent, target, source):
    """Only fully committed native evidence; legacy screenshots cannot be adopted."""
    if target.exists():raise StageError('Evidence restore needs a fresh destination')
    candidates = sorted(stage_parent.glob('*/runtime_capture*'),key=lambda p:p.stat().st_mtime,reverse=True)
    for folder in candidates:
        if not folder.is_dir() or folder == target:continue
        manifest = load_valid(folder,source)
        if manifest is None:continue
        target.mkdir(parents=True)
        for name in manifest['files']:
            dst=safe_file(target,name);dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(safe_file(folder,name),dst)
        # Verify the copied bytes too. Never accept a partial copy or race.
        if any(digest(safe_file(target,n))!=h for n,h in manifest['files'].items()):
            raise StageError('Preflight evidence changed during reuse; partial copy preserved')
        write_json(target/'reuse.json',{'source':str(folder),'commit_sha256':digest(folder/'capture_commit.json'),
                   'reason':'Identical runtime/content/capture contract. Reuses observations, never visual approval.'})
        commit(target,source,manifest['payload'])
        return manifest['payload']
    return None
