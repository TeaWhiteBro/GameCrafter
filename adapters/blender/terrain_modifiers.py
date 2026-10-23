"""Apply shared terrain details before final structural/excavation constraints."""
try:
    from . import route_banks,wall_banks,surface_deposits,cart_tracks,structure_terrain,terrain_channels
except ImportError:
    import route_banks,wall_banks,surface_deposits,cart_tracks,structure_terrain,terrain_channels


def apply(cfg,field,x,y,z):
    exploration=cfg.get('exploration',{})
    if exploration.get('route_banks'):z+=route_banks.offset(exploration,field,x,y)
    if any(w.get('bank_height') for key in ['walls','terrain_banks'] for w in exploration.get(key,[])):
        z+=wall_banks.offset(exploration,field,x,y)
    if cfg.get('surface_deposits'):z+=surface_deposits.offset(cfg['surface_deposits'],x,y)
    if any(r.get('wheel_ruts') for r in exploration.get('routes',[])):z+=cart_tracks.offset(field,x,y)
    # Added surface detail may never bury authored treads or refill a riverbed.
    if cfg.get('destination_details'):z=structure_terrain.below_structures(cfg['destination_details'],x,y,z)
    if cfg.get('terrain_channels'):z=terrain_channels.bed(cfg['terrain_channels'],x,y,z)
    return z
