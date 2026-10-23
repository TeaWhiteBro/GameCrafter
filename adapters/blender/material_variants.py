"""Explicit per-instance material variants reuse source geometry and provenance."""
import copy,math,re

def binding(source,variants,name):
    if name is None:return source
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,15}',name) or name not in variants:raise ValueError('Unknown or invalid material variant')
    if not source.get('materials'):raise ValueError('Material variants require explicit source slots')
    result=copy.deepcopy(source);result['material_id']+='__'+name
    for slot,patch in variants[name].items():
        if slot not in result['materials']:raise ValueError('Material variant references missing source slot')
        for key,value in patch.items():
            if key not in ['color','tint','roughness','normal_strength']:raise ValueError('Unsupported material variant parameter')
            values=value if isinstance(value,list) else [value]
            if key in ['color','tint'] and len(values)!=3:raise ValueError('Material variant color requires RGB')
            if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=(4 if key=='tint' else 1) for v in values):raise ValueError('Invalid material variant value')
        result['materials'][slot].update(patch)
    return result
