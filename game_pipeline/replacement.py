"""Prepare an isolated character replacement, retaining verified ancestor artifacts."""
import copy
import shutil
import sqlite3
from pathlib import Path
from .core import Engine, RunLock, StageError, digest, fingerprint, now, read_json, write_json
from .contracts import load_spec, validate_spec


def character_with_source(old, source, name=None, height=None):
    new={k:copy.deepcopy(old[k]) for k in ('morphology','height_m','triangle_budget','render_qa') if k in old}
    new['name']=name or old.get('name','Character')
    if height is not None:new['height_m']=height
    new['source']=copy.deepcopy(source)
    return new


def environment_signature(spec):
    return fingerprint({k:spec.get(k) for k in ('scene','lighting','lighting_overrides','layout_seed','concept')})


def baseline_context(ctx,cfg):
    path=cfg.get('replacement_baseline')
    if not path:return None
    baseline=read_json(path)
    if not read_json(baseline['base_release']['review']).get('approved'):
        raise StageError('Replacement baseline has no accepted release')
    if baseline['environment_signature']!=environment_signature(read_json(ctx.root/'game_spec.json')):
        raise StageError('Environment changed; a character-only baseline review is not applicable')
    if baseline['scene_report_sha256']!=digest(ctx.inputs['scene']['report']):
        raise StageError('Environment geometry report differs from accepted replacement baseline')
    return {'scope':'character replacement in an accepted environment','preserved_environment_verified':True,
            'base_run':baseline['base_run'],'role':baseline['role']}


def prepare_replacement(source_run, target_run, machine, role, asset, *, image=False,
                        name=None, height=None, references=()):
    from .cli import graph
    source_run, target_run, asset = map(lambda p: Path(p).resolve(), (source_run, target_run, asset))
    if role not in ('player', 'boss'):
        raise StageError('Replacement role must be player or boss.')
    if source_run == target_run or source_run in target_run.parents or target_run in source_run.parents:
        raise StageError('Replacement needs a separate sibling run directory.')
    if target_run.exists():
        raise StageError('Target run already exists; resume it with pipeline.py run instead.')
    if not asset.is_file() or any(not Path(p).is_file() for p in references):
        raise StageError('Replacement asset or reference file is missing.')
    if image:
        from PIL import Image
        with Image.open(asset) as im:
            im.verify()
    with RunLock(source_run/'.run.lock'):
        release=read_json(source_run/'release.json')
        if not read_json(release['review']).get('approved') or not read_json(release['validation']).get('passed'):
            raise StageError('Replacement base must be a released, accepted run.')
        spec=load_spec(source_run/'game_spec.json')
        old=spec['characters'][role]
        # Every measurement and skin decision belongs to the old source mesh.
        # Preserve only high-level role settings, never landmarks or bone maps.
        source={'provider':'tripo','mode':'image','image':str(asset)} if image else {'provider':'local','path':str(asset)}
        new=character_with_source(old,source,name=name or role.title(),height=height)
        spec['characters'][role]=new
        for stage in ['mesh_'+role,'rig_'+role]:
            override=spec.get('adapters',{}).get(stage)
            if override and override['adapter']=='artifact.inherit':spec['adapters'].pop(stage)
            elif override and stage=='rig_'+role:raise StageError('Custom rig adapter: explicitly migrate its per-asset settings before replacement.')
        validate_spec(spec)
        affected={'mesh_'+role}
        for node in graph(spec,machine):
            if affected.intersection(node.deps):affected.add(node.name)
        db=sqlite3.connect(source_run/'run.sqlite')
        try:
            rows=db.execute('select name,fingerprint,status,result,updated from nodes where status="complete"').fetchall()
            imports=[]
            for row in rows:
                if row[0] in affected or row[0]=='design':continue
                result=__import__('json').loads(row[3])
                if not result.get('_artifacts') or any(not Path(p).is_file() or digest(p)!=sha for p,sha in result['_artifacts'].items()):
                    raise StageError('Base artifact changed: '+row[0]+'. Repair the base before replacement.')
                imports.append(row)
            implementations=dict(db.execute('select name,digest from implementations'))
        finally:db.close()
        if spec.get('production') or (source_run/'upgrade.json').is_file():
            untouched={'concept','art_plan','scene_layout','exploration_plan','scene','mesh_'+('player' if role=='boss' else 'boss'),'rig_'+('player' if role=='boss' else 'boss')}
            for row in imports:
                if row[0] not in untouched:continue
                result=__import__('json').loads(row[3]);artifacts=result.pop('_artifacts')
                spec.setdefault('adapters',{})[row[0]]={'adapter':'artifact.inherit','config':{'result':result,'artifacts':artifacts,
                    '_source_files':list(artifacts),'parent_run':str(source_run),'rig':row[0].startswith('rig_')}}
        target_run.mkdir(parents=True)
        inputs=target_run/'inputs';inputs.mkdir()
        destination=inputs/('source'+asset.suffix.lower());shutil.copy2(asset,destination)
        new['source']['image' if image else 'path']=str(destination)
        refs=[]
        for i,p in enumerate(references):
            p=Path(p);dest=inputs/f'reference_{i:02d}{p.suffix.lower()}'
            shutil.copy2(p,dest);refs.append(str(dest))
        if image and not refs:refs=[str(destination)]
        review=spec.setdefault('adapters',{}).setdefault('review',{'adapter':'agent.review','config':{}})
        config=review.setdefault('config',{})
        base_test=read_json(release['validation'])
        views=base_test.get('view_groups',{})
        config['quality_benchmarks']=views.get('combat',[])[:1]+views.get('overview',[])[:1]
        config['replacement_baseline']=str(target_run/'replacement.json')
        config.setdefault('_source_files',[]).extend([config['replacement_baseline'],release['review']]+config['quality_benchmarks'])
        if refs:
            config.setdefault('character_references',{})[role]=refs
            config.setdefault('_source_files',[]).extend(refs)
        if spec.get('production'):spec['production']['source_policy']='provided'
        write_json(target_run/'game_spec.json',spec)
        engine=Engine(target_run,machine,{})
        try:
            with RunLock(target_run/'.run.lock'):
                engine.db.executemany('insert into nodes values(?,?,?,?,?)',imports)
                for row in imports:
                    if row[0] in implementations:engine.db.execute('insert into implementations values(?,?)',(row[0],implementations[row[0]]))
                provenance={'created':now(),'base_run':str(source_run),'base_release':release,'role':role,
                            'environment_signature':environment_signature(spec),
                            'scene_report_sha256':digest(__import__('json').loads(next(row[3] for row in imports if row[0]=='scene'))['report']),
                            'source_sha256':digest(destination),'generation_mode':'single_image' if image else 'local',
                            'references':refs,'reused_stages':[r[0] for r in imports],'rebuild_stages':sorted(affected),
                            'cleared_source_fields':sorted(set(old)-set(new)),
                            'note':'Inherited artifacts remain in the base run. Runtime projects are copied by downstream adapters; budgets count only new requests.'}
                engine.db.execute('insert into events(ts,node,event,detail) values(?,?,?,?)',(now(),'replacement','inherit_artifacts',__import__('json').dumps(provenance)))
                engine.db.commit();write_json(target_run/'replacement.json',provenance)
        finally:engine.db.close()
    return spec
