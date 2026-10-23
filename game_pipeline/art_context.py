"""Resource-planning input excludes local layout/grounding adjustments."""
import copy
from collections import Counter

def resource_intent(scene):
    composition=scene.get('composition',{});exploration=composition.get('exploration',{})
    materials=copy.deepcopy(scene.get('materials',{}))
    destinations=[]
    for item in composition.get('destination_details',[]):
        destinations.append({k:copy.deepcopy(v) for k,v in item.items() if k=='kind' or k.endswith('_material') or k in ['material','plant_asset']})
    return {'planning_scope':'resource_intent_v1',
        'floor_material':scene.get('floor_material'),'path_material':scene.get('path_material'),
        'materials':materials,'paving_style':composition.get('paving_style'),
        'architectural_vocabulary':dict(sorted(Counter(o['kind'] for o in scene.get('objects',[]) if o.get('kind')!='asset').items())),
        'authored_scan_ids':sorted({o['asset'] for o in scene.get('objects',[]) if o.get('asset')}),
        'destination_modules':destinations,
        'modular_architecture':[{k:copy.deepcopy(v) for k,v in o.items() if k=='kind' or k=='material' or k.endswith('_material')} for o in composition.get('modular_architecture',[])],
        'places':[{'role':p.get('name'),'surface':p.get('surface','stone')} for p in exploration.get('places',[])],
        'route_surfaces':sorted({r.get('surface','stone') for r in exploration.get('routes',[])}),
        'regional_palettes':[sorted({p['asset'] for p in region.get('palette',[])}) for region in exploration.get('planting_regions',[])],
        'scatter_resource_ids':{k:v for k,v in composition.get('scatter',{}).items() if k.endswith('_asset')},
        'geological_resource':composition.get('terrain_shape',{}).get('height_texture_set')}
