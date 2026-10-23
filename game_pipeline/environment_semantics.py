"""Reject missing source semantics before importing a populated DCC scene."""

CLASSES = {'terrain', 'paving', 'architecture', 'rock', 'vegetation', 'prop'}

def validate_sources(scene, library):
    names = set()
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'asset', 'plant_asset', 'rock_asset', 'formation_asset'} and isinstance(item, str):
                    names.add(item)
                elif key == 'assets' and isinstance(item, list):
                    names.update(v for v in item if isinstance(v, str))
                visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit(scene)
    for name in sorted(names):
        if name not in library: raise ValueError('Unavailable source mesh: ' + name)
        binding = library[name]
        materials = binding.get('materials') or {'single': binding.get('material', {})}
        for slot, material in materials.items():
            if material.get('semantic_class') not in CLASSES:
                raise ValueError('Source mesh ' + name + ', slot ' + str(slot) + ': explicit valid semantic_class is required before Blender import')
    return sorted(names)
