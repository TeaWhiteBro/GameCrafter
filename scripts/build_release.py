"""Export a clean, allowlisted source distribution; never copy runs or local config."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game_pipeline import __version__

FILES = [
    'README.md','README.zh-CN.md','AGENTS.md','AGENT_PROTOCOL.md','QUALITY_GATES.md','DATASET.md',
    'CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICES.md','CONTRIBUTING.md','SECURITY.md',
    '.gitignore','.gitattributes','.editorconfig',
    'pipeline.py','capture_dataset.py','replace_character.py','upgrade_demo.py',
    'attach_geometry_diagnostics.py','inspect_pixel.py','preview_scene.py',
    'setup.ps1','requirements.lock.txt','toolchain.lock.json','machine.example.json','config/production_rules.json',
    'examples/local_assets.spec.json','examples/mesh_source_variants.json',
    'examples/benchmark_prompts.json','examples/prompts/agent_task.txt']
DIRECTORIES = ['game_pipeline','adapters','templates/Source','tests','config','docs','.github','scripts','examples/prompts']
SUFFIXES={'.py','.cpp','.h','.cs','.json','.md','.html','.css','.js','.svg','.txt','.yml','.yaml','.ps1'}
SECRET = re.compile(r'\bsk-[A-Za-z0-9_\-]{12,}|Bearer\s+(?!\$|YOUR_|<|\{|\+)[A-Za-z0-9_\-]{18,}')
PRIVATE = re.compile(r'[A-Z]:[/\\]+Users[/\\]+(?!YOUR_USER[/\\]|Public[/\\]|Default[/\\])[^/\\\s"\']+[/\\]|Documents[/\\]+Codex[/\\]+20\d\d',re.I)


def source_files():
    selected={ROOT/name for name in FILES}
    for folder in DIRECTORIES:
        selected.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in SUFFIXES
                        and not {'__pycache__','node_modules','.venv'} & set(p.parts))
    # The obsolete private image-script bridge is not part of the public provider.
    selected.discard(ROOT/'game_pipeline/image_cli_runner.py')
    return sorted(selected)


def export(destination, archive=None):
    destination=Path(destination).resolve()
    if destination==ROOT or ROOT in destination.parents:
        raise ValueError('Export to a new sibling directory, outside the source tree.')
    if destination.exists():
        raise ValueError('Export destination exists; select a new directory, preserving earlier exports.')
    files=source_files()
    for p in files:
        if not p.is_file():raise ValueError('Missing source file: '+str(p.relative_to(ROOT)))
        data=p.read_text(encoding='utf-8-sig')
        if SECRET.search(data) or PRIVATE.search(data):
            raise ValueError('Possible credential or private path in '+str(p.relative_to(ROOT)))
    manifest={'version':__version__,'policy':'Allowlisted source only; no prior case assets, machine config, credentials or engine content.','files':{}}
    destination.mkdir(parents=True)
    for p in files:
        relative=p.relative_to(ROOT);target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target);manifest['files'][relative.as_posix()]=hashlib.sha256(target.read_bytes()).hexdigest()
    (destination/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    if archive:
        archive=Path(archive).resolve()
        if archive.exists():raise ValueError('Archive exists; choose a new name.')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(destination.rglob('*')):
                if p.is_file():z.write(p,destination.name+'/'+p.relative_to(destination).as_posix())
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path);parser.add_argument('--zip',type=Path)
    args=parser.parse_args();manifest=export(args.out,args.zip)
    print(json.dumps({'version':manifest['version'],'source_files':len(manifest['files']),'output':str(args.out)},indent=2))
