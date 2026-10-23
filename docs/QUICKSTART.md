# Quickstart

## 1. Install the toolchain

Use Windows, Python 3.12, Blender 5.2.1 and UE 5.8. Install Visual Studio 2022 with Desktop/Game development with C++, MSVC and a supported Windows SDK. In the UE installation options, include Templates and Feature Packs. Keep ample disk space: generated models, independent UE project copies and raw five-channel sequences can be large.

The default motion provider expects the engine's `Templates/TemplateResources/High/Characters/Content/Mannequins` resources. `doctor` checks the source mesh and all 14 motion files individually. If your distribution omits them, install those resources or create a Third Person project with the Combat variant and supply a complete compatible `Content/Characters` folder. Merely having an empty animation directory is insufficient.

## 2. Configure a clean checkout

```powershell
.\setup.ps1
& .\.venv\Scripts\python.exe pipeline.py init --unreal-root "D:\UE_5.8" --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --planner-model "YOUR_VISION_CAPABLE_CHAT_MODEL"
$env:LEVELINFINITE_API_KEY = "YOUR_GATEWAY_KEY"
& .\.venv\Scripts\python.exe pipeline.py doctor
```

Paths shown are examples. `init` records your actual paths. Relative tool/build paths in the machine config resolve relative to that file. Keep `machine.local.json` and keys out of Git. Set `gateway.planner_model` to a model available through your gateway that supports image input and JSON output. The default named model is an example of the tested deployment, not a promise of account entitlement.

The default budget is eight mesh submissions, two image submissions and 100 chat calls **per run**, including repair attempts. These are limits, not prepaid work or exact cost estimates. Increase a limit deliberately if a preserved run reaches it. Concept/image submissions with uncertain outcomes are not automatically retried.

## 3. Choose an input

Text only:

```powershell
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\garden --prompt-file examples\prompts\sakura.txt
```

Reference scene and new reference-derived Boss:

```powershell
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\reference_case --prompt "Build a coherent exploration map and a humanoid Boss encounter matching the references." --reference-scene inputs\scene.png --boss-image inputs\boss.png
```

A reference scene informs planning and the `gpt-image-2` edit request. It is not silently treated as 3D geometry. `--player-image` and `--boss-image` are single-image Tripo requests; use `source.mode: multiview` with `front`, `left`, `back`, `right` in a trusted spec for four-view generation. Keep references local and use absolute paths in hand-authored specs.

Existing mesh inputs are explicit:

1. Copy `examples/local_assets.spec.json` and fill in the actual absolute concept/mesh paths and intended content.
2. Run `pipeline.py run --run-dir runs\provided_case --spec inputs\provided.spec.json --profile world_demo --source-policy provided`.
3. Source, deformation, orientation, gameplay and data acceptance still apply.

For a compact combat-only demo, specify `--profile arena_demo`. This removes exploration construction/capture; it retains the three cameras, five channels and other acceptance requirements.

## 4. Plan, inspect and resume

`pipeline.py plan --run-dir runs\new_case --prompt "..."` calls the design model, validates a spec and writes the DAG manifest. It is not an offline dry run. Supplying an existing `--spec` instead avoids that design call. Planning does not certify source assets or final quality.

`pipeline.py run --run-dir runs\new_case --until scene_preflight` runs through current UE art preflight before the full suite. To continue after that or after an agent repair:

```powershell
& .\.venv\Scripts\python.exe pipeline.py status --run-dir runs\new_case
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\new_case
& .\.venv\Scripts\python.exe pipeline.py timing --run-dir runs\new_case --out reports\new_case
```

Use a fresh directory for a different case; repeating a prompt against an established spec is rejected. A normal resume verifies existing artifact hashes and reruns invalidated consumers. `pipeline.py replay --run-dir ...` only accepts matching completed receipts and refuses to generate missing work.

## 5. Play and find outputs

After release, run `pipeline.py play --run-dir runs\new_case`. `release.json` identifies the exact UE project and launcher. Controls: WASD move; Shift sprint; mouse controls perspective view; left mouse/J attacks; right mouse/K heavy attack; Space dodge; Tab target lock; C guard; T heal; F riposte; R reset; 1 first-person; 2 third-person; 3 isometric; V cycles views. Verify the current HUD if a runtime provider changes controls.

The run contains `game_spec.json`, `pipeline_manifest.json`, `run.sqlite`, immutable stage directories, `run_summary.json` and the final `release.json`. Camera-specific collections and their `frames.jsonl` files describe the paired output. Follow artifact paths from the manifest/release instead of assuming a stage hash.

No success file substitutes for actual launch verification. Ask the executing agent to open the emitted launcher, observe a responsive game frame, switch views and record the result. A headless worker without a display must report that launcher observation remains pending.
