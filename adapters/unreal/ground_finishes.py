"""Bounded UE surface finishes that preserve source geometry and semantics."""
import copy,math
try:
    from .surface_wetness import validate as validate_zones
except ImportError:
    from surface_wetness import validate as validate_zones

def apply(scene,finishes,library):
    result=copy.deepcopy(scene)
    if not isinstance(finishes,dict):raise ValueError('Ground finishes must be a material mapping')
    for name,finish in finishes.items():
        material=result['materials'].get(name)
        if not material or material.get('surface') not in ['layered_ground','pbr']:raise ValueError('Ground finish requires an existing PBR ground material')
        if set(finish)!={'vertex_wear_surface','wear_zones'}:raise ValueError('Ground finish may only add wear appearance and bounded surface zones')
        layer=finish['vertex_wear_surface']
        required={'texture_set','scale_cm','paint_color','paint_detail','roughness'}
        if not isinstance(layer,dict) or set(layer)!=required:raise ValueError('Invalid wear layer fields')
        source=library.get(layer['texture_set'],{})
        if not all(source.get(k) for k in ['base','normal','roughness']):raise ValueError('Wear needs an existing matched PBR set')
        color=layer['paint_color']
        if not isinstance(color,list) or len(color)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in color):raise ValueError('Wear color must be finite linear RGB')
        for key,lo,hi in [('scale_cm',20,5000),('paint_detail',0,1),('roughness',.1,1)]:
            x=layer[key]
            if type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi:raise ValueError('Invalid wear '+key)
        validate_zones(finish['wear_zones'])
        if material['surface']=='pbr':
            if layer['texture_set']!=material.get('texture_set') or finish['wear_zones']:raise ValueError('PBR finish preserves source textures and existing vertex masks')
            prior=material.get('vertex_wear_surface',{})
            material['vertex_wear_surface']={'paint_color':list(color),'detail':layer['paint_detail'],'scale_cm':layer['scale_cm'],'roughness':layer['roughness'],'normal_strength':prior.get('normal_strength',.65)}
        else:material.update(copy.deepcopy(finish))
    return result
