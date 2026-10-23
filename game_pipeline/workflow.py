"""Versioned production policy, shared by fresh runs and isolated upgrades."""
import copy
from . import __version__
from .core import Node, StageError, write_json

CAMERAS = ['first', 'third', 'isometric']
CHANNELS = ['rgb', 'depth', 'semantics', 'skeleton', 'whitebox']
SUPPORTED_VERSIONS = (__version__,)

def configure(spec, profile='world_demo', frames=360, source_policy='fresh'):
    if profile not in ['world_demo', 'arena_demo']:
        raise ValueError('Unknown production profile: ' + profile)
    spec = copy.deepcopy(spec)
    from .quality_standard import default_benchmarks
    if 'quality_benchmarks' not in spec:spec['quality_benchmarks']=default_benchmarks()
    if source_policy not in ('fresh', 'provided'):
        raise ValueError('Source policy must be fresh or provided')
    spec['production'] = {'version': __version__, 'profile': profile, 'art_planning_scope':'resource_intent_v1',
                          'source_policy': source_policy}
    if source_policy == 'fresh':
        spec.setdefault('surface_assets', {'provider':'polyhaven', 'max_materials':6, 'resolution':'1k'})
    spec.setdefault('environment_assets',{'enabled':True,'max_new_assets':3})
    spec['dataset'] = {'enabled': True, 'cameras': CAMERAS.copy(), 'channels': CHANNELS.copy(),
        'frames': frames, 'width': 640, 'height': 360, 'whitebox': True,
        'activities': ['combat', 'exploration'] if profile == 'world_demo' else ['combat'],
        'autoplay': True, 'videos': True, 'visibility_policy':'all_activities_v1'}
    validate(spec)
    return spec

def validate(spec):
    policy = spec.get('production')
    if not policy:
        return None  # Explicit custom specifications may omit the production profile.
    if policy.get('version') not in SUPPORTED_VERSIONS or policy.get('profile') not in ['world_demo','arena_demo']:
        raise ValueError('Unsupported production version/profile; configure the current contract explicitly')
    if policy.get('source_policy', 'provided') not in ('fresh', 'provided'):
        raise ValueError('Unsupported source policy')
    if policy.get('art_planning_scope','legacy_scene') not in ['legacy_scene','resource_intent_v1']:
        raise ValueError('Unknown art planning scope')
    data = spec.get('dataset', {})
    if data.get('enabled') is not True or data.get('whitebox') is not True:
        raise ValueError('Production requires paired datasets including structural whitebox')
    if sorted(data.get('cameras', [])) != sorted(CAMERAS):
        raise ValueError('Production requires each of the three camera modes exactly once')
    if sorted(data.get('channels', [])) != sorted(CHANNELS):
        raise ValueError('Production requires RGB, metric depth, semantic IDs, skeleton and whitebox')
    if data.get('visibility_policy')!='all_activities_v1':
        raise ValueError('Production requires subject visibility across gameplay conditions')
    expected = ['combat','exploration'] if policy['profile']=='world_demo' else ['combat']
    if sorted(data.get('activities', [])) != sorted(expected):
        raise ValueError('Capture activities must cover the selected gameplay profile')
    if type(data.get('frames')) is not int or not 60 <= data['frames'] <= 1200:
        raise ValueError('Production active clips must contain 60-1200 frames; compose longer datasets from episodes')
    if any(type(data.get(k)) is not int or not 64 <= data[k] <= 4096 or data[k] % 2 for k in ['width','height']):
        raise ValueError('Capture resolution must use even integer dimensions within 64-4096')
    if data.get('autoplay') is not True or data.get('videos') is not True:
        raise ValueError('Production acceptance needs active sequences and verified viewing exports')
    if spec.get('full_playtest',True) is not True or spec.get('review_agent',True) is not True:
        raise ValueError('Production may not bypass full gameplay or visual review')
    return policy

def add_acceptance(nodes, spec):
    """Use one acceptance DAG for both initial production and accepted-artifact upgrades."""
    policy = validate(spec)
    if not policy:
        return nodes
    nodes = [n for n in nodes if n.name != 'dataset']
    review = next(n for n in nodes if n.name == 'review')
    delivery = next(n for n in nodes if n.name == 'delivery')
    playtest = next(n for n in nodes if n.name == 'playtest')
    benchmarks = review.config.get('quality_benchmarks',[])
    nodes.insert(nodes.index(playtest),Node('scene_preflight','ue.scene_preflight',
        {'quality_benchmarks':benchmarks,'_source_files':benchmarks,'original_user_brief':spec.get('prompt','')},['ue_assemble','scene','concept']))
    preflight=next(n for n in nodes if n.name=='scene_preflight')
    preflight.config['convergence_policy']='evidence_bound_v1'
    if spec.get('repair_plan'):
        preflight.config['repair_plan']=spec['repair_plan']
        preflight.config['_source_files']=list(benchmarks)+[spec['repair_plan']]
    playtest.deps.append('scene_preflight')
    # Probe every requested condition before expensive gameplay QA.
    nodes.insert(nodes.index(playtest),Node('capture_probe','ue.capture_probe',
        {**spec['dataset'],'probe_scope':'all_requested'},['ue_assemble','scene_preflight']))
    playtest.deps.append('capture_probe')
    index = nodes.index(review)
    additions = [
        Node('camera_validation','ue.camera_validation',{},['ue_assemble','playtest']),
        Node('capture_plan','agent.capture_plan',spec['dataset'],['ue_assemble','playtest','camera_validation']),
        Node('calibration','ue.calibration',{},['ue_assemble','capture_plan']),
        Node('dataset','ue.dataset_paired',{},['ue_assemble','capture_plan','calibration']),
        Node('pair_validation','dataset.validate_pairs',{},['ue_assemble','capture_plan','calibration','dataset']),
    ]
    next(n for n in additions if n.name=='dataset').deps.append('capture_probe')
    nodes[index:index] = additions
    review.deps += ['camera_validation','pair_validation','scene_preflight']
    review.config['production_version'] = policy['version']
    delivery.deps = list(dict.fromkeys(delivery.deps + ['scene_preflight','camera_validation','capture_plan','calibration','dataset','pair_validation']))
    delivery.config['production'] = policy
    delivery.config['required_channels'] = CHANNELS
    delivery.deps.append('capture_probe')
    return nodes

def save_manifest(root, nodes, spec):
    write_json(root / 'pipeline_manifest.json', {'pipeline_version':__version__,
        'production':spec.get('production', {'profile':'custom_explicit'}),
        'asset_policy':'New runs may generate different assets; receipts track provenance and resume only.',
        'stages':[{'name':n.name,'adapter':n.adapter,'dependencies':n.deps,
                   'implementation_files':n.config.get('_implementation_files',[])} for n in nodes]})
