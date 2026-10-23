import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from game_pipeline.core import ROOT, read_json
from game_pipeline.contracts import ContractError, validate_design_output
from game_pipeline.services import design


class DesignHandoffTests(unittest.TestCase):
    def seed(self):
        spec=read_json(ROOT/'examples/local_assets.spec.json')
        spec.pop('adapters',None)
        spec['scene'].pop('composition',None)
        spec['scene']['size_m']=28
        spec['scene']['objects']=[]
        spec['concept']={'provider':'gpt_image'}
        for mat in spec['scene']['materials'].values():mat['texture_set']=''
        for char in spec['characters'].values():char['source']={'provider':'tripo','mode':'text','prompt':'complete separated humanoid'}
        return spec

    def test_world_geometry_cannot_be_guessed_during_design(self):
        spec=self.seed()
        spec['scene'].update(size_m=180,composition={'exploration':{'routes':[{'points_m':[[0,0,0],[1,0,0]]}]}})
        with self.assertRaisesRegex(ContractError,'compact combat-core seed'):validate_design_output(spec)

    def test_seed_defers_scan_selection_to_installed_catalog(self):
        spec=self.seed();validate_design_output(spec)
        next(iter(spec['scene']['materials'].values()))['texture_set']='invented_soot_scan'
        with self.assertRaisesRegex(ContractError,'resource-aware'):validate_design_output(spec)

    def test_retry_preserves_world_target_and_full_original_brief(self):
        valid=self.seed();invalid=copy.deepcopy(valid)
        invalid['scene']['composition']={'exploration':{}}
        with tempfile.TemporaryDirectory() as folder:
            ctx=SimpleNamespace(directory=Path(folder),event=lambda *args:None)
            cfg={'prompt':'A branching dark world with a foundry and hill routes','production_profile':'world_demo'}
            with patch('game_pipeline.services.chat',side_effect=[invalid,valid]) as chat:
                result=design(ctx,cfg)
            self.assertEqual(chat.call_count,2)
            self.assertIn('Production target:',chat.call_args_list[1].args[2])
            self.assertIn('compact combat-core seed',chat.call_args_list[1].args[2])
            self.assertEqual(read_json(result['spec'])['prompt'],cfg['prompt'])

    def test_recoverable_schema_placement_needs_no_new_model_call(self):
        candidate=self.seed()
        for key in ['lighting','gameplay','spawns']:candidate['scene'][key]=candidate.pop(key)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'agent_response_1.txt').write_text(json.dumps(candidate),encoding='utf-8')
            ctx=SimpleNamespace(directory=root,event=lambda *args:None)
            with patch('game_pipeline.services.chat') as chat:
                result=design(ctx,{'prompt':'A new world','production_profile':'world_demo'})
            chat.assert_not_called();validate_design_output(read_json(result['spec']))

if __name__=='__main__':unittest.main()
