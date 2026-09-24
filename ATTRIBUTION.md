# Attribution and provenance

## Runtime

Three.js **0.180.0** is included under the MIT License. Its copyright and full license text are preserved in `vendor/three/LICENSE`. The page uses GLTFLoader, SkeletonUtils, BufferGeometryUtils, and RoomEnvironment from that release.

## Environment resources

The following Poly Haven resources are CC0, as recorded in the source asset manifests. The page includes resized diffuse maps:

| Page asset | Source |
| --- | --- |
| `texture_stone.jpg` | [Monastery Stone Floor](https://polyhaven.com/a/monastery_stone_floor) |
| `texture_grass.jpg` | [Leafy Grass](https://polyhaven.com/a/leafy_grass) |
| `texture_asphalt.jpg` | [Clean Asphalt](https://polyhaven.com/a/clean_asphalt) |
| `texture_sand.jpg` | [Red Sand](https://polyhaven.com/a/red_sand), neutralized albedo for the miniature material |
| `texture_snow.jpg` | [Snow 02](https://polyhaven.com/a/snow_02) |

The shrine, cherry tree, cyberpunk shop, hover vehicle, sandstone house, market stall, date palm, ranger lodge, watchtower, spruce, and current characters were prepared from the project's generated assets. The Amber Cloister guardian comes from the accepted reference-image Boss replacement. Web meshes were exported and simplified in Blender; some materials and character display poses are adapted for the diorama. Architecture such as arches, columns, the miniature paths, footbridge, awning, and cloister is authored directly in the page.

Generated and user-supplied media retain their applicable source/provider rights. This package does not assign them the Three.js or Poly Haven license.

## Case lineage

| Display case | Capture and asset lineage |
| --- | --- |
| Sakura Courtyard | Accepted `sakura_courtyard` case; six perspective/gameplay sessions plus corrected high-resolution presentation captures |
| Neon Switchyard | Accepted `neon_switchyard` cyberpunk case and its multimodal sessions |
| Dune Court | Fresh `desert_caravanserai` benchmark; accepted release `ebd880c3cff10eb6`, six 360-frame perspective/gameplay sessions |
| Frostwatch Outpost | Fresh `snowbound_outpost` benchmark; accepted release `7f2289b94e96a799`, six 360-frame perspective/gameplay sessions |
| Amber Cloister | Expanded `system_v07_demo` monastery with the reference-image bull Boss |

Rejected early cases are not included as display worlds. Early Moonshore and Observatory entries were replaced in this page; their original demos remain archived. The six-session cases use available clips; their lengths vary.

All result images and videos are derived from actual project captures, resized or transcoded for the browser. Sakura's aligned stills come from frame 0 of the corrected linear-capture sequence. Other aligned stills use a common time from their capture sequence or composite. Different camera sessions are not asserted to be simultaneous. The hero miniature is a separate display composition.

Sakura's two main gameplay videos and archived camera thumbnails include a verified correction of one redundant sRGB encoding in the historical capture. See `CAPTURE_NOTES.md` for the correction and validation; timing and scene content are unchanged.

## Framework source

`assets/worldcrafter-framework-v1.0.zip` is a copy of the project's existing bilingual v1.0 release. Its own documentation and licensing apply to that source archive. This project-page folder supplies presentation assets and is separate from the game-generation runtime.

New benchmark result videos are byte-identical copies of their accepted RGB exports. Their five aligned images use native frame 120 from one third-person combat sequence; independent camera thumbnails use frame 90. No Sakura transfer correction was applied to the new results. See `scripts/benchmark_media_provenance.json` for source hashes and transformations.

The miniature viewer adds OrbitControls and DRACOLoader from Three.js 0.180.0 (MIT), with its bundled Draco decoder (Apache 2.0). See `vendor/three/examples/jsm/libs/draco/LICENSE`.

## Current courtyard assets · 2026-09-21

Sunward Sentinel uses current-run rigged characters, generated olive/fountain/flowers, and Blender scene geometry. Source receipts: `scripts/courtyard_media_provenance_20260921.json`. The native UE captures retain their original transfer, resolution and timing. The earlier art refusals are preserved in the separate closeout record.

## Underwater sources · 2026-09-21

Abyssal Lock uses the accepted current-run diver player, pressure-suit Boss, submersible, coral and pressure relay, plus the authored habitat geometry. No other case assets were used for this production. Display exports preserve source references in scripts/underwater_media_provenance_20260921.json.


## Multi-scene teaser · 2026-09-24

The teaser combines a fresh high-resolution render of the same six-sector web diorama with four existing Unreal Engine captures. The garden uses the accepted first-person arrival-gate image; the neon and desert images use their accepted route captures; the snow image uses its accepted exploration camera. The images are cropped for composition without synthesizing or retouching scene content. The central miniature remains a representative web display rather than an Unreal level export.
