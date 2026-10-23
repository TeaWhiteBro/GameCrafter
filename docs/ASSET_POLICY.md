# Fresh-run asset policy

`production.source_policy: fresh` is the default for new prompts. It excludes the machine's prior `asset_catalog`, `mesh_library`, `texture_library`, `asset_descriptors` and `art_kits` before planning and construction.

| Source | Fresh production behavior |
|---|---|
| Scene concept | A new generation or reference-conditioned image edit in this run |
| Player and Boss | New text/image/multiview Tripo tasks; existing task IDs cannot be selected as input |
| Distinctive plants, building exteriors and props | Demand agent chooses necessary new assets within the explicit budget |
| Walkable buildings, terrain, roads, ramps and scalable details | Constructed from this run's Blender layout and reusable modeling code |
| PBR surfaces | Selected public source maps downloaded into this run, with license and hash receipts |
| Animations | Retargeted from a user-installed compatible UE motion library; not claimed as newly generated motion |
| Quality references | Written criteria by default; user-supplied benchmark images are optional |
| Interrupted work | The same run may resume its own verified assets and remote tasks |
| Previous cases | No automatic mesh, level, catalog, accepted-image or stage inheritance |

“From scratch” means no dependence on our demonstration assets. It does not mean rebuilding Blender/UE, synthesizing an engine animation library, or pretending publicly downloaded scans were generated. A benchmark must report these standard dependencies and which inputs the method receives. If a benchmark disallows public scans or motion libraries, supply and validate alternative providers; that stricter setting is not the default framework configuration.

`provided` is an explicit opt-in for local meshes, user-owned catalogs and accepted-case upgrades/replacements. It remains subject to all relevant acceptance requirements. Never report it as an independent fresh-generation result.

Source prompts must specify complete separated anatomy or botanical branches. A generated exterior cannot be assumed to have a navigable interior. Use Blender for supported passages and stairs. Preserve the source license/provenance even after preparation or material repair. A new material variant is not a new independently generated mesh.
