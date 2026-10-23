import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from adapters.unreal.foliage_wind import configure_shadow_cache, maximum_displacement_cm


class Component:
    def __init__(self): self.values = {}
    def set_editor_property(self, name, value): self.values[name] = value
    def get_editor_property(self, name): return self.values.get(name)


class WindShadowTests(unittest.TestCase):
    def test_only_bounded_noncolliding_vegetation_uses_rigid_cache(self):
        api = NS(ShadowCacheInvalidationBehavior=NS(RIGID='rigid'))
        c = Component()
        result = configure_shadow_cache(api, c, {'semantic_id': 5, 'collision': False}, {'surface': 'foliage'})
        self.assertGreater(result['max_wind_displacement_cm'], .35)
        self.assertLess(result['max_wind_displacement_cm'], .36)
        self.assertEqual(c.values['shadow_cache_invalidation_behavior'], 'rigid')
        for entry, surface in [({'semantic_id': 11, 'collision': False}, 'foliage'),
                               ({'semantic_id': 5}, 'foliage'),
                               ({'semantic_id': 5, 'collision': True}, 'foliage'),
                               ({'semantic_id': 5, 'collision': False}, 'pbr')]:
            c = Component()
            self.assertIsNone(configure_shadow_cache(api, c, entry, {'surface': surface}))
            self.assertEqual(c.values, {})

    def test_larger_shader_motion_cannot_silently_keep_cached_shadows(self):
        with patch('adapters.unreal.foliage_wind.SWAY_X_CM', 10):
            c = Component()
            self.assertIsNone(configure_shadow_cache(None, c, {'semantic_id': 5, 'collision': False}, {'surface': 'foliage'}))
            self.assertEqual(c.values, {})
        self.assertLessEqual(maximum_displacement_cm('grass'), 1.1)

    def test_rejected_sdk_assignment_fails(self):
        c = Component()
        c.get_editor_property = lambda key: 'auto'
        with self.assertRaisesRegex(RuntimeError, 'did not persist'):
            configure_shadow_cache(NS(ShadowCacheInvalidationBehavior=NS(RIGID='rigid')), c,
                                   {'semantic_id': 5, 'collision': False}, {'surface': 'grass'})
