"""Mount audited external art libraries without binding game content to runtime."""
import copy,json,hashlib
from pathlib import Path

def validate_entry(entry,base,verify_hashes=False):
    if entry.get('provenance') in ['generated','procedural']:
        expected=('provider_terms','tripo:') if entry['provenance']=='generated' else ('project-authored+CC0-textures','blender:')
        if entry.get('license')!=expected[0] or not entry.get('source','').startswith(expected[1]):
            raise ValueError('Generated resources must retain provider provenance; never label them CC0')
        binding=entry.get('binding',{})
        required=[binding.get('file'),binding.get('structural_proxy'),entry.get('visual_review')]
        required += [p for m in binding.get('materials',{}).values() for p in m.get('textures',{}).values()]
        if not required or any(not p or not Path(p).is_file() for p in required):raise ValueError('Incomplete generated model/texture/proxy/review')
        recorded={str((Path(base)/item['path']).resolve()) for item in entry.get('files',[])}
        if any(str(Path(p).resolve()) not in recorded for p in required):raise ValueError('Generated dependency missing from provenance manifest')
        if json.loads(Path(entry['visual_review']).read_text(encoding='utf-8')).get('approved') is not True:raise ValueError('Generated asset has no passing visual source review')
        for item in entry['files']:
            path=(Path(base)/item['path']).resolve()
            if Path(base).resolve() not in path.parents:raise ValueError('Asset escaped its library')
            if not path.is_file() or (verify_hashes and hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']):raise ValueError('Corrupt generated asset dependency')
        return
    if entry.get('license')!='CC0-1.0':raise ValueError('This provider requires recorded CC0 provenance')
    if not entry.get('source','').startswith('https://polyhaven.com/a/'):raise ValueError('Missing scan provenance')
    if not {'base','normal','roughness'}<=set(entry.get('textures',{})):raise ValueError('Incomplete PBR texture set')
    if entry.get('normal_convention') not in ['DirectX','OpenGL']:raise ValueError('Unknown normal convention')
    for key,path in entry['textures'].items():
        if not Path(path).is_file():raise ValueError('Missing '+key+' texture: '+path)
    for item in entry['files']:
        path=(Path(base)/item['path']).resolve()
        if Path(base).resolve() not in path.parents:raise ValueError('Asset escaped its library')
        if not path.is_file():raise ValueError('Missing asset dependency '+str(path))
        if verify_hashes and hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Corrupt asset dependency '+str(path))

def mount(machine,verify_hashes=False):
    machine=copy.deepcopy(machine)
    if not machine.get('asset_catalog'):return machine
    path=Path(machine['asset_catalog'])
    paths=[path]+sorted((path.parent/'extensions').glob('*/catalog.json'))
    entries=[];seen=set()
    for source_path in paths:
        data=json.loads(source_path.read_text(encoding='utf-8'))
        if data.get('errors'):raise ValueError('Catalog contains incomplete downloads: '+str(source_path))
        for name,entry in data['entries'].items():
            if name in seen:raise ValueError('Catalog extension would overwrite existing resource: '+name)
            seen.add(name);entries.append((name,entry,source_path.parent))
    machine.setdefault('texture_library',{});machine.setdefault('mesh_library',{});descriptors={}
    for name,entry,base in entries:
        validate_entry(entry,base,verify_hashes)
        if entry.get('provenance') in ['generated','procedural']:
            machine['mesh_library'][name]=copy.deepcopy(entry['binding'])
            descriptors[name]=copy.deepcopy(entry['descriptor'])
            continue
        if entry['kind']=='textures':machine['texture_library'][name]=entry['textures']
        else:
            bound={k:entry[k] for k in ['file','triangle_budget','material_id','material']}
            bound['variant_mode']=entry.get('variant_mode','assembled')
            bound['preserve_aspect']=entry.get('preserve_aspect',True)
            bound['placement']=entry.get('placement','prop')
            bound['material']['semantic_class']=entry['category']
            machine['mesh_library'][name]=bound
        descriptors[name]={k:entry[k] for k in ['kind','category','scale_cm','normal_convention','source']}
        descriptors[name]['channels']=sorted(entry['textures'])
        descriptors[name]['license']=entry['license']
        if entry['kind']=='models':descriptors[name].update(placement=entry.get('placement','prop'),variant_mode=entry.get('variant_mode','assembled'),preserve_aspect=entry.get('preserve_aspect',True))
    guidance=path.parent/'usage_guidance.json'
    if guidance.is_file():
        for name,notes in json.loads(guidance.read_text(encoding='utf-8')).items():
            if name not in descriptors:raise ValueError('Usage guidance references unavailable resource: '+name)
            descriptors[name]['usage_guidance']=notes
    machine['asset_descriptors']=descriptors
    machine['art_kits']={}
    for kit in [path.parent/'art_kits.json']+sorted((path.parent/'extensions').glob('*/art_kits.json')):
        if not kit.exists():continue
        for name,data in json.loads(kit.read_text(encoding='utf-8')).items():
            if name in machine['art_kits']:raise ValueError('Art-kit extension overwrites an existing kit: '+name)
            if any(t not in machine['texture_library'] for t in data.get('textures',[])) or any(m not in machine['mesh_library'] for m in data.get('meshes',[])):
                raise ValueError('Art-kit references unavailable resources: '+name)
            machine['art_kits'][name]=data
    return machine
