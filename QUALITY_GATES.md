# Required quality gates

Every requested gate remains on the release dependency path. The executing agent records additional direct image/launcher observations after tool gates. Generic image benchmarks are optional; the written requirements below always apply.

| Layer | Required evidence | Examples that must fail |
|---|---|---|
| Source completeness | Multi-view anatomy and source bounds | Missing shins/feet, fused arms, cropped bust |
| Rig and deformation | Semantic chains, source-aware landmarks, five moving poses, stretch metrics | Invalid joint bounds, REST-only skin, unweighted points, webbing |
| Animation | 14 slots, imported material-name mapping, measured planted-foot retraction | Static clips, mismatched material slots, guessed stride from height |
| Scene readiness | Actual resources, physical units, representation/placement contracts | Sample strip scattered as whole plant, unplaced required generation, missing maps |
| Geometry | Saved-geometry route probes, supported paving, portals, structural terrain error | A wall across a route, buried floor, floating base, blocked whitebox opening |
| Art preflight | Current overview, three full routes and correctly targeted destination views | Repeated empty pads, ungrounded structures, incoherent materials, absent requested identity |
| Gameplay | Actual movement/hits/death/reset, continuous travel, hit visibility, frame-time measurement | Teleport, invisible hit frames, no actual contact |
| Facing | Travel plus evaluated torso; locked strafe and Boss tracking; valid injected error control | Ninety-degree side-facing; missing samples treated as negative-control success |
| Cameras | Default initialization, real same-session switching, 16 cases, restored visibility/projection | Default view bypasses policy, switching displacement, stale hidden body |
| Exploration | Full itinerary with real collision/damage; physical Boss return and reengagement | Only spline parameters checked; final waypoint counted as reengagement |
| Calibration | Independent known-size/distance RGB, depth, IDs and whitebox anchors | Wrong units, displaced projections, failed foreground/background occlusion |
| Data pairing | Per-frame native/export comparison and complete videos | Old bones, altered IDs, missing whitebox, only a success flag checked |
| Final review | Current normal-run images and complete acceptance artifacts | Fault-injection pictures or earlier accepted scene used as current evidence |
| Release observation | Matching replay and observed working launcher | LoadMap log alone presented as visual success |

Mesh preparation must preserve authored weights and intentional gaps. Existing skins still need real evaluated vertex motion. Source incompleteness requires source correction, not more interpolation. Imported skeletal slots match by name, never array position.

Architecture needs continuous support, legible purpose and connected transitions. Plant forms must retain gaps/branches and correct root placement. The same asset duplicated at every destination does not establish variety. Map identity is judged in actual game cameras, not solely in the concept image. Avoid particles or excess bloom as substitutes for composition.

Nanite rendering and fallback collision are independent. Collision retains sufficient detail for the visible walkable surface. Shared geometry and bounded imports reduce work without reducing coverage. Inspect streamed distant silhouettes and real frame times separately. Projection-specific AO and transient shadow warnings require current image evidence.

Whitebox terrain keeps the existing 18 cm p95 error ceiling with bounded refinement. Its camera/time pairing is exact; simplified surface silhouettes need not match RGB pixel boundaries. Dense semantics reject unknown classes and unsupported transparency. Full conditions are in [DATASET.md](DATASET.md).

Retain negative controls and prior refusals. A disputed object may require same-project elevated or source-mesh diagnostics. Additional evidence is allowed; repeated unchanged review sampling is not. Classify blockers, diagnostic uncertainty and optional polish separately.

## Early full-condition checks

Every requested complete camera/activity sequence passes capture_probe before long gameplay QA. It retains the final frame count and five channels; it does not replace independent calibration, camera QA, final pairing or visual review.

Native runtime logs must not contain failed material compilation/fallback. NullRHI import success alone is insufficient. Ground checks include stair/floor ownership, excavation after additive deposits, capsule-scale whitebox proportions, and an apron that covers the camera footprint. Ambiguous dark patches require source-matched oblique and ground-level diagnosis before geometry edits.

## Condition and convergence gates

Complete all requested final clips in early capture. For third/isometric exploration, require valid visible-player identity and at least max(4, ceil(raster_pixels*0.00025)) pixels in 90% of frames; at least half of the first six frames must meet the threshold, with no occlusion span longer than twelve frames at 60 Hz. First-person owner hiding is exempt. This sentinel complements current visual review and full-map traversal; it does not prove exhaustive map-state coverage.

After three distinct environmental refusals, require a plan bound to the latest refusal and current source, with complete issue coverage and hashed evidence. Identical evidence retains its recorded decision. The executing agent resolves uncertainty before reconstruction and reruns all affected gates after repair.
