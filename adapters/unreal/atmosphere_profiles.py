"""Explicit physical atmospheric scattering presets, independent of scene content."""

def install(u, component, lighting):
    profile = lighting.get('weather_profile', 'clear')
    if profile not in ('clear', 'overcast'):
        raise ValueError('Unknown weather profile')
    if profile == 'overcast':
        # Neutral aerosol scattering with a broad phase function reduces the
        # clear-sky blue gradient. Directional energy is set separately by the
        # authored lighting contract; this is not an exposure compensation.
        settings = {
            'rayleigh_scattering': u.LinearColor(.012, .012, .012, 1),
            'rayleigh_scattering_scale': .20,
            'mie_scattering': u.LinearColor(.008, .008, .008, 1),
            'mie_scattering_scale': 3.,
            'mie_anisotropy': .25,
            'other_absorption_scale': 0.,
        }
        for key, value in settings.items():
            component.set_editor_property(key, value)
    return profile
