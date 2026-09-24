# Sakura display-color correction

The Sakura gameplay posters had already been captured with correct display
color, but the two linked third-person videos and archived camera thumbnails
still came from an older RGB capture path. That path encoded sRGB twice,
lifting midtones and washing out materials when playback started.

The exploration and combat videos now use all 360 original lossless source
frames with exactly one redundant sRGB encoding removed. Frame count,
resolution, animation timing, and 60 fps playback are retained. The MP4s use
explicit BT.709 matrix and limited-range metadata. This is a correction of a
known capture transfer error, not a change to scene lighting or exposure.

The transfer correction was compared against a previously validated same-frame
native Unreal recapture: mean RGB error fell from 53.34 to 0.40 on an 8-bit
scale before video compression.

The three combat camera images and all six archived source posters are also
corrected. The gallery's high-resolution native exploration stills, main
gameplay posters, and aligned multimodal stills were already correct and remain
unchanged. Other cases are unchanged. The original game projects, captures,
depth arrays, semantic labels, and skeleton metadata are preserved.

Corrected media filenames contain `display_v2` to distinguish them from the
historical capture and avoid stale browser video caches. The correction must
not be applied again to these media or to native display-correct captures.

## Dune Court and Frostwatch Outpost

These September 19 benchmark exports already have correct display color. Their RGB videos are copied without re-encoding or exposure/gamma operations. Main posters come from their own frame 0. Five aligned stills come from native frame 120 of the corresponding third-person combat capture; camera thumbnails use frame 90 from each independent session. Semantic colors and depth colors remain display previews, while their original integer IDs and metric arrays are preserved in the source collection.

## Interactive authored-map miniatures (September 21)

The results section now offers an orbit/zoom miniature for each of six accepted scenes, including Ironwake Foundry. These are actual archived Blender environment layouts, reduced and batched for WebGL. Far-field terrain outside the playable route is cropped for presentation. Source material descriptions approximate the engine appearance, while the original Unreal gameplay captures remain authoritative. The viewer loads one map on demand, supports mouse/touch rotation and zoom, and has a reset control.

Ironwake Foundry media uses the accepted source release and native five-channel frame 120. No exposure or gamma correction was applied. Cloister remains in results. The courtyard is withheld from promotion because its fourth diagnosed art preflight still failed; the front disc therefore retains the existing five accepted worlds. Original accepted scenes and historical page media were not changed.

## Current courtyard capture · 2026-09-21

Sunward Sentinel uses current-run rigged characters, generated olive/fountain/flowers, and Blender scene geometry. Source receipts: `scripts/courtyard_media_provenance_20260921.json`. The native UE captures retain their original transfer, resolution and timing. The earlier art refusals are preserved in the separate closeout record.

## Underwater paired captures · 2026-09-21

Six independent controlled camera/activity sequences contain 360 frames each. Page videos are byte-identical accepted export previews. Display JPEGs preserve the source color transfer. Five modality images are frame 120 of the selected activity in third person; the three camera examples are frame 90 of separate runs, not simultaneous cross-camera ground truth. Glass follows opaque_surface_behind_glass_v1: RGB includes bounded non-refractive glazing; metric depth and semantic IDs identify the first opaque surface behind it. Structural whitebox omits transparent infill. Raw arrays and lossless IDs remain authoritative.
