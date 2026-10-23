from game_pipeline.cli import main
from game_pipeline.core import StageError, log
import sys
for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
try:sys.exit(main())
except (StageError,ValueError,OSError,KeyError) as exc:
    log(type(exc).__name__+': '+str(exc));sys.exit(1)
