"""The public play command must use the same rendering policy as capture."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from game_pipeline import cli
from game_pipeline.rendering import launch_args


class PlayRendering(unittest.TestCase):
    def test_public_cli_applies_capture_rendering_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);machine=root/'machine.json'
            machine.write_text(json.dumps({'unreal_editor':'UnrealEditor.exe'}),encoding='utf-8')
            (root/'release.json').write_text(json.dumps({'project':'Demo.uproject'}),encoding='utf-8')
            argv=['pipeline.py','--machine',str(machine),'play','--run-dir',str(root)]
            with patch('sys.argv',argv),patch.object(cli.subprocess,'Popen') as start:
                self.assertEqual(cli.main(),0)
            command=start.call_args.args[0]
            self.assertEqual(Path(command[0]),(root/'UnrealEditor.exe').resolve())
            self.assertEqual(command[1],'Demo.uproject')
            for value in launch_args():self.assertIn(value,command)
            self.assertIn('-game',command)


if __name__=='__main__':unittest.main()
