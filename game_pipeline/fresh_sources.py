"""Separate a new production from explicitly supplied or inherited content."""
import copy
from .core import StageError


def is_fresh(spec):
    return spec.get('production', {}).get('source_policy') == 'fresh'


def machine_for_spec(machine, spec):
    result = copy.deepcopy(machine)
    if is_fresh(spec):
        result.pop('asset_catalog', None)
        for key in ('mesh_library', 'texture_library', 'asset_descriptors', 'art_kits'):
            result[key] = {}
    return result


def validate(spec):
    if not is_fresh(spec):
        return
    if spec.get('concept', {}).get('provider', 'gpt_image') != 'gpt_image':
        raise StageError('Fresh production generates its concept. Use provided policy for a local concept.')
    for role, character in spec.get('characters', {}).items():
        source = character.get('source', {})
        if source.get('provider') != 'tripo' or source.get('mode') not in ('text', 'image', 'multiview'):
            raise StageError(role + ': fresh production needs a new text/image Tripo source; use provided policy for existing assets.')
    if any(v.get('adapter') == 'artifact.inherit' for v in spec.get('adapters', {}).values()):
        raise StageError('Fresh production cannot inherit artifacts from another run.')
    if not spec.get('environment_assets', {}).get('enabled'):
        raise StageError('Fresh production requires environment demand planning and source preparation.')
    if spec.get('surface_assets', {}).get('provider') != 'polyhaven':
        raise StageError('Fresh production requires the public PBR source stage; register another provider explicitly to extend it.')
