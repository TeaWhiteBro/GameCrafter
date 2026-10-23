# Reproducing the framework

Reproduction means repeating the supported stages and acceptance contracts with new content. It does not require identical assets, camera trajectories across separate runs or a fixed completion time. Start with the commands in [README.md](../README.md).

## Native prerequisites

The built-in native path uses Windows executable paths, PowerShell, Unreal Build Tool and Visual Studio C++ compilation. Python 3.12, Blender 5.2.1, UE 5.8 and VS 2022 form the recorded environment in [toolchain.lock.json](../toolchain.lock.json). Other versions require independent validation. macOS/Linux native production is not implemented by these Windows launch/build adapters; Python source tests are a narrower capability.

Install UE Templates and Feature Packs. The motion provider reads `Templates/TemplateResources/High/Characters/Content/Mannequins`: `Meshes/SKM_Manny_Simple.uasset` and all 14 clips enumerated in `game_pipeline/machine.py`. Alternatively configure `animation_library` to a complete compatible Third Person Combat-variant `Content/Characters` directory. The directory must contain the actual mesh and required clips. Do not ship these Epic assets in this source repository.

Install VS C++ build tools and a supported Windows SDK before running UE compilation. Allocate space for meshes, independent project copies, derived data and native five-channel captures. Requirements depend on content/resolution; the framework does not impose a misleading universal minimum. Configure `build_root` on a suitable disk. `doctor` verifies file presence/dependencies and environment credentials only; a native compile and real launch remain separate gates.

## Generation services

Configure the Level Infinite gateway and an image-capable chat model supporting the expected structured responses. Set `LEVELINFINITE_API_KEY` in the same process that starts Python. Read [API.md](API.md) for image, mesh, storage and polling requests. PBR download uses public Poly Haven metadata/hosts and never receives the gateway Authorization header. Fresh runs select public resources and new generated sources; they do not mount a previous private asset catalog.

## Inputs and planning

Use `--prompt` or `--prompt-file`, with a new `--run-dir`. All example prompt files are ordinary input text; use any supported theme. `--reference-scene`, `--player-image` and `--boss-image` are optional local image paths. Character source requests can also use four views in a trusted spec:

```json
{"provider":"tripo","mode":"multiview","front":"D:/inputs/front.png","left":"D:/inputs/left.png","back":"D:/inputs/back.png","right":"D:/inputs/right.png"}
```

Confirm the exact source schema in `game_pipeline/contracts.py` and `examples/mesh_source_variants.json`. For existing geometry, copy `examples/local_assets.spec.json`, fill in absolute source/concept paths, and run:

```powershell
& .\.venv\Scripts\python.exe pipeline.py run --run-dir runs\provided_world --spec inputs\provided.spec.json --profile world_demo --source-policy provided
```

`provided` is explicit reuse, not independent fresh production. It keeps the same source, skin, facing, scene, runtime and data requirements.

`plan --prompt ...` calls the design model and writes a validated GameSpec/DAG; it is not an offline dry run. `plan --spec ...` uses the supplied specification. Planning validates intent, not actual resulting assets. `run --until scene_preflight` is a useful bounded stopping point before long gameplay/data acceptance; continue with `run --run-dir ...`.

## Agent execution and recovery

Give the coding agent [agent_task.txt](../examples/prompts/agent_task.txt). It should inspect current artifacts, operate the native tools, resolve failures at their responsible layer and resume. Consult [AGENT_PROTOCOL.md](../AGENT_PROTOCOL.md) for evidence-bound repair. The scheduler records checked stage files and remote state, not a complete autonomous reconstruction policy.

Use `status`, `diagnose` and `impact` before changing a rejected result. API uncertainty is a distinct `waiting_external` state. Recover the original provider task or saved response; do not remove paid intent markers. Local source preparation can be revised while retaining that task. The engine invalidates affected artifact consumers using configuration, dependency and implementation fingerprints.

After three distinct refused environmental preflights, complete the generated repair worklist and source-bound repair plan before another review. Use targeted oblique/ground views to settle uncertain geometry, batch related repairs and freeze optional polish when requirements pass. See [workflow responsibilities](WORKFLOW.md) and [quality gates](../QUALITY_GATES.md).

## Full acceptance checklist

1. Source views verify complete separated anatomy; deformation poses verify evaluated weights and stretching.
2. Detailed and structural scenes share physical units, terrain support, portal openings and transformations.
3. UE compilation/import succeeds, materials compile in actual rendering, and normal gameplay views retain intended composition.
4. All requested full camera/activity jobs pass early probe. Full playtest, travel/facing negative controls and same-session switching remain mandatory.
5. Independent calibration and all-frame native/export checks pass; five required channels and videos are present.
6. Final review and delivery refer to current sources. Replay verifies matching artifacts. An agent with a display observes the emitted/public launcher, responsive movement and view switching.

Do not treat an API success, compiled module, static preview or `release.json` alone as proof of every item. Record pending observations honestly. This source-distribution validation does not replace a clean-machine full native production test.
