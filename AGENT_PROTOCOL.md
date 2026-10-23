# Agent execution protocol

Use [the complete workflow](docs/WORKFLOW.md) for stage responsibilities and [Codex instructions](docs/CODEX.md) for a ready-to-use task prompt. These are executable production obligations, not claims of a fully autonomous art solver.

## Stage contract

Input: JSON config, named dependency results, output directory and local machine config. Output: JSON result with `_files`; every listed file must exist and is hashed before completion. States are `running`, `complete`, `failed` and `waiting_external`. One OS lock protects each run. Local implementation files have scoped hashes; changes invalidate affected consumers. Source submission intent survives preparation changes.

Fresh runs clear all prior scene-asset libraries and inherited-stage routes. Generation varies between runs. Same-run recovery retains verified files and paid task IDs. Existing assets require explicit `provided` mode. Keep user models, source scales, placement semantics and characters in contracts, not code branches.

## Repair decisions

1. Read the failing stage's current config, log, artifacts and source hashes.
2. Identify source, schema, topology, geometry, import, animation, rendering, gameplay or capture as the responsible layer.
3. Check actual images/geometry before changing disputed structures. Diagnostic clay/hidden-object views cannot certify finished UE art.
4. Repair the root cause in a new artifact revision. Preserve the original refusal and explain any reversed diagnosis. Batch connected repairs.
5. Resume and rerun invalidated consumers. Never soften thresholds to obtain acceptance.

Only the bounded exposure/sky/fog patch loop is automatically applied by the CLI. Missing anatomy, fused limbs, unsupported source representations and broken composition need executing-agent decisions. An identical review reuses its recorded decision; after three failures diagnose from the worklist before rebuilding.

## Cross-software invariants

- Source anatomy determines forward after import using semantic reference bones. UE actor forward is +X, Z is up. Distinguish input projection, travel, actor orientation and evaluated torso orientation. Keep leg animation when correcting locked upper-body aim.
- A material coordinate mask is validated against actual final UE geometry at several asymmetric locations. An intermediate FBX reflection is not the final coordinate basis. Do not use the same guessed transform to construct both test and expectation.
- Single-sided authored panels retain winding. Closed-mesh normal recalculation is not valid for every sheet. Component-selection tools use world coordinates after group transforms.
- Structural companions share the authored footprint, elevations and transformations. Real clearances, terrain errors and openings must pass independently. Whitebox characters are animation-driven capsules; they never affect normal RGB or collision.
- Material planning uses observed source albedo plus matched normal/roughness maps, not names. Tint multiplies color. Functional pavement zones and physical seams must not create coplanar overlays or incompatible duplicate joint patterns.
- Projection policy applies on default startup and every switch. Orthographic AO handling must preserve perspective restoration. Destination QA anchors the actual location and checks its projection; a spring-arm offset alone may not be sufficient.
- Runtime, preview, preflight and capture share the rendering policy. Raw capture reuse requires unchanged complete Content/module/map/config hashes, camera, activity, warmup, resolution and frame count.

## Acceptance and reporting

Read QUALITY_GATES.md and DATASET.md. Real route traversal retains collision and damage; Boss disengagement means physically returning and reengaging. Negative facing tests need valid moving samples. Active data needs actual contact, visible subjects and movement from the start. Metric calibration is independent of exported matrices.

No asset count, successful API response, build, route, screenshot file or MP4 establishes final visual/data quality by itself. Check final current normal-run views, full native/export data and real launch. Preserve known transient warnings and distinguish fixed-step simulation from measured play FPS.

The node executor is sequential. Environment submissions may overlap remotely. Count execution-agent edits/diagnostics in total user wait. Do not present cache replay or inheritance as faster independent production. Keep public test claims separate from full UE integration evidence.


## Convergence and condition coverage

Before an expensive rebuild, run `pipeline.py diagnose --run-dir RUN` and `pipeline.py impact --run-dir RUN --changed-file RELATIVE_SOURCE`. These read saved evidence without executing tools or charging providers. Untracked helper changes require a dependency audit in implementation.py.

All requested complete camera/activity jobs run in capture_probe before long gameplay QA. Successful exports are immutable and reusable only when source, job, render policy, exporter and every output hash match. Final independent calibration and all-frame validation remain required. This is same-run reuse, not previous-case content inheritance.

After three distinct consecutive environmental refusals, supply spec.repair_plan using the generated worklist. Bind it to the latest refusal and current source fingerprints, cover every issue, name an owner/root cause, and include hashed targeted evidence. Confirmed repairs additionally identify changed files. Settle uncertain geometry with matching oblique and ground-level evidence before reconstruction. The plan validates repair process, never waives visual acceptance.

Record total user wall time including executing-agent diagnostics/edits. Stage windows can overlap and are not additive independent production-time measurements. No fixed completion time is guaranteed.
