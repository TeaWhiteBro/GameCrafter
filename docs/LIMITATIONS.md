# Scope and limitations

- The built-in rig supports upright humanoids with resolvable, separated limbs. Fused or incomplete anatomy can require source repair or a newly authorized generation. Existing skins still need evaluated deformation checks.
- Gameplay is single-player melee against one Boss and free exploration. Driving, multiplayer, inventory and quests are not default mechanics.
- Fourteen installed compatible UE motions are retargeted; this is not a trained motion-generation service. First person hides the owner body; dedicated arms are not authored.
- Configurable construction, generated props, PBR and Lumen support varied worlds. They do not guarantee commercial AAA quality or arbitrary prompts succeeding without executing-agent intervention.
- The built-in output is an editable UE project and editor-dependent launcher. Standalone cooking/packaging is an extension. Native adapters target Windows.
- Five-channel capture supports opaque/masked surfaces and an explicit opaque-surface-behind-thin-glass observation policy. Refractive transparency and unknown semantic IDs are unsupported.
- Exact pairing applies within a capture. Separate camera runs may have small motion differences. Structural whitebox shares camera/time but has simplified silhouette boundaries.
- Full-route traversal and short captured intervals establish different coverage. Exploration visibility thresholds are minimum sentinels, not exhaustive perceptual scores or all-state coverage.
- Fixed 60 Hz data simulation is not real-time 60 FPS. GPU readback/export throughput and play performance are measured separately. No universal cost or completion-time guarantee is claimed.
- Source tests, clean export and local setup checks do not establish a new clean-machine full native game acceptance. Account access, native compilation, GPU rendering and launch observation remain required.

See [REPRODUCING.md](REPRODUCING.md), [QUALITY_GATES.md](../QUALITY_GATES.md) and [DATASET.md](../DATASET.md).
