# Third-party dependencies and asset rights

The MIT license covers this repository's original source and documentation. It does not relicense separately installed tools, engine content, generated models or downloaded scans.

- **Unreal Engine and template animations:** installed by each user under Epic's applicable license. No Epic binaries, `.uasset` files or animation data are distributed here. The code invokes the documented engine integration and expects a compatible installation.
- **Blender:** separately installed software under its own license. This distribution contains integration scripts, not Blender binaries.
- **Python dependencies:** installed from requirements.lock.txt and retain their individual licenses. The source export contains no vendored Python package binaries.
- **Poly Haven materials:** acquired at run time; public metadata identifies CC0 sources. Every acquired set records the source page and hashes. There are no scan binaries in the source export.
- **Level Infinite / Tripo / image and chat models:** external services requiring account access. Generated outputs follow their provider terms; they are not labelled CC0 or MIT by this framework.
- **User references and supplied meshes:** the user controls their inclusion and sharing rights. Inputs and outputs are ignored by default.

The templates/Source directory contains the project's C++ integration/gameplay runtime, not copied engine content. A source release is distinct from distributing a built UE game; follow the relevant engine and asset terms for a later binary release.
