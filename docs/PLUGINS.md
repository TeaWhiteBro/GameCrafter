# Extending providers

This repository uses a stage adapter registry, not a dependency on a Codex plugin installation. `cli.REGISTRY` combines gateway, Blender, UE, planning and capture adapters.

```python
def my_adapter(ctx, cfg):
    # ctx.inputs: named dependency results; ctx.directory: this stage revision
    # ctx.machine: installed tools; ctx.event / spend: journal and budget
    # ctx.run: bounded subprocess with persistent logs
    result_file = ctx.directory / 'result.json'
    # Produce and validate the actual artifact here.
    return {'report': str(result_file), '_files': [result_file]}
```

Register the function and select it in a trusted GameSpec:

```json
{"adapters":{"scene":{"adapter":"my.scene","config":{"revision":"1"}}}}
```

Preserve the replaced stage's output contract. A custom rig needs FBX, semantic bones, materials and deformation evidence. A custom scene needs geometry, coordinate basis, actual collision/route acceptance and the structural whitebox. A custom animation provider must deliver all motion slots and stride measurements. A renderer must satisfy independent multi-camera calibration and native/export pairing; writing an MP4 is insufficient.

Declare helper dependencies in `game_pipeline/implementation.py` or trusted `_implementation_files`. Provider code changes invalidate that stage and its consumers. Paid source identity is distinct from local preparation code. Add failure/negative controls and document licensing/setup. Stage JSON from an LLM must not select commands or local executable plugins; only trusted configuration may do that.

The public surface menu is data in `config/public_surfaces.json`. Add a real source ID with usable matched maps and license provenance, then verify its live metadata and downloads. Additional resource acquisition providers can replace `surface_assets` while retaining the `resources` bundle. Extend `fresh_sources.validate` deliberately if adding a new allowed provider; do not silently route fresh runs through a private catalog.

Use a sibling run for changes to a released project. See [CONTRIBUTING.md](../CONTRIBUTING.md) for validation and export rules.
