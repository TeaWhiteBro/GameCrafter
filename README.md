# GameCrafter project page

**GameCrafter: An Agentic Framework for Multi-Gameplay Game World Generation**

This repository contains the static research project page. It includes an interactive six-sector 3D overview, the method figure, eight recorded game-world cases, and a high-resolution Dune Court teaser.

## View locally

Use Python 3 on Windows, macOS, or Linux:

```sh
python3 serve.py
```

On Windows, `python serve.py` also works. Open `http://127.0.0.1:8765/`. Use `--port 8766` if the default port is occupied. A modern browser with WebGL is required for interactive 3D. Do not open `index.html` directly from the filesystem.

Viewing the checked-in site requires no build, API keys, or external asset server. Three.js, models, textures, media, and the browser bundle are included.

## What is included

- Six opening miniatures: Sakura Courtyard, Neon Switchyard, Dune Court, Frostwatch Outpost, Sunward Sentinel, and Abyssal Lock.
- Eight result cases, including the archived Amber Cloister and Ironwake Foundry.
- Exploration and Boss combat, three camera perspectives, and five visual representations where available in the recorded case.
- Orbitable authored-map previews and actual Unreal Engine images and videos.
- The manuscript abstract, four-stage method figure and interactive stage descriptions.

The opening disc is a representative web composition, not a full Unreal level export. Result images and videos come from the recorded UE cases. The five modality images within each paired set share a frame and camera; separate camera recordings are not claimed to be simultaneous. Browser depth and semantic images are display previews, not raw scientific arrays.

## Update content

| Path | Purpose |
| --- | --- |
| `index.html` | Page structure, method figure, teaser, and results |
| `src/worlds.js` | Case descriptions and miniature configuration |
| `src/media.json` | Gameplay, camera, modality, and full-map media |
| `src/diorama.js` | Interactive opening and character display poses |
| `src/panorama.js` | Full-map orbit viewer |
| `src/asset-transport.js` | Asset loading for ordinary and sandboxed hosts |
| `assets/figures/` | Method and teaser figures |
| `assets/models/`, `assets/images/`, `assets/videos/` | Browser-ready case media |

Preserve relative URLs so the page works below a repository path. A case can be opened directly with `?scene=neon_switchyard#results`. Media should preserve capture provenance and paired-frame alignment. Original game projects and production receipts are maintained separately.

After editing JavaScript, `src/media.json`, models, or miniature textures, rebuild with Node.js 18 or newer:

```sh
npm install
npm run build
npm run verify:assets
```

Commit the updated source and generated `src/site.bundle.js`, `src/portable-manifest.json`, and `assets/portable/` files together. HTML, CSS, and existing image/video replacements do not need a rebuild unless their paths change in JavaScript or the media manifest.

## Sandboxed project-page hosts

Anonymous GitHub isolates its page in an opaque-origin sandbox. ES modules and ordinary JavaScript asset requests can fail there even when images and videos are accessible. The checked-in classic script bundle includes the media manifest and supports this environment without changing the host's security policy or linking to an external asset domain.

On ordinary hosts, models and textures use their original files. In an opaque-origin sandbox, the same 3D assets are delivered as on-demand classic scripts, decoded locally, and checked against their recorded length and SHA-256 when available. These are lossless copies: geometry, textures, and videos are unchanged. Full-map models still load only when requested. Use a current browser with WebGL and `DecompressionStream` support. After pushing an update, refresh the anonymized repository if the service still serves its earlier snapshot.

## GitHub Pages

Publish the repository root from the `main` branch using **Settings → Pages → Deploy from a branch**. `.nojekyll` keeps the site as plain static files. No Git LFS or workflow build is required. Keep GLB, MP4, and image files in their current relative locations.

The sandbox-compatible copies add approximately 284 MiB to the repository; a visitor downloads only the asset representation needed by their host. MP4 files use native browser playback and seeking.

## Attribution

See [ATTRIBUTION.md](ATTRIBUTION.md) and [CAPTURE_NOTES.md](CAPTURE_NOTES.md). Three.js retains its MIT license and Draco retains its bundled license. Generated and user-supplied media retain their source/provider rights; these assets are not automatically relicensed under the dependency licenses.

## Showcase scope

This repository presents the method and recorded results. It does not distribute the production framework, source archives, or an anonymous code package. The title and four method stages follow the current manuscript; the full abstract is available in a collapsible panel so the page remains focused on visual results.

The page contains no author block, personal links, analytics, external fonts, or API credentials. All display resources use relative URLs. Third-party licenses remain intact. Original game projects, framework releases, and production receipts are maintained separately.
