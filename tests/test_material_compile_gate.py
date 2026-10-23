import tempfile,unittest
from pathlib import Path
from game_pipeline.core import StageError
from game_pipeline.preflight_capture import check_material_compilation

class CompileGateTests(unittest.TestCase):
 def test_successful_process_with_material_fallback_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'engine.log';p.write_text('LogShaderCompilers: Warning: Failed to compile Material /Game/Generated/M_Ice for PCD3D_SM6, Default Material will be used in game.\nProcess exit code: 0')
   with self.assertRaises(StageError):check_material_compilation(p)
 def test_optional_sdk_warning_is_not_a_shader_failure(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'engine.log';p.write_text('Failed to SetupSDK for platform Android\nShaders compiled successfully')
   check_material_compilation(p)
