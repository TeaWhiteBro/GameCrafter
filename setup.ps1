param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
& $Python -m venv (Join-Path $PSScriptRoot '.venv')
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$pipelinePython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $pipelinePython -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 'Use Python 3.12 for the pinned release. Pass -Python with its executable path.')"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $pipelinePython -m pip install -r (Join-Path $PSScriptRoot 'requirements.lock.txt')
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Write-Output 'Dependencies installed. Run pipeline.py init with your UE and Blender paths, then pipeline.py doctor.'
