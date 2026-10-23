"""Cheap source/placement checks shared by planning and Blender submission."""
from pathlib import Path
import copy
from .core import ROOT, StageError, read_json, write_json
from .environment_semantics import validate_sources
from .asset_usage import consumed_texture_sets


def lessons(role):
    return read_json(ROOT/'config/production_rules.json')[role]


def mesh_uses(value, path='scene'):
    if path=='scene':
        value=copy.deepcopy(value)
        cfg=value.get('composition',{})
        ex=cfg.get('exploration',{})
        if ex.get('composition_version',1)>=2:
            # Version 2 uses regional palettes and rock clusters, not the
            # version-1 roadside-pair defaults retained in older specs.
            ex.pop('plant_asset',None);ex.pop('rock_asset',None)
        scatter=cfg.get('scatter',{})
        if scatter.get('plant_count',200)<=0 or cfg.get('plant_palette'):
            scatter.pop('plant_asset',None)
        if scatter.get('rock_count',50)<=0 and scatter.get('small_rock_count',75)<=0:
            scatter.pop('rock_asset',None)
        if scatter.get('formation_count',18)<=0:scatter.pop('formation_asset',None)
        if scatter.get('plant_count',200)<=0:cfg.pop('plant_palette',None)
    if isinstance(value,dict):
        for key,item in value.items():
            here=path+'.'+key
            if key in {'asset','plant_asset','rock_asset','formation_asset'} and isinstance(item,str):
                yield here,item
            elif key=='assets' and isinstance(item,list):
                for index,name in enumerate(item):
                    if isinstance(name,str):yield f'{here}[{index}]',name
            yield from mesh_uses(item,here)
    elif isinstance(value,list):
        for index,item in enumerate(value):yield from mesh_uses(item,f'{path}[{index}]')


def usage_errors(scene, machine):
    errors=[]
    for where,name in mesh_uses(scene):
        guide=machine.get('asset_descriptors',{}).get(name,{}).get('usage_guidance',{})
        contract=guide.get('placement_contract',{})
        repeated=('.objects[' not in where or where.endswith('.plant_asset'))
        if repeated and contract.get('scatter_allowed') is False:
            errors.append({'owner':'scene_layout','code':'unsuitable_scatter_representation','asset':name,'location':where,
                'message':guide.get('placement_warning','Source is not prepared for independent-instance scattering.'),
                'repair':'Use a reviewed specimen representation; suggested available alternative: '+str(guide.get('preferred_alternative','inspect and prepare the source'))})
    return errors


def validate_usage(scene,machine):
    errors=usage_errors(scene,machine)
    if errors:raise StageError('Asset placement contract failed: '+str(errors))


def evaluate(data,machine,required_generated=()):
    scene=data['scene'];uses=list(mesh_uses(scene));names=sorted({name for _,name in uses});errors=usage_errors(scene,machine)
    checks={}
    def check(name,owner,call):
        try:call();checks[name]=True
        except (ValueError,KeyError,TypeError,StageError) as exc:
            checks[name]=False;errors.append({'owner':owner,'code':name,'message':str(exc)})
    from .contracts import validate_scene_resources
    check('resource_contract','scene_layout',lambda:validate_scene_resources(scene,machine))
    check('source_semantics','asset_preparation',lambda:validate_sources(scene,machine.get('mesh_library',{})))
    if scene.get('composition'):
        from .scene_intent import validate as validate_intent
        from .local_lights import validate as validate_lights
        check('scene_intent','scene_layout',lambda:validate_intent(data))
        check('lighting_contract','scene_layout',lambda:validate_lights(data['lighting']))
    for name in sorted(set(required_generated)-set(names)):
        errors.append({'owner':'scene_layout','code':'generated_asset_unused','asset':name,
                       'message':'Required generated source has no planned placement. Fix before scene construction.'})
    paths=set();descriptors={}
    for name in names:
        binding=machine.get('mesh_library',{}).get(name,{})
        if binding.get('file'):paths.add(binding['file'])
        if binding.get('structural_proxy'):paths.add(binding['structural_proxy'])
        for material in (binding.get('materials') or {'single':binding.get('material',{})}).values():
            paths.update(material.get('textures',{}).values())
        descriptors[name]={k:machine.get('asset_descriptors',{}).get(name,{}).get(k) for k in
                           ['placement','height_m','source_geometry','usage_guidance']}
    texture_sets=set()
    for material in scene.get('materials',{}).values():
        texture_sets.update(consumed_texture_sets(material));paths.update(material.get('textures',{}).values())
    for name in texture_sets:paths.update(machine.get('texture_library',{}).get(name,{}).values())
    for path in sorted(paths):
        if not Path(path).is_file():errors.append({'owner':'asset_preparation','code':'missing_source_file','message':path})
    return {'schema_version':1,'passed':not errors,'checks':checks,'errors':errors,'mesh_uses':[{'location':p,'asset':n} for p,n in uses],
            'source_profiles':descriptors,'verified_file_count':len(paths),'texture_sets':sorted(texture_sets),
            'default_construction':{'repeated_noncolliding_meshes':'shared source geometry','export_batch_source_triangles':4000000,
                                    'ue_worker_source_triangles':machine.get('ue_import_batch_triangles',8000000)},
            'limits':'This checks source compatibility and numeric intent, not rendered composition, actual clearance, anatomy, FPS or paired data. Those gates remain mandatory.'}


def require_ready(data,machine,out,required_generated=()):
    result=evaluate(data,machine,required_generated);write_json(out,result)
    if not result['passed']:
        raise StageError('Production readiness failed before Blender: '+str(out)+'; '+str(result['errors']))
    return result
