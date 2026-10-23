"""FBX may reorder materials when several meshes share one imported skin."""
def material_index(imported_name, slot_name, source_materials):
    def normalized(name):
        return ''.join(c for c in str(name).removeprefix('Material::').casefold() if c.isalnum())
    candidates={normalized(imported_name),normalized(slot_name)}-{''}
    matches=[i for i,mat in enumerate(source_materials) if normalized(mat['name']) in candidates]
    if len(matches)!=1:
        raise ValueError('Cannot uniquely match imported material slot '+repr(str(imported_name))+' / '+repr(str(slot_name))+' to source materials '+repr([m['name'] for m in source_materials]))
    return matches[0]
