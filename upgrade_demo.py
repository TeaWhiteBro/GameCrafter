"""Upgrade a released demo's runtime/art in an isolated, resumable local DAG."""
from pathlib import Path
import argparse,json,shutil,sys
from game_pipeline.core import Engine,Node,ROOT,read_json,write_json,digest,StageError
from game_pipeline.catalog import mount
from game_pipeline import local_adapters as local
from game_pipeline.contracts import validate_rig
from game_pipeline.capture_adapter import dataset
from game_pipeline import scene_preflight

def inherited(ctx,cfg):
    result=cfg['result'];files=cfg['files']
    for path,expected in cfg['hashes'].items():
        if digest(path)!=expected:raise StageError('Inherited accepted artifact changed: '+path)
    if cfg.get('rig'):validate_rig(read_json(result['report']))
    record=ctx.directory/'inheritance.json';write_json(record,{'files':cfg['hashes'],'parent_release':cfg['parent_release']})
    return {**result,'_files':files+[record]}

def runtime(ctx,cfg):
    result=local.project(ctx,cfg);project=Path(result['project']);parent=Path(cfg['parent_project'])
    shutil.copytree(parent.parent/'Content',project.parent/'Content',dirs_exist_ok=True)
    result['_files'] += list((project.parent/'Content/Generated').rglob('*.uasset'))
    return result

def animation_reuse(ctx,cfg):
    return {'project':ctx.inputs['ue_project']['project'],'report':cfg['report'],'_files':[cfg['report']]}

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--from-run',type=Path,required=True);p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--scene-report',type=Path,required=True);p.add_argument('--until');p.add_argument('--replay',action='store_true')
    p.add_argument('--title',help='Optional content title for the isolated upgrade')
    p.add_argument('--review-geometry-audit',type=Path,action='append',default=[])
    p.add_argument('--with-dataset',action='store_true');p.add_argument('--dataset-frames',type=int,default=360)
    p.add_argument('--profile',choices=['world_demo','arena_demo']);p.add_argument('--capture-frames',type=int,default=360)
    p.add_argument('--machine',type=Path,default=ROOT/'machine.local.json')
    a=p.parse_args(argv);base=a.from_run.resolve();run=a.run_dir.resolve()
    if run==base or base in run.parents:raise ValueError('Upgrade must use an independent sibling run')
    release=read_json(base/'release.json');parent=read_json(base/'run_summary.json')['nodes']
    spec_base=base;visited=set()
    while not (spec_base/'game_spec.json').is_file():
        if spec_base in visited:raise StageError('Cyclic upgrade provenance')
        visited.add(spec_base)
        if not (spec_base/'upgrade.json').is_file():raise StageError('Accepted parent has no recoverable game spec')
        spec_base=Path(read_json(spec_base/'upgrade.json')['parent'])
    spec=read_json(spec_base/'game_spec.json')
    if a.title:spec['title']=a.title
    if not read_json(release['validation'])['passed'] or not read_json(release['review']).get('approved'):raise StageError('Parent release is not accepted')
    machine=mount(read_json(a.machine));machine['budgets']['llm_calls']=max(8,machine.get('budgets',{}).get('llm_calls',0))
    from game_pipeline import workflow,planning_agents,production_capture,camera_validation
    if a.profile:
        spec=workflow.configure(spec,a.profile,a.capture_frames,source_policy='provided')
        source_spec=a.scene_report.resolve().parent/'scene_spec.json'
        if not source_spec.is_file():
            job=a.scene_report.resolve().parent.parent/'job.json'
            if job.is_file():source_spec=Path(read_json(job)['scene_spec'])
        if not source_spec.is_file():raise StageError('Project variants require the source scene_spec.json alongside the scene report or in its job')
        scene_data=read_json(source_spec)
        spec.update({k:scene_data[k] for k in ['scene','spawns','lighting']})
        from game_pipeline.contracts import validate_spec
        validate_spec(spec)
        if a.profile=='world_demo':planning_agents.validate_exploration(scene_data,machine)
    run.mkdir(parents=True,exist_ok=True)
    write_json(run/'game_spec.json',spec)
    write_json(run/'upgrade.json',{'parent':str(base),'parent_release_sha256':digest(base/'release.json'),'scene_report':str(a.scene_report.resolve()),'runtime_contract':('integrated production' if a.profile else 'structural whitebox pairs'),'spec_source':str(spec_base/'game_spec.json'),'production':spec.get('production')})
    nodes=[]
    def add(name,result,files,rig=False):
        files=list(map(str,files));nodes.append(Node(name,'upgrade.inherited',{'result':result,'files':files,'hashes':{f:digest(f) for f in files},'parent_release':str(base/'release.json'),'rig':rig,'_source_files':files}))
    add('concept',parent['concept'],[parent['concept']['image']])
    if a.profile:
        nodes.append(Node('art_plan','agent.art_plan',{'mode':'audit_existing','brief':spec['prompt'],'art_direction':spec['art_direction'],'scene':spec['scene'],'production':spec['production']},['concept']))
        add('scene_layout',{'scene_spec':str(source_spec)},[source_spec])
        nodes.append(Node('exploration_plan','agent.exploration_plan',{'required':a.profile=='world_demo','layout_config':{}},['scene_layout','concept','art_plan']))
    for role in ['player','boss']:
        r=parent['rig_'+role];report=read_json(r['report']);files=[r['report'],r['fbx']]+[p['image'] for p in report.get('deformation',{}).get('pose_tests',[])]
        add('rig_'+role,r,files,True)
    s=read_json(a.scene_report);add('scene',{'report':str(a.scene_report.resolve())},[a.scene_report]+[e['file'] for e in s['environment']]+([s['whitebox']['file'],s['whitebox']['manifest']] if s.get('whitebox') else []))
    nodes.append(Node('ue_project','upgrade.runtime',{'parent_project':release['project'],'_source_files':[release['project']]+[str(f) for f in (ROOT/'templates/Source').rglob('*') if f.is_file()],'_implementation_files':['templates/Source','upgrade_demo.py:runtime']}))
    nodes.append(Node('animations','upgrade.animation_reuse',{'report':parent['animations']['report'],'_source_files':[parent['animations']['report']]},['ue_project']))
    nodes.append(Node('ue_assemble','ue.assemble',{'title':spec['title'],'gameplay':spec['gameplay'],'characters_config':{r:{'name':c['name']} for r,c in spec['characters'].items()},'lighting_overrides':spec.get('lighting_overrides',{}),'_source_files':[p for t in machine['texture_library'].values() for p in t.values()]},['animations','scene']))
    nodes.append(Node('playtest','ue.playtest',{'full':True},['ue_assemble']))
    if a.with_dataset:nodes.append(Node('dataset','ue.dataset',{'cameras':['first','third','isometric'],'frames':a.dataset_frames,'width':640,'height':360,'autoplay':True,'whitebox':bool(s.get('whitebox'))},['ue_assemble','playtest']))
    accepted_views=read_json(release['validation']).get('view_groups',{})
    # An exploration revision needs the accepted route views as well as its court.
    # Comparing a sparse ridge only with the densely built arena misstates the baseline.
    benchmarks=list(dict.fromkeys(accepted_views.get('overview',[])+accepted_views.get('roam_third',[])+accepted_views.get('roam_isometric',[])[::2]))
    review={'visual_agent':True,'quality_benchmarks':benchmarks,'_source_files':benchmarks}
    if a.review_geometry_audit:
        audits=[str(p.resolve()) for p in a.review_geometry_audit]
        review['geometry_audits']=audits;review['_source_files']=benchmarks+audits
    previous=spec.get('adapters',{}).get('review',{}).get('config',{})
    for key in ['prepared_character_views','character_references']:
        if key in previous:review[key]=previous[key]
    nodes.append(Node('review','agent.review',review,['playtest','concept','scene','rig_player','rig_boss']))
    nodes.append(Node('delivery','release.playable',{},['review','playtest']+(['dataset'] if a.with_dataset else [])))
    if a.profile:
        nodes=workflow.add_acceptance(nodes,spec)
        next(n for n in nodes if n.name=='review').deps+=['art_plan','exploration_plan']
        next(n for n in nodes if n.name=='delivery').deps+=['art_plan','exploration_plan']
    workflow.save_manifest(run,nodes,spec)
    registry={**local.REGISTRY,**planning_agents.REGISTRY,**production_capture.REGISTRY,'ue.scene_preflight':scene_preflight.run,'ue.camera_validation':camera_validation.run,'upgrade.inherited':inherited,'upgrade.runtime':runtime,'upgrade.animation_reuse':animation_reuse,'ue.dataset':dataset}
    results=Engine(run,machine,registry).execute(nodes,replay=a.replay,until=a.until)
    write_json(run/'run_summary.json',{'nodes':{k:{f:v for f,v in val.items() if not f.startswith('_')} for k,val in results.items()}})
    if 'delivery' in results:shutil.copy2(results['delivery']['release'],run/'release.json')
    print('Upgrade stages complete: '+', '.join(results),flush=True)

if __name__=='__main__':main()
