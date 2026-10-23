# Paired camera and multimodal outputs

The default world profile produces six active sequences: combat and exploration in first-person, third-person and isometric/2.5D cameras. Each contains five synchronized channels. Default clips are 360 frames at 640×360; `--capture-frames` accepts 60–1200. Simulation advances at 60 Hz, independent of readback/export wall time.

| Channel | Authoritative representation | Meaning |
|---|---|---|
| RGB | PNG plus native color buffer | Camera render without HUD; capture disables temporal AA/TSR, motion blur and depth of field |
| Depth | float32 NPY plus native depth | Camera-Z depth in metres, not Euclidean ray distance or a colored preview |
| Semantics | Raw uint8 ID PNG/native IDs; lossless FFV1 video | Stable class IDs; no gamma/color interpolation of labels |
| Skeleton | JSON world joints, parent links, projections; rendered skeleton PNG | Actual post-animation bone coordinates; occlusion assistance is separate metadata |
| Whitebox | PNG/native whitebox buffer | Authored structural low-poly scene and articulated character capsules |

Each collection's `frames.jsonl` links frame ID, simulation time, camera mode, channels and joint metadata. Per-frame metadata includes camera/projection matrices, actor poses and whitebox capsule endpoints. Viewing MP4s are convenient previews, not substitutes for metric depth or integer IDs.

## Alignment

Capture runs after animation and camera updates. The channels share the same simulation step, view/projection and resolution. Whitebox geometry is built alongside the detailed scene and imported through the same basis. Its components have no normal-world collision, shadow, distance-field or indirect-light contribution; all normal passes explicitly exclude them. First-person owner visibility is respected.

Simplified whitebox surfaces have different silhouettes from detailed RGB; paired does not mean identical surface boundaries. Skeleton coordinates are animation ground truth; a visibility helper describes projected actor-surface visibility, not optical visibility of bones inside skin.

Independent calibration uses known geometry at known distances and occlusion order. It checks RGB colors/edges, projected IDs and metric depth rather than trusting a self-reprojected matrix alone. Wrong scale, offset, units and occlusion are negative controls.

## Active collection and verification

Warmup is excluded from delivered frame IDs. Opening frames must already contain real activity. Combat clips require finite participant trajectories, melee proximity, visible subjects and health loss or a hit/stagger reaction; moving off-screen bones or empty-air swings do not count. First-person sustained near-plane obstruction is screened before completing all clips and again during pair validation.

Raw reuse requires matching Content, module/map/config and rendering hashes plus camera, activity, warmup, dimensions and frame count. Each sequence commits independently. An exporter change reprocesses matching raw bytes; an uncommitted sequence is diagnostic and must be recaptured.

Pair validation reads each frame against native color/depth/ID/pose data, reconstructs skeleton rasterization, checks capsule timing and whitebox presence, and verifies all required exports. The exporter decodes the lossless label video; final validation requires its successful round-trip record, and committed file hashes protect subsequent reuse. Default sky encoding uses the engine's clear depth with preserved original stencil bytes; finite-surface IDs must not be relabelled silently.

Full-route traversal proves authored route coverage. Short data sequences sample activity; they do not claim to cover every reachable map state. Real-time performance is measured separately, using normal rendering rather than fixed-time capture throughput.

## Early full-condition coverage and immutable reuse

capture_probe captures every requested full final camera/activity job before long gameplay QA. Final collection reuses a committed export only when complete project content, job, rendering policy, exporter and every file hash match. Independent calibration and final native/export comparison remain required. Changed source requires recapture; changed exporter can reprocess verified raw bytes. Pairing is exact within a capture, not across independently executed camera runs.

Third/isometric exploration requires visible class-10 player pixels with bounded brief occlusion, verified identity and opening visibility. First-person owner hiding is intentional. Combat checks participants, proximity and actual contact. See QUALITY_GATES.md for thresholds.

For explicitly declared `thin_glass`, `opaque_surface_behind_glass_v1` is the observation policy: RGB retains non-refractive glass; metric depth and semantics refer to the first opaque surface behind it. The structural whitebox omits glass but retains frames, decks and shells. This is an explicit label policy, not a claim that glass has an opaque front-surface depth. Refractive transparency is not supported by this contract. Undefined eye-plane joint projections are masked; undefined in-front joints fail.
