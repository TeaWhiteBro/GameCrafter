# GameCrafter project page

**GameCrafter: An Agentic Framework for Multi-Gameplay Game World Generation**

This repository contains the static research project page. It includes an interactive six-sector 3D overview, the method figure, eight recorded game-world cases, and a high-resolution cyberpunk teaser.

## View locally

Use Python 3 on Windows, macOS, or Linux:

```sh
python3 serve.py
```

On Windows, `python serve.py` also works. Open `http://127.0.0.1:8765/`. Use `--port 8766` if the default port is occupied. A modern browser with WebGL is required for interactive 3D. Do not open `index.html` directly from the filesystem.

The site has no build step and needs no API keys or external asset server. Three.js, models, textures, and media are included.

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
| `assets/figures/` | Method and teaser figures |
| `assets/models/`, `assets/images/`, `assets/videos/` | Browser-ready case media |

Preserve relative URLs so the page works below a repository path. A case can be opened directly with `?scene=neon_switchyard#results`. Media should preserve capture provenance and paired-frame alignment. Original game projects and production receipts are maintained separately.

## GitHub Pages

Publish the repository root from the `main` branch using **Settings → Pages → Deploy from a branch**. `.nojekyll` keeps the site as plain static files. No Git LFS or workflow build is required. Keep GLB, MP4, and image files in their current relative locations.

The site contains approximately 530 MiB of display assets. Large map models load only on request. MP4 files support native browser playback and seeking.

## Attribution

See [ATTRIBUTION.md](ATTRIBUTION.md) and [CAPTURE_NOTES.md](CAPTURE_NOTES.md). Three.js retains its MIT license and Draco retains its bundled license. Generated and user-supplied media retain their source/provider rights; these assets are not automatically relicensed under the dependency licenses.

## Showcase scope

This repository presents the method and recorded results. It does not distribute the production framework, source archives, or an anonymous code package. The title and four method stages follow the current manuscript; the full abstract is available in a collapsible panel so the page remains focused on visual results.

The page contains no author block, personal links, analytics, external fonts, or API credentials. All display resources use relative URLs. Third-party licenses remain intact. Original game projects, framework releases, and production receipts are maintained separately.
