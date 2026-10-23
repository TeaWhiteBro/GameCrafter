"""Add capture assets and explicit annotations to a private upgraded project."""
import unreal as u,json,os,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import semantics
job=json.loads(Path(os.environ['GAME_PIPELINE_JOB']).read_text(encoding='utf-8'))
result={'ok':False}
try:
    level=u.get_editor_subsystem(u.LevelEditorSubsystem);level.load_level('/Game/Generated/Maps/Demo')
    scene=json.loads(Path(job['scene_report']).read_text(encoding='utf-8'))
    spec=json.loads(Path(job['scene_spec']).read_text(encoding='utf-8'))['scene']
    counts={}
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        label=actor.get_actor_label()
        if label.startswith('Environment '):
            entry=scene['environment'][int(label.split()[-1])];name=entry['material']
            identity=semantics.class_for_material(name,scene['materials'][name],spec['floor_material'],spec['path_material'])
            semantics.tag(actor,identity);counts[str(identity)]=counts.get(str(identity),0)+1
            component=actor.static_mesh_component
            if component.static_mesh.get_editor_property('nanite_settings').enabled:
                for material in component.get_materials():
                    u.MaterialEditingLibrary.set_material_usage(material,u.MaterialUsage.MATUSAGE_NANITE)
                    u.EditorAssetLibrary.save_loaded_asset(material)
        elif isinstance(actor,u.StaticMeshActor) and not actor.is_hidden_ed():
            # Invisible gameplay boundary actors are excluded by the capture runtime.
            if not label.startswith('Play bounds '):raise ValueError('Unclassified visible static actor '+label)
    semantics.material();level.save_current_level();result.update(ok=True,classes=semantics.CLASSES,groups=counts)
except Exception:result['error']=traceback.format_exc();print(result['error'])
Path(job['out']).write_text(json.dumps(result,indent=2),encoding='utf-8')
print('CAPTURE_SETUP',result['ok'])
