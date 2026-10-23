from __future__ import annotations
import argparse, copy, json, os, shutil, sqlite3, sys, subprocess
from pathlib import Path
from .core import ROOT, Engine, Node, StageError, read_json, write_json, log
from .contracts import validate_spec, load_spec
from . import services, local_adapters
from . import __version__, workflow, planning_agents

REGISTRY={**services.REGISTRY,**local_adapters.REGISTRY}
from .capture_adapter import dataset
REGISTRY['ue.dataset']=dataset
REGISTRY.update(planning_agents.REGISTRY)
from . import production_capture,camera_validation,scene_preflight
from .artifacts import inherit
REGISTRY.update(production_capture.REGISTRY);REGISTRY['ue.camera_validation']=camera_validation.run
REGISTRY['artifact.inherit']=inherit
REGISTRY['ue.scene_preflight']=scene_preflight.run
from .camera_revision import run as revise_camera
REGISTRY['ue.camera_revision']=revise_camera
from . import environment_assets
REGISTRY.update(environment_assets.REGISTRY)
from . import public_surfaces
REGISTRY['resources.public_surfaces']=public_surfaces.acquire

def graph(spec,machine):
    from .fresh_sources import machine_for_spec,validate as validate_sources
    validate_sources(spec)
    machine=machine_for_spec(machine,spec)
    policy=workflow.validate(spec)
    library=machine.get('mesh_library',{});library_files=[]
    for asset in library.values():
        source=Path(asset['file']);library_files.append(str(source))
        if source.suffix.lower()=='.gltf':library_files.extend(str(p) for p in source.parent.glob('*.bin'))
        library_files.extend(asset.get('material',{}).get('textures',{}).values())
        library_files.extend(p for m in asset.get('materials',{}).values() for p in m.get('textures',{}).values())
        if asset.get('structural_proxy'):library_files.append(asset['structural_proxy'])
    library_files.extend(channels['height'] for channels in machine.get('texture_library',{}).values() if 'height' in channels)
    concept=spec.get('concept',{'provider':'gpt_image'})
    cc={'provider':concept.get('provider','gpt_image'),'model':'gpt-image-2','prompt':spec['art_direction']['concept_prompt']}
    if cc['provider']=='local':cc.update(path=concept['path'],_source_files=[concept['path']])
    if concept.get('references'):cc['references']=concept['references'];cc['_source_files']=concept['references']
    nodes=[Node('concept','image.gpt_image',cc)]
    for role,char in spec['characters'].items():
        cfg=dict(char['source']);files=[cfg[k] for k in ['path','image','front','left','back','right'] if cfg.get(k) and not cfg[k].startswith('https://')]
        if files:cfg['_source_files']=files
        nodes.append(Node('mesh_'+role,'mesh.source',cfg))
        nodes.append(Node('rig_'+role,'blender.rig',{'role':role,**{k:v for k,v in char.items() if k not in ['source','name']}},['mesh_'+role]))
    stub={'schema_version':1,'title':'Scene contract','prompt':'Scene contract','art_direction':{'concept_prompt':'Validation'},'characters':{r:{'morphology':'humanoid','height_m':1.8,'triangle_budget':50000,'source':{'provider':'local','path':'validation-only'}} for r in ['player','boss']},'scene':spec['scene'],'spawns':spec['spawns'],'lighting':spec['lighting'],'gameplay':spec['gameplay']}
    layout={'scene':spec['scene'],'lighting':spec['lighting'],'spawns':spec['spawns'],'validation_spec':stub,'agent_review':spec.get('scene_agent',True)}
    layout['available_resources']={'meshes':sorted(library),'textures':{name:sorted(channels) for name,channels in machine.get('texture_library',{}).items()},'descriptors':machine.get('asset_descriptors',{}),'art_kits':machine.get('art_kits',{})}
    nodes.extend([
        Node('scene_layout','agent.scene_layout',layout,['concept']),
        Node('scene','blender.scene',{'seed':spec.get('layout_seed',417),'mesh_library':library,'_source_files':library_files},['scene_layout']),
        Node('ue_project','ue.project',{'_source_files':[str(p) for p in (ROOT/'templates/Source').rglob('*') if p.is_file()]}),
        Node('animations','ue.animation',{'provider':'ue_mannequin_retarget'},['ue_project','rig_player','rig_boss']),
        Node('ue_assemble','ue.assemble',{'title':spec['title'],'gameplay':spec['gameplay'],
            'characters_config':{r:{'name':c['name']} for r,c in spec['characters'].items()},'lighting_overrides':spec.get('lighting_overrides',{}),
            '_source_files':[p for textures in machine.get('texture_library',{}).values() for p in textures.values()]},['ue_project','animations','scene']),
        Node('playtest','ue.playtest',{'full':spec.get('full_playtest',True)},['ue_assemble']),
        Node('review','agent.review',{'visual_agent':spec.get('review_agent',True),'original_user_brief':spec.get('prompt',''),'quality_benchmarks':spec.get('quality_benchmarks',[]),'_source_files':spec.get('quality_benchmarks',[])},['playtest','concept','scene','rig_player','rig_boss']),
        Node('delivery','release.playable',{},['review','playtest'])])
    if spec.get('dataset',{}).get('enabled',False):
        index=next(i for i,n in enumerate(nodes) if n.name=='review')
        nodes.insert(index,Node('dataset','ue.dataset',spec['dataset'],['ue_assemble','playtest']))
        next(n for n in nodes if n.name=='delivery').deps.append('dataset')
    if policy:
        scene_node=next(n for n in nodes if n.name=='scene')
        layout_node=next(n for n in nodes if n.name=='scene_layout')
        layout_node.config['production_requirements']={'exploration_required':policy['profile']=='world_demo','whitebox_required':True}
        layout_node.deps.append('art_plan')
        from .art_context import resource_intent
        planning_scene=resource_intent(spec['scene']) if policy.get('art_planning_scope')=='resource_intent_v1' else spec['scene']
        nodes.insert(nodes.index(layout_node),Node('art_plan','agent.art_plan',{'brief':spec['prompt'],'art_direction':spec['art_direction'],'scene':planning_scene,'production':policy},['concept']))
        nodes.insert(nodes.index(scene_node),Node('exploration_plan','agent.exploration_plan',{'required':policy['profile']=='world_demo','layout_config':layout},['scene_layout','concept','art_plan']))
        scene_node.deps=['exploration_plan'];scene_node.config['layout_input']='exploration_plan'
        nodes=workflow.add_acceptance(nodes,spec)
        next(n for n in nodes if n.name=='review').deps += ['art_plan','exploration_plan']
        next(n for n in nodes if n.name=='delivery').deps += ['art_plan','exploration_plan']
        planning=['concept','art_plan','scene_layout','exploration_plan']
        resources=spec.get('environment_assets',{})
        if resources.get('enabled'):
            demands=Node('asset_demands','agent.environment_demands',{'brief':spec['prompt'],'art_direction':spec['art_direction'],**resources},['concept'])
            demands.config['_source_files']=[a['image'] for a in resources.get('plan',{}).get('generated_assets',[]) if a.get('image')]
            generated=Node('environment_assets','environment.generate',{'max_new_assets':resources.get('max_new_assets',3),'original_user_brief':spec.get('prompt','')},['asset_demands'])
            if spec.get('surface_assets'):
                demands.config['surface_assets']=spec['surface_assets']
                surfaces=Node('surface_assets','resources.public_surfaces',spec['surface_assets'],['asset_demands'])
                generated.deps.append('surface_assets')
                nodes.append(surfaces)
                next(n for n in nodes if n.name=='delivery').deps.append('surface_assets')
            nodes += [demands,generated]
            next(n for n in nodes if n.name=='art_plan').deps.append('environment_assets')
            next(n for n in nodes if n.name=='delivery').deps += ['asset_demands','environment_assets']
            planning=['concept','asset_demands']+(['surface_assets'] if spec.get('surface_assets') else [])+['environment_assets','art_plan','scene_layout','exploration_plan']
        nodes=[next(n for n in nodes if n.name==name) for name in planning]+[n for n in nodes if n.name not in planning]
    # Any stage can be replaced by a registered adapter, or a JSON command plugin.
    for n in nodes:
        override=spec.get('adapters',{}).get(n.name)
        if override:
            n.adapter=override['adapter'];n.config.update(override.get('config',{}))
            if n.adapter=='artifact.inherit':
                n.config=dict(override['config']);n.deps=[]
    # An inherited final rig must not trigger its old paid mesh source as an orphan.
    needed=set()
    by_name={n.name:n for n in nodes}
    def visit(name):
        if name in needed:return
        needed.add(name)
        for dep in by_name[name].deps:visit(dep)
    visit('delivery')
    nodes=[n for n in nodes if n.name in needed]
    return nodes

ALLOWED_REPAIRS={'lighting.exposure_bias':(-2,2),'lighting.fog_density':(0,.03),'lighting.sky_intensity':(.2,2)}
def repair(spec,review):
    updated=copy.deepcopy(spec);applied=[]
    for item in review.get('suggested_repairs',[]):
        field=item.get('field');value=item.get('value')
        if field not in ALLOWED_REPAIRS or isinstance(value,bool) or not isinstance(value,(int,float)):continue
        lo,hi=ALLOWED_REPAIRS[field]
        if not lo<=value<=hi:continue
        name=field.split('.')[1]
        if updated.get('lighting_overrides',{}).get(name,spec['lighting'].get(name))==value:continue
        updated.setdefault('lighting_overrides',{})[name]=value;applied.append(item)
    return updated,applied

def doctor(machine):
    from .machine import check
    report=check(machine);report['pipeline_version']=__version__
    print(json.dumps(report,indent=2));return report['passed']

def main():
    p=argparse.ArgumentParser(description='Prompt/reference -> asset generation -> Blender -> UE -> playable boss demo')
    p.add_argument('--machine',type=Path,default=ROOT/'machine.local.json')
    p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    init=sub.add_parser('init',help='Write a portable local config without credentials or private content')
    init.add_argument('--unreal-root',type=Path,required=True);init.add_argument('--blender',type=Path,required=True)
    init.add_argument('--build-root',type=Path);init.add_argument('--planner-model',default='YOUR_VISION_CAPABLE_CHAT_MODEL')
    timing=sub.add_parser('timing',help='Read-only time/rework audit; no machine config or gateway required')
    timing.add_argument('--run-dir',type=Path,required=True)
    timing.add_argument('--out',type=Path)
    diagnosis=sub.add_parser('diagnose',help='Read-only failure, repair and timing summary; no machine or API required')
    diagnosis.add_argument('--run-dir',type=Path,required=True)
    preview=sub.add_parser('impact',help='Read-only implementation invalidation preview from the saved DAG')
    preview.add_argument('--run-dir',type=Path,required=True)
    preview.add_argument('--changed-file',action='append',required=True)
    upgrade=sub.add_parser('upgrade',help='Explicit isolated upgrade of an accepted demo (provided content)')
    upgrade.add_argument('--from-run',type=Path,required=True);upgrade.add_argument('--run-dir',type=Path,required=True)
    upgrade.add_argument('--scene-report',type=Path);upgrade.add_argument('--title')
    upgrade.add_argument('--review-geometry-audit',type=Path,action='append',default=[])
    upgrade.add_argument('--profile',choices=['world_demo','arena_demo'],default='world_demo')
    upgrade.add_argument('--capture-frames',type=int,default=360);upgrade.add_argument('--until');upgrade.add_argument('--replay',action='store_true')
    for name in ['run','plan','replay','status','repair','invalidate','play']:
        cmd=sub.add_parser(name);cmd.add_argument('--run-dir',type=Path,required=True)
        if name=='invalidate':cmd.add_argument('--stage',required=True)
        if name in ['run','plan']:
            cmd.add_argument('--prompt');cmd.add_argument('--prompt-file',type=Path);cmd.add_argument('--spec',type=Path);cmd.add_argument('--reference-scene',type=Path)
            cmd.add_argument('--source-policy',choices=['fresh','provided'])
            cmd.add_argument('--player-image',type=Path);cmd.add_argument('--boss-image',type=Path)
            cmd.add_argument('--until');cmd.add_argument('--max-repairs',type=int,default=2)
            cmd.add_argument('--profile',choices=['world_demo','arena_demo'])
            cmd.add_argument('--capture-frames',type=int)
    a=p.parse_args()
    if a.command in ['diagnose','impact']:
        from .diagnostics import diagnose,impact
        result=diagnose(a.run_dir) if a.command=='diagnose' else impact(read_json(a.run_dir/'pipeline_manifest.json')['stages'],a.changed_file)
        print(json.dumps(result,indent=2));return 0
    if a.command=='timing':
        from .timing import audit,markdown
        report=audit(a.run_dir)
        if a.out:
            a.out.mkdir(parents=True,exist_ok=True)
            write_json(a.out/'timing.json',report)
            (a.out/'TIMING.md').write_text(markdown(report),encoding='utf-8')
        print(markdown(report));return 0
    if a.command=='init':
        from .machine import initialize
        print(initialize(a.machine,a.unreal_root,a.blender,a.build_root,a.planner_model));return 0
    if getattr(a,'prompt_file',None):
        if a.prompt:raise StageError('Use either --prompt or --prompt-file.')
        a.prompt=a.prompt_file.read_text(encoding='utf-8-sig').strip()
    if getattr(a,'prompt',None) and getattr(a,'spec',None):
        raise StageError('Use either a prompt or --spec, not both.')
    for option in ('reference_scene','player_image','boss_image'):
        source=getattr(a,option,None)
        if source:
            from PIL import Image
            if not source.is_file():raise StageError('Missing input image: '+str(source))
            with Image.open(source) as reference:reference.verify()
    from .machine import load
    machine=load(a.machine)
    if a.command=='doctor':return 0 if doctor(machine) else 1
    if a.command=='upgrade':
        from upgrade_demo import main as upgrade_main
        report=a.scene_report or Path(read_json(a.from_run/'run_summary.json')['nodes']['scene']['report'])
        args=['--from-run',str(a.from_run),'--run-dir',str(a.run_dir),'--scene-report',str(report),'--profile',a.profile,'--capture-frames',str(a.capture_frames),'--machine',str(a.machine)]
        for audit in a.review_geometry_audit:args+=['--review-geometry-audit',str(audit)]
        if a.title:args+=['--title',a.title]
        if a.until:args+=['--until',a.until]
        if a.replay:args+=['--replay']
        upgrade_main(args);return 0
    root=a.run_dir.resolve()
    if a.command=='status':
        db=sqlite3.connect(root/'run.sqlite');print(json.dumps([{'stage':n,'status':s,'updated':t} for n,s,t in db.execute('select name,status,updated from nodes')],indent=2));return 0
    if a.command=='play':
        release=read_json(root/'release.json')
        from .rendering import launch_args
        subprocess.Popen([machine['unreal_editor'],release['project'],'/Game/Generated/Maps/Demo','-game','-windowed','-ResX=1600','-ResY=900','-ForceRes','-ddc=InstalledNoZenLocalFallback','-NoLiveCoding']+launch_args())
        log('Launched this run.');return 0
    if a.command=='run':
        from .machine import check
        readiness=check(machine)
        write_json(root/'machine_preflight.json',readiness)
        if not readiness['passed']:
            raise StageError('Machine prerequisites failed before any paid generation. Run pipeline.py doctor and resolve its checks.')
    if a.command in ('run','plan') and getattr(a,'prompt',None) and (root/'game_spec.json').exists():
        raise StageError('This run already has a spec. Resume without --prompt, or choose a new run directory.')
    engine=Engine(root,machine,REGISTRY)
    spec_file=root/'game_spec.json'
    if a.command in ['run','plan'] and a.prompt:
        cfg={'prompt':a.prompt,'production_profile':getattr(a,'profile',None) or 'world_demo'}
        if a.reference_scene:cfg['reference_images']=[str(a.reference_scene.resolve())];cfg['_source_files']=cfg['reference_images']
        result=engine.execute([Node('design','agent.design',cfg)])
        spec=read_json(result['design']['spec'])
        if a.reference_scene:spec['concept']['references']=[str(a.reference_scene.resolve())]
    elif getattr(a,'spec',None):spec=load_spec(a.spec)
    elif spec_file.exists():spec=load_spec(spec_file)
    else:raise StageError('Provide --prompt or --spec to start a new run.')
    profile=getattr(a,'profile',None)
    if profile or ((getattr(a,'prompt',None) or getattr(a,'source_policy',None)) and not spec.get('production')):
        spec=workflow.configure(spec,profile or 'world_demo',getattr(a,'capture_frames',None) or 360,
            source_policy=getattr(a,'source_policy',None) or 'fresh')
    elif getattr(a,'capture_frames',None) is not None:
        if not spec.get('production'):raise StageError('--capture-frames needs a production profile')
        spec['dataset']['frames']=a.capture_frames
    workflow.validate(spec)
    for role in ['player','boss']:
        image=getattr(a,role+'_image',None)
        if image:
            from .replacement import character_with_source
            source={'provider':'tripo','mode':'image','image':str(image.resolve())}
            if spec['characters'][role]['source']!=source:
                spec['characters'][role]=character_with_source(spec['characters'][role],source)
            config=spec.setdefault('adapters',{}).setdefault('review',{'adapter':'agent.review','config':{}}).setdefault('config',{})
            config.setdefault('character_references',{})[role]=[str(image.resolve())]
            config['_source_files']=sorted(set(config.get('_source_files',[])+[str(image.resolve())]))
    if getattr(a,'source_policy',None):
        spec.setdefault('production',{})['source_policy']=a.source_policy
    from .fresh_sources import machine_for_spec,validate as validate_sources,is_fresh
    validate_sources(spec)
    if is_fresh(spec):machine=machine_for_spec(machine,spec)
    else:
        from .catalog import mount
        machine=mount(machine)
    engine.machine=machine
    validate_spec(spec);write_json(spec_file,spec)
    if a.command=='invalidate':
        nodes=graph(spec,machine);names={n.name for n in nodes}
        if a.stage not in names:raise StageError('Unknown stage '+a.stage)
        from .diagnostics import descendants
        affected=descendants([{'name':n.name,'dependencies':n.deps} for n in nodes],{a.stage})
        for name in affected:engine.db.execute('update nodes set status="invalidated" where name=?',(name,))
        engine.db.commit();log('Invalidated: '+', '.join(sorted(affected)));return 0
    if a.command=='plan':
        workflow.save_manifest(root,graph(spec,machine),spec)
        log('Validated plan: '+str(spec_file));return 0
    if a.command=='repair':
        row=engine.db.execute('select result from nodes where name="review" and status="complete"').fetchone()
        if not row:raise StageError('No completed review to repair.')
        spec,applied=repair(spec,read_json(json.loads(row[0])['review']))
        if not applied:raise StageError('Review contains no allowed automatic repair. Read its diagnostics.')
        write_json(spec_file,spec);write_json(root/'applied_repairs.json',applied)
    for cycle in range(getattr(a,'max_repairs',0)+1):
        try:
            nodes=graph(spec,machine);workflow.save_manifest(root,nodes,spec)
            result=engine.execute(nodes,replay=a.command=='replay',until=getattr(a,'until',None))
            if 'delivery' in result:write_json(root/'release.json',read_json(result['delivery']['release']))
            log('Pipeline completed requested stages.');return 0
        except StageError:
            if a.command!='run' or cycle>=a.max_repairs:raise
            row=engine.db.execute('select result from nodes where name="review" and status="complete"').fetchone()
            if not row:raise
            spec2,applied=repair(spec,read_json(json.loads(row[0])['review']))
            if not applied:raise
            spec=spec2;write_json(spec_file,spec);write_json(root/f'repair_{cycle+1}.json',applied)
            log('Applying bounded art repair; rerunning affected stages.')

if __name__=='__main__':
    for stream in [sys.stdout,sys.stderr]:
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    try:sys.exit(main())
    except (StageError,ValueError,OSError,KeyError) as exc:
        log(type(exc).__name__+': '+str(exc));sys.exit(1)
