"""Audit resources actually attached to exported scene geometry, not catalog size."""
from .core import digest, read_json, write_json


def consumed_texture_sets(material):
    family=material.get('surface')
    if family=='layered_ground':
        return {x['texture_set'] for x in material.get('layers',[]) if x.get('texture_set')}
    if family in ('masonry','pbr'):
        result={material['texture_set']} if material.get('texture_set') and not material.get('textures') else set()
        if family=='masonry' and material.get('weather_texture_set'):result.add(material['weather_texture_set'])
        return result
    # Procedural metal/grass do not consume a named texture set. Scan maps are
    # embedded in the source model binding rather than the surface catalog.
    return set()


def summarize(report,machine,plan=None):
    active={entry['material'] for entry in report['environment'] if entry.get('triangles',0)>0}
    materials={name:report['materials'][name] for name in sorted(active)}
    textures=sorted(set().union(*(consumed_texture_sets(m) for m in materials.values())))
    instances=report.get('asset_instances',{})
    candidates={name:sorted(k for k,v in machine.get('mesh_library',{}).items() if v['material_id']==name)
        for name in active if any(v['material_id']==name for v in machine.get('mesh_library',{}).values())}
    planned_textures={x for region in (plan or {}).get('regions',[]) for x in region.get('textures',[])}
    planned_meshes={x for region in (plan or {}).get('regions',[]) for x in region.get('meshes',[])}
    return {
        'evidence':'Nonempty exported geometry material groups and actual Blender instance calls; visual quality still needs UE review.',
        'texture_sets':textures,'mesh_instances':instances,
        'legacy_material_candidates':candidates if not instances else {},
        'unused_material_definitions':sorted(set(report['materials'])-active),
        'material_groups':{name:{'surface':m.get('surface','constant'),'texture_sets':sorted(consumed_texture_sets(m)),
            'embedded_channels':sorted(m.get('textures',{})),
            'triangles':sum(e.get('triangles',0) for e in report['environment'] if e['material']==name)} for name,m in materials.items()},
        'planned_not_observed':{'textures':sorted(planned_textures-set(textures)),
            'meshes':sorted(planned_meshes-set(instances)) if instances else None},
        'resource_sources':{name:machine.get('asset_descriptors',{}).get(name,{'source':'machine binding; see scene job'})
            for name in textures+sorted(instances)},
    }


def write_audit(report_path,machine,out,plan_path=None):
    result=summarize(read_json(report_path),machine,read_json(plan_path) if plan_path else None)
    result['scene_report']={'path':str(report_path),'sha256':digest(report_path)}
    if plan_path:result['art_plan']={'path':str(plan_path),'sha256':digest(plan_path)}
    write_json(out,result)
    return result
