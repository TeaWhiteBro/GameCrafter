"""Portable machine setup and offline prerequisites; credentials never enter reports."""
import copy
import importlib.util
import sys
from pathlib import Path
from urllib.parse import urlsplit
from .core import ROOT, StageError, read_json, write_json

CLIPS = [
    'Unarmed/MM_Idle', 'Unarmed/Walk/MF_Unarmed_Walk_Fwd', 'Unarmed/Walk/MF_Unarmed_Walk_Bwd',
    'Unarmed/Walk/MF_Unarmed_Walk_Left', 'Unarmed/Walk/MF_Unarmed_Walk_Right', 'Unarmed/Jog/MF_Unarmed_Jog_Fwd',
    'Unarmed/Attack/MM_Attack_01', 'Unarmed/Attack/MM_Attack_02', 'Unarmed/Attack/MM_Attack_03',
    'Unarmed/Attack/MM_ChargedAttack', 'Unarmed/Jump/MM_Dash', 'Rifle/HitReact/MM_HitReact_Front_Hvy_01',
    'Rifle/HitReact/MM_HitReact_Front_Lgt_01', 'Death/MM_Death_Front_01']


def initialize(path, unreal_root, blender, build_root=None, planner_model='YOUR_VISION_CAPABLE_CHAT_MODEL'):
    path = Path(path).resolve()
    if path.exists():
        raise StageError('Machine config already exists; edit it explicitly instead of overwriting it.')
    ue = Path(unreal_root).resolve()
    cfg = read_json(ROOT/'machine.example.json')
    cfg.update(python=sys.executable, blender=str(Path(blender).resolve()),
        unreal_editor=str(ue/'Engine/Binaries/Win64/UnrealEditor.exe'),
        unreal_build=str(ue/'Engine/Build/BatchFiles/Build.bat'),
        build_root=str(Path(build_root).resolve() if build_root else path.parent/'builds'),
        animation_library=str(ue/'Templates/TemplateResources/High/Characters/Content'))
    cfg['gateway']['planner_model'] = planner_model
    write_json(path,cfg)
    return path


def load(path):
    path = Path(path).resolve()
    cfg = read_json(path)
    for key in ('python','blender','unreal_editor','unreal_build','build_root','animation_library'):
        if cfg.get(key) and not Path(cfg[key]).is_absolute():
            cfg[key] = str((path.parent/cfg[key]).resolve())
    return cfg


def check(cfg):
    from .services import credential
    checks = {key:Path(cfg.get(key,'__missing__')).is_file() for key in ('python','blender','unreal_editor','unreal_build')}
    editor = Path(cfg.get('unreal_editor','__missing__'))
    checks['unreal_commandlet'] = editor.with_name('UnrealEditor-Cmd.exe').is_file()
    base = Path(cfg.get('animation_library','__missing__'))/'Mannequins'
    required = ['Meshes/SKM_Manny_Simple.uasset'] + ['Anims/'+clip+'.uasset' for clip in CLIPS]
    missing = [p for p in required if not (base/p).is_file()]
    checks['animation_assets'] = not missing
    checks['python_dependencies'] = all(importlib.util.find_spec(m) for m in ('PIL','numpy','imageio_ffmpeg'))
    checks['gateway_https'] = urlsplit(cfg.get('gateway',{}).get('base_url','')).scheme == 'https'
    model = cfg.get('gateway',{}).get('planner_model', '')
    checks['planner_model'] = isinstance(model, str) and bool(model.strip()) and not model.startswith('YOUR_')
    try:
        credential(cfg); checks['credential_readable'] = True
    except Exception:
        checks['credential_readable'] = False
    checks['generation_budgets'] = all(type(cfg.get('budgets',{}).get(k)) is int and cfg['budgets'][k] >= n
        for k,n in {'mesh_calls':5,'image_calls':1,'llm_calls':20}.items())
    return {'passed':all(checks.values()), 'checks':checks, 'missing_animation_assets':missing,
        'scope':'Offline prerequisites only. Does not certify API access, MSVC compilation, GPU performance or a completed game.',
        'animation_setup':'Install UE Templates and Feature Packs, including the High Characters resources; or supply a complete compatible Characters folder.',
        'fresh_policy':'Previous case catalogs and meshes are excluded from new fresh runs.'}
