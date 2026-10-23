"""UE commandlet: alter bounded lens defaults, with a native state invariant."""
import hashlib
import json
import os
from pathlib import Path
import unreal as u

job = json.loads(Path(os.environ['GAMECRAFTER_CAMERA_JOB']).read_text(encoding='utf-8'))
le = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert le.load_level('/Game/Generated/Maps/Demo')
actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()


def stable(v):
    if v is None or isinstance(v, (str, bool, int, float)):return v
    if isinstance(v, u.Vector):return [v.x, v.y, v.z]
    if isinstance(v, u.Rotator):return [v.pitch, v.yaw, v.roll]
    if isinstance(v, (u.Color, u.LinearColor)):return [v.r, v.g, v.b, v.a]
    if hasattr(v, 'get_path_name'):return v.get_path_name()
    raise TypeError('Unsupported native state type: '+type(v).__name__)


def signature():
    rows = []
    for a in actors:
        row = [a.get_name(), a.get_class().get_path_name(), stable(a.get_actor_location()),
               stable(a.get_actor_rotation()), stable(a.get_actor_scale3d()),
               stable(a.get_editor_property('hidden'))]
        for c in a.get_components_by_class(u.ActorComponent):
            state = [c.get_name(), c.get_class().get_path_name()]
            for key in ('relative_location', 'relative_rotation', 'relative_scale3d', 'visible',
                        'hidden_in_game', 'static_mesh', 'skeletal_mesh_asset', 'cast_shadow',
                        'intensity', 'light_color', 'fog_density', 'attenuation_radius'):
                try: value=c.get_editor_property(key)
                except Exception: continue
                state.append((key, stable(value)))
            if isinstance(c, u.MeshComponent):
                state.append([c.get_material(i).get_path_name() if c.get_material(i) else None
                              for i in range(c.get_num_materials())])
            row.append(state)
        rows.append(row)
    return hashlib.sha256(json.dumps(sorted(rows), sort_keys=True).encode()).hexdigest()


before = signature()
players = [a for a in actors if a.get_class().get_path_name() == '/Script/GameDemo.GameDemoFighter'
           and not a.get_editor_property('is_boss')]
assert len(players) == 1
player = players[0]
old = {k: player.get_editor_property(k) for k in job['camera']}
for key, value in job['camera'].items(): player.set_editor_property(key, value)
actual = {k: player.get_editor_property(k) for k in job['camera']}
assert actual == job['camera'] and signature() == before
assert le.save_current_level()
Path(job['result']).write_text(json.dumps({'passed': True, 'camera_before': old,
    'camera_after': actual, 'actor_render_signature_before': before,
    'actor_render_signature_after': signature(), 'actor_count': len(actors)}, indent=2), encoding='utf-8')
