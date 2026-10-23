"""Shared, centimetre-bounded wind used by shaders and shadow-cache policy."""
import math

SWAY_X_CM = .85
SWAY_Y_CM = .55
FOLIAGE_WEIGHT = .35


def maximum_displacement_cm(surface):
    if surface not in ('foliage', 'grass','botanical'):
        return None
    # Grass weights are the normalized vertex-colour channel.
    weight = FOLIAGE_WEIGHT if surface in ('foliage','botanical') else 1.
    return math.hypot(SWAY_X_CM, SWAY_Y_CM) * weight


def configure_shadow_cache(api, component, entry, material_data):
    bound = maximum_displacement_cm(material_data.get('surface'))
    if entry.get('collision') is not False or entry.get('semantic_id') != 5 or bound is None:
        return None
    # If a later shader increases wind, return to dynamic invalidation.
    if bound > 1.1:
        return None
    behavior = api.ShadowCacheInvalidationBehavior.RIGID
    component.set_editor_property('shadow_cache_invalidation_behavior', behavior)
    installed = component.get_editor_property('shadow_cache_invalidation_behavior')
    if installed != behavior:
        raise RuntimeError('Bounded foliage shadow-cache setting did not persist')
    return {'policy': 'rigid_cache_for_small_wind', 'max_wind_displacement_cm': bound,
            'rigid_transforms_invalidate': True, 'visible_wind_retained': True,
            'approximation': 'Foliage shadows may retain a cached wind pose within the reported displacement bound; character shadows remain dynamic.'}
