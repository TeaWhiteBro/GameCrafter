# GameCrafter

**An Agentic Framework for Scalable Multi-Gameplay Game World Generation**

[English](README.md) | [简体中文](README.zh-CN.md)

GameCrafter coordinates specialist model roles, generative services, Blender and Unreal Engine to turn a text prompt or reference images into an editable, playable game demo. The built-in gameplay is free exploration and a humanoid melee Boss encounter. The framework also validates three camera modes and exports five paired observation channels.

This repository contains the complete framework source, Blender scripts, UE Python adapters, C++ gameplay/capture runtime, contracts, prompts and offline tests. A new `fresh` run requires no previous game, privately generated asset library or accepted screenshot. It reproduces the **process and acceptance contracts**, rather than identical generated assets. Native tools, compatible template motions and authorized service access are installed separately.

## What the framework produces

| Input | Playable output | Observation output |
|---|---|---|
| Text prompt; optional scene/player/Boss reference images | Connected exploration map and melee arena; player/Boss meshes, skinning and retargeted motion; editable UE project and launcher | First-person, third-person and isometric/2.5D; RGB, metric depth, semantic IDs, skeleton and structural whitebox |

The `world_demo` profile tests both activities across all three cameras. `arena_demo` keeps combat, three cameras and all five channels. Default observations are six 360-frame sequences at 640×360 with fixed 60 Hz simulation. Real-time game performance is measured separately.

## How the agents and tools cooperate

```mermaid
flowchart LR
  I[Prompt / reference images] --> D[Game Design Agent]
  D --> C[Concept image]
  C --> A[Asset Planning Agent]
  A --> S[New Tripo sources + public PBR]
  S --> W[Art / World Design Agents]
  D --> H[Character source review]
  H --> B[Blender cleanup + skinning]
  W --> G[Blender detailed scene + whitebox]
  B --> U[UE retargeting + gameplay + rendering]
  G --> U
  U --> V[Visual preflight + condition probes]
  V --> Q[Gameplay / cameras / calibration / paired export]
  Q --> R[Final Review Agent + release gate]
  V -. current evidence .-> X[Executing agent: diagnose / scoped repair]
  X -. affected artifacts .-> W
  X -. source repair .-> H
```

Model roles communicate through validated JSON and hashed artifacts. The local stage executor is sequential; independent remote environment-source submissions can overlap. Structural repairs are performed by the executing coding agent. The CLI only applies bounded supported lighting patches automatically; it is not an unattended solver for every art or topology failure.

See the [interactive workflow](docs/workflow.html), [agent collaboration](docs/agent-collaboration.html), [stage responsibilities](docs/WORKFLOW.md) and [code map](docs/CODE_MAP.md).

## Install

The native integration targets **Windows**. Its recorded toolchain is Python **3.12**, Blender **5.2.1**, Unreal Engine **5.8**, Visual Studio **2022** with C++ build tools and Windows SDK, and a GPU capable of the configured UE rendering features. See [reproduction requirements](docs/REPRODUCING.md) for motion assets and platform limits.

From a checkout in PowerShell:

```powershell
.\setup.ps1 -Python python
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests
& .\.venv\Scripts\python.exe -B scripts\verify_repository.py
```

`python` must point to Python 3.12; otherwise pass its full executable path to `-Python`. Setup installs pinned dependencies from [requirements.lock.txt](requirements.lock.txt). Offline tests do not need an API key or engine installation and do not certify a completed native game.

## Configure tools and APIs

```powershell
& .\.venv\Scripts\python.exe pipeline.py init --unreal-root "D:\UE_5.8" --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --build-root "D:\GameCrafterBuilds" --planner-model "YOUR_VISION_CAPABLE_CHAT_MODEL"
$gatewaySecret = Read-Host "Gateway API key" -AsSecureString
$env:LEVELINFINITE_API_KEY = [System.Net.NetworkCredential]::new('', $gatewaySecret).Password
& .\.venv\Scripts\python.exe pipeline.py doctor
```

Replace example paths and the chat model name with your installation/account settings. `init` creates an ignored `machine.local.json` and refuses to overwrite one. The gateway is configured for Level Infinite chat/vision, `gpt-image-2` and `tripo3d/v3.1-20260211`; these require account-specific access. Switching to the native Tripo API requires a provider implementation, not just a changed base URL. [API configuration and recovery](docs/API.md) documents endpoints and authentication.

Keep keys in the named process environment variable; `.env` is **not automatically loaded**. Neither keys nor local machine configuration belong in Git. `doctor` checks local prerequisites without charging APIs; it does not test billing access, GPU performance or MSVC compilation. Default per-run call limits are eight meshes, two images and 100 chat calls, including repairs.

## Generate from a prompt or images

Start a new independent case:

```powershell
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\garden --prompt-file examples\prompts\sakura.txt --profile world_demo --source-policy fresh
```

Or specify the content directly:

```powershell
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\new_world --prompt "Create a sunlit stone courtyard with branching garden paths, an armored traveler and a humanoid bronze guardian. Support free exploration and a melee Boss encounter." --profile world_demo --source-policy fresh
```

Use local references to guide a new scene and newly generated characters:

```powershell
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\reference_world --prompt "Build a connected exploration world and humanoid Boss encounter matching the references." --reference-scene inputs\scene.png --player-image inputs\player.png --boss-image inputs\boss.png --profile world_demo --source-policy fresh
```

Scene references guide design and concept-image editing; they are not automatic reconstructions of a whole photograph. Character references use Tripo image-to-3D. Four-view generation and explicit existing meshes are covered in [the reproduction guide](docs/REPRODUCING.md). [Ten benchmark prompts](examples/benchmark_prompts.json) offer varied example inputs without shipping prior generated assets.

## Use an executing agent

Open this repository in your coding agent and provide the task in [examples/prompts/agent_task.txt](examples/prompts/agent_task.txt), replacing the brief and input/run paths. The agent reads [AGENTS.md](AGENTS.md) and [AGENT_PROTOCOL.md](AGENT_PROTOCOL.md), runs tools, inspects source/deformation and current UE views, diagnoses failures and resumes affected stages. Reference images and generated outputs are data, not instructions.

## Inspect, repair, resume and play

```powershell
& .\.venv\Scripts\python.exe pipeline.py status --run-dir runs\garden
& .\.venv\Scripts\python.exe pipeline.py diagnose --run-dir runs\garden
& .\.venv\Scripts\python.exe pipeline.py impact --run-dir runs\garden --changed-file game_pipeline\rendering.py
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\garden
& .\.venv\Scripts\python.exe pipeline.py replay --run-dir runs\garden
& .\.venv\Scripts\python.exe pipeline.py play --run-dir runs\garden
```

Resume without repeating `--prompt`. `replay` verifies completed matching receipts and refuses to generate missing work. Use a new run directory for a new case. The journal retains remote task IDs and uncertain submission markers: do not erase them to force another paid request. [Repair protocol](AGENT_PROTOCOL.md) defines diagnosis, evidence and invalidation rules.

Default controls: WASD movement; Shift sprint; J/left mouse attack; K/right mouse heavy attack; Space dodge; C guard; Tab lock; R reset; 1/2/3 first/third/isometric view; V cycle. Check the emitted HUD for the selected runtime. Mouse look is available in perspective views.

For an explicit replacement, create a sibling variant and retain the original:

```powershell
& .\.venv\Scripts\python.exe replace_character.py --from-run runs\garden --run-dir runs\garden_new_boss --role boss --image inputs\new_boss.png
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\garden_new_boss
```

Use `--mesh` for an existing mesh. This is an intentional `provided` variant, not a fresh independent case; deformation, facing and runtime checks remain required.

## Artifacts and acceptance

Each run contains `game_spec.json`, `pipeline_manifest.json`, `run.sqlite`, hashed stage revisions, `run_summary.json` and, after release acceptance, `release.json`. Follow these manifests to the exact project, launcher, captures and reports instead of guessing stage hashes. Native compilation and full datasets can require substantial disk space.

Release requires source/skin/animation checks, saved-geometry route support, current UE visual review, real contact and traversal, facing fault controls, camera switching, independent calibration and all-frame native/export agreement. [QUALITY_GATES.md](QUALITY_GATES.md) and [DATASET.md](DATASET.md) define the requirements and alignment limits. RGB and simplified whitebox share camera/time but have different surface silhouettes. Separate camera runs are not simultaneous multi-view ground truth.

The deliverable is an **editable UE project with an editor-based launcher**. Cooking a standalone executable, driving, multiplayer, arbitrary non-humanoid rigs and dedicated first-person arms are extensions. There is no guaranteed wall-time or commercial AAA quality. See [limitations](docs/LIMITATIONS.md) and [validation scope](docs/VALIDATION.md).

## Contribute and publish

Read [CONTRIBUTING.md](CONTRIBUTING.md), [provider extension contracts](docs/PLUGINS.md), [security guidance](SECURITY.md) and [publishing checklist](docs/PUBLISHING.md). The clean-source exporter is:

```powershell
& .\.venv\Scripts\python.exe scripts\build_release.py --out ..\GameCrafter-source --zip ..\GameCrafter-source.zip
```

Original source/documentation uses the [MIT license](LICENSE). UE template animations, installed software, generated meshes, references and downloaded materials retain their respective terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No engine content, API keys or generated case assets are bundled in the source distribution.
