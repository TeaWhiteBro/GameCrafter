"""Render detail management is independent of whether foliage blocks players.

Keep source scans intact. Nanite selects current-view detail, with area
preservation for separated leaves; the structural companion stays independent.
This runs after verified static-package reuse as well as fresh mesh imports.
"""

def preservation_property(api,settings):
    # UE 5.8 replaced bPreserveArea with ENaniteShapePreservation.
    # Resolve the installed SDK instead of assuming an older Python binding.
    if hasattr(settings,'shape_preservation'):
        return 'shape_preservation',api.NaniteShapePreservation.PRESERVE_AREA
    if hasattr(settings,'preserve_area'):return 'preserve_area',True
    raise RuntimeError('Installed UE exposes no supported Nanite shape-preservation setting')

def configure(api,mesh,material,entry,save):
    if entry.get('collision') or entry.get('semantic_id')!=5 or entry.get('triangles',0)<=10000:
        return None
    settings=mesh.get_editor_property('nanite_settings')
    preservation,value=preservation_property(api,settings)
    target=api.NaniteFallbackTarget.PERCENT_TRIANGLES
    changed=(not settings.enabled or getattr(settings,preservation)!=value or settings.fallback_target!=target
             or abs(settings.fallback_percent_triangles-.03)>1e-6 or abs(settings.fallback_relative_error)>1e-6)
    api.MaterialEditingLibrary.set_material_usage(material,api.MaterialUsage.MATUSAGE_NANITE)
    save(material)
    if changed:
        settings.enabled=True
        setattr(settings,preservation,value)
        # No gameplay collision uses this fallback. Current Nanite rasterization
        # still derives from the full source geometry; keep a bounded fallback.
        settings.fallback_target=target
        settings.fallback_percent_triangles=.03
        settings.fallback_relative_error=0.
        mesh.set_editor_property('nanite_settings',settings)
        save(mesh)
    installed=mesh.get_editor_property('nanite_settings')
    if not installed.enabled or getattr(installed,preservation)!=value:
        raise RuntimeError('Noncolliding foliage Nanite settings did not persist')
    return {'material':entry['material'],'source_triangles':entry['triangles'],
            'nanite_enabled':bool(installed.enabled),'preserve_area':getattr(installed,preservation)==value,'sdk_property':preservation,
            'fallback_percent_triangles':float(installed.fallback_percent_triangles),'collision':False,'changed':changed}
