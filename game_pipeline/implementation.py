"""Scoped implementation receipts: a runtime fix must not resubmit paid assets."""
import ast
from .core import ROOT, digest, fingerprint

SCOPE = {
 'ue.camera_revision':['game_pipeline/camera_revision.py','adapters/unreal/revise_camera.py','game_pipeline/local_adapters.py:clone_project,project_namespace'],
 'agent.design':['game_pipeline/services.py:design,chat','game_pipeline/contracts.py:plan_instructions,validate_design_output,validate_spec,normalize_design'],
 'artifact.inherit':['game_pipeline/artifacts.py','game_pipeline/contracts.py:validate_rig'],
 'agent.art_plan':['game_pipeline/planning_agents.py:art_plan,validate_art','game_pipeline/services.py:chat','game_pipeline/catalog.py'],
 'agent.exploration_plan':['game_pipeline/planning_agents.py:exploration_plan,validate_exploration','game_pipeline/services.py:scene_layout','game_pipeline/contracts.py:validate_scene_resources'],
 'ue.camera_validation':['game_pipeline/camera_validation.py'],
 'ue.scene_preflight':['game_pipeline/scene_preflight.py','game_pipeline/services.py:chat','game_pipeline/art_criteria.py'],
 'agent.capture_plan':['game_pipeline/production_capture.py:capture_plan','game_pipeline/workflow.py'],
 'ue.calibration':['game_pipeline/production_capture.py:calibration,collect,capture_job,committed','capture_dataset.py','game_pipeline/dataset.py'],
 'ue.dataset_paired':['game_pipeline/production_capture.py:dataset,collect,capture_job,committed','capture_dataset.py','game_pipeline/dataset.py'],
 'dataset.validate_pairs':['game_pipeline/production_capture.py:validate_pairs,validate_sequence,validate_combat_visibility,validate_combat_contact','game_pipeline/dataset.py'],
 'blender.rig': ['game_pipeline/local_adapters.py:rig', 'game_pipeline/contracts.py:validate_rig,validate_landmarks', 'adapters/blender/character.py', 'adapters/blender/skin_quality.py', 'adapters/blender/inspect_character.py', 'adapters/blender/appendages.py', 'adapters/blender/heat_skin.py'],
 'blender.scene': ['game_pipeline/local_adapters.py:scene', 'adapters/blender/scene.py', 'adapters/blender/environment.py', 'adapters/blender/architecture.py', 'adapters/blender/courtyard.py', 'adapters/blender/whitebox.py', 'adapters/blender/exploration.py', 'adapters/blender/landscape_routes.py', 'adapters/blender/add_groundcover.py', 'adapters/blender/check_routes.py', 'adapters/blender/transform_parts.py', 'adapters/blender/refine_landscape.py', 'adapters/blender/surface_bedding.py', 'adapters/blender/refine_surfaces.py', 'adapters/blender/destination_details.py', 'adapters/blender/refine_destinations.py', 'adapters/blender/island_transform.py', 'adapters/blender/mesh_components.py', 'adapters/blender/route_banks.py', 'adapters/blender/refine_ravine.py', 'adapters/blender/settle_rocks.py'],
 'ue.project': ['game_pipeline/local_adapters.py:project', 'game_pipeline/runtime_cache.py', 'templates/Source'],
 'ue.animation': ['game_pipeline/local_adapters.py:animations,clone_project,run_unreal', 'adapters/unreal/assemble.py:animate,skeletal,ikrig,material,tex', 'adapters/unreal/motion_metrics.py', 'adapters/unreal/material_slots.py'],
 'ue.assemble': ['game_pipeline/local_adapters.py:assemble,normalize_texture_library,clone_project,run_unreal', 'adapters/unreal/assemble.py:assemble,static,spawn,material,tex,node,output,wire,prop,save,create', 'adapters/unreal/surfaces.py', 'adapters/unreal/semantics.py', 'adapters/unreal/whitebox.py', 'game_pipeline/static_reuse.py'],
 'ue.playtest': ['game_pipeline/local_adapters.py:playtest'],
 'ue.dataset': ['game_pipeline/capture_adapter.py','game_pipeline/dataset.py','capture_dataset.py'],
 'agent.scene_layout': ['game_pipeline/services.py:scene_layout', 'game_pipeline/contracts.py:validate_spec,validate_scene_resources,normalize_design'],
 'agent.review': ['game_pipeline/local_adapters.py:review', 'game_pipeline/services.py:chat', 'game_pipeline/replacement.py:baseline_context,environment_signature','game_pipeline/review_evidence.py','game_pipeline/art_criteria.py'],
 'release.playable': ['game_pipeline/local_adapters.py:deliver'],
}

for adapter in ['ue.calibration','ue.dataset_paired','dataset.validate_pairs','ue.dataset']:
    SCOPE[adapter].append('game_pipeline/whitebox_presence.py')

for adapter in ['ue.scene_preflight','agent.review']:
    SCOPE[adapter].append('game_pipeline/labeled_evidence.py')
    SCOPE[adapter].append('game_pipeline/review_evidence.py')

SCOPE['ue.scene_preflight'].extend(['game_pipeline/preflight_capture.py','game_pipeline/preflight_cache.py','game_pipeline/review_cycle.py'])
SCOPE['agent.review'].extend(['game_pipeline/preflight_cache.py','game_pipeline/rendering.py'])

SCOPE['blender.scene'].extend(['adapters/blender/curved_wall.py','adapters/blender/refine_curved_walls.py'])
SCOPE['blender.scene'].append('game_pipeline/asset_usage.py')
SCOPE['blender.scene'].append('adapters/blender/terrain_lod.py')
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/authored_planting.py')
SCOPE['blender.scene'].append('adapters/blender/court_exposure.py')
SCOPE['blender.scene'].append('adapters/blender/modular_paving.py')
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/court_outline.py')
SCOPE['blender.scene'].append('adapters/blender/geometry_batches.py')
SCOPE['blender.scene'].append('adapters/blender/shared_geometry.py')
SCOPE['blender.scene'].append('adapters/blender/mesh_complexity.py')
SCOPE['blender.scene'].append('game_pipeline/environment_semantics.py')
SCOPE['blender.scene'].extend(['game_pipeline/production_readiness.py','game_pipeline/scene_intent.py','game_pipeline/local_lights.py','game_pipeline/contracts.py:validate_scene_resources'])
SCOPE['blender.scene'].append('config/source_usage_guidance.json')
for adapter in ['agent.environment_demands','agent.art_plan','agent.scene_layout','agent.exploration_plan']:
    SCOPE.setdefault(adapter,[]).extend(['game_pipeline/production_readiness.py','config/production_rules.json'])
for adapter in ['ue.calibration','ue.dataset_paired','dataset.validate_pairs']:
    SCOPE[adapter].append('game_pipeline/capture_quality.py')
SCOPE['blender.scene'].append('adapters/blender/landscape_materials.py')
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/planting_footprint.py')
    SCOPE[adapter].append('adapters/blender/material_variants.py')
SCOPE['blender.scene'].append('game_pipeline/scene_geometry.py')
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/route_elevation.py')
SCOPE['blender.scene'].append('adapters/blender/generated_parts.py')
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/modular_architecture.py')
    SCOPE[adapter].append('adapters/blender/urban_frontage.py')
SCOPE['blender.scene'].append('adapters/blender/ground_support.py')
SCOPE['blender.scene'].append('adapters/blender/lodge_details.py')
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/terrain_channels.py')
SCOPE['blender.scene'].append('adapters/blender/structure_terrain.py')
SCOPE['agent.art_plan'].append('game_pipeline/art_context.py')
SCOPE['agent.art_plan'].append('game_pipeline/material_evidence.py')
SCOPE['ue.assemble'].append('adapters/unreal/practical_lights.py')
SCOPE['ue.assemble'].append('game_pipeline/lighting_contract.py')
SCOPE['ue.assemble'].append('adapters/unreal/atmosphere_profiles.py')
SCOPE['ue.assemble'].append('adapters/unreal/frozen_surface.py')
for adapter in ['blender.scene','ue.assemble','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/unreal/water_surface.py')
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/unreal/frozen_surface.py')
SCOPE['blender.scene'].append('adapters/blender/mast_footing.py')
SCOPE['ue.assemble'].extend(['game_pipeline/bounded_import.py','adapters/unreal/assemble.py:import_environment_batch'])
SCOPE['ue.assemble'].append('adapters/unreal/vegetation_rendering.py')
SCOPE['ue.assemble'].append('adapters/unreal/foliage_wind.py')
for adapter in ['ue.assemble','blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/unreal/surface_wetness.py')
SCOPE['ue.playtest'].append('game_pipeline/performance.py')
for adapter in ['agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].extend(['game_pipeline/scene_intent.py','game_pipeline/local_lights.py'])

for adapter in ['ue.playtest','ue.scene_preflight','ue.camera_validation','ue.calibration','ue.dataset_paired','dataset.validate_pairs','release.playable']:
    SCOPE[adapter].append('game_pipeline/rendering.py')
for adapter in ['agent.exploration_plan','agent.scene_layout']:
    SCOPE[adapter].append('adapters/blender/destination_details.py')
    SCOPE[adapter].append('adapters/blender/route_banks.py')
for adapter in ['blender.scene','agent.exploration_plan','agent.scene_layout']:
    SCOPE[adapter].append('adapters/blender/organic_paths.py')

SCOPE['agent.environment_demands']=['game_pipeline/environment_assets.py:demand_plan,validate_demands','game_pipeline/services.py:chat']
SCOPE['agent.environment_demands'].extend(['game_pipeline/production_readiness.py','config/production_rules.json'])
SCOPE['agent.environment_demands'].extend(['game_pipeline/catalog.py','config/source_usage_guidance.json'])
SCOPE['agent.art_plan'].append('config/source_usage_guidance.json')
SCOPE['environment.generate']=['game_pipeline/environment_assets.py:build_assets,validate_demands,asset_context,review_signature,equivalent_review_evidence,source_config','game_pipeline/implementation.py:environment_preparation_digest','game_pipeline/services.py:mesh,chat','game_pipeline/tripo_client.py','adapters/blender/prepare_environment.py']
SCOPE['blender.environment_asset']=['adapters/blender/prepare_environment.py','adapters/blender/botanical_refinement.py']
SCOPE['environment.generate'].append('adapters/blender/botanical_refinement.py')
for adapter in ['blender.environment_asset','environment.generate']:
    SCOPE[adapter].append('adapters/blender/culm_refinement.py')
    SCOPE[adapter].append('adapters/blender/static_clump.py')
    SCOPE[adapter].append('adapters/blender/texture_regions.py')
    SCOPE[adapter].append('adapters/blender/static_recipes.py')
for adapter in ['agent.art_plan','agent.scene_layout','agent.exploration_plan','blender.scene']:
    SCOPE[adapter].append('game_pipeline/environment_assets.py:with_resources,resource_result')

# Paid source stages are keyed by submission intent, not local implementation.
# Changing a downloader must not submit another image for an existing run.
SCOPE['resources.public_surfaces']=['game_pipeline/public_surfaces.py','config/public_surfaces.json']
SCOPE['agent.environment_demands'].extend(['game_pipeline/public_surfaces.py:menu,validate_selection','config/public_surfaces.json'])
for adapter in ['agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/exploration.py:RouteField')
SCOPE['ue.assemble'].append('game_pipeline/environment_assets.py:with_resources')
for adapter in ['ue.project','ue.animation','ue.assemble']:
    SCOPE[adapter].append('game_pipeline/local_adapters.py:project_namespace')

for adapter in ['agent.scene_layout','agent.exploration_plan','blender.scene']:
    SCOPE[adapter].append('adapters/blender/masonry_destinations.py')

SCOPE['blender.scene'].append('adapters/blender/walk_support.py')

def implementation_digest(adapter, extra_files=()):
    sources={}
    for entry in list(SCOPE.get(adapter, []))+list(extra_files):
        path, marker, names=entry.partition('.py:')
        if marker:path+='.py'
        else:path=entry;names=''
        p=ROOT/path
        if names:
            tree=ast.parse(p.read_text(encoding='utf-8-sig'))
            wanted=set(names.split(','))
            sources[entry]={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name in wanted}
            missing=wanted-set(sources[entry])
            if missing:raise ValueError('Missing declared implementation symbols in '+path+': '+', '.join(sorted(missing)))
        elif p.is_dir():
            sources[entry]={str(f.relative_to(p)):digest(f) for f in sorted(p.rglob('*')) if f.is_file() and '__pycache__' not in f.parts}
        else:sources[entry]=digest(p)
    return fingerprint(sources) if sources else ''

def environment_preparation_digest(asset):
    """Only active optional source operations invalidate this prepared object."""
    files=['adapters/blender/prepare_environment.py']
    for flag,module in [('botanical_refinement','botanical_refinement'),('texture_regions','texture_regions'),
                        ('roof_snow_refinement','roof_snow'),('culm_refinement','culm_refinement'),('stem_clump','static_clump'),('construction','static_recipes'),('static_cleanup','static_cleanup')]:
        if asset.get(flag):files.append('adapters/blender/'+module+'.py')
    if asset.get('construction',{}).get('recipe')=='eroded_outcrop':
        files.append('adapters/blender/geological_recipe.py')
    return fingerprint({path:digest(ROOT/path) for path in files})

for adapter in ['blender.environment_asset','environment.generate']:
    SCOPE[adapter].append('adapters/blender/geological_recipe.py')

SCOPE['environment.generate'].append('adapters/blender/roof_snow.py')
SCOPE['environment.generate'].append('adapters/blender/static_cleanup.py')

SCOPE['blender.scene'].append('adapters/blender/natural_court.py')
SCOPE['blender.scene'].append('adapters/blender/wall_banks.py')
for adapter in ['agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/wall_banks.py')

SCOPE['blender.scene'].append('adapters/blender/horizon_terrain.py')
SCOPE['blender.scene'].append('adapters/blender/surface_deposits.py')
for adapter in ['agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/surface_deposits.py')
SCOPE['ue.assemble'].append('adapters/unreal/ground_finishes.py')
SCOPE['blender.scene'].extend(['adapters/blender/arch_profiles.py','adapters/blender/cart_tracks.py'])
SCOPE['blender.scene'].append('adapters/blender/terrain_modifiers.py')
for adapter in ['agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/arch_profiles.py')

# Shared capture helpers and exporter fingerprints must invalidate every
# consumer. These scopes never invalidate a paid source submission.
SCOPE['ue.capture_probe']=list(SCOPE['dataset.validate_pairs'])+list(SCOPE['ue.dataset_paired'])
for adapter in ['agent.capture_plan','ue.capture_probe','ue.calibration','ue.dataset_paired','dataset.validate_pairs']:
    SCOPE[adapter]=[p for p in SCOPE[adapter] if not p.startswith('game_pipeline/production_capture.py:')]
    SCOPE[adapter].append('game_pipeline/production_capture.py')

# Declared opt-in interior construction and measured functional region checks.
for adapter in ['blender.scene','agent.scene_layout','agent.exploration_plan']:
    SCOPE[adapter].append('adapters/blender/pressure_habitat.py')
SCOPE['agent.exploration_plan'].append('game_pipeline/planning_agents.py:validate_composition_regions')

SCOPE['ue.scene_preflight'].append('game_pipeline/repair_contract.py')
