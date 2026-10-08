# Publishing a release

Repository: [joystick1898/SWTOR-Terrain-Tools](https://github.com/joystick1898/SWTOR-Terrain-Tools). Current release: **v1.0.5**. The source package is at the repository root; `dist/` is generated locally and excluded from Git.

## Prepare and verify

1. Update `bl_info['version']`, README installer links, CHANGELOG, version notes, and validation together. Preserve package and saved-property identifiers.
2. Run from the repository root in a separate development environment:

```text
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m black --check swtor_terrain_tools tests scripts
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_resolution_smoke.py
python scripts/build_release.py
```

Use a verified Blender 4.1 executable if it is not on PATH. For behavior changes, check representative private real-data scenes too. Record what actually ran and keep untested configurations visible.

3. Confirm the ZIP contains only the three runtime Python modules, LICENSE, and CREDITS.md under `swtor_terrain_tools/`. Exclude game assets, virtual environments, caches, internal chat handoffs, personal paths, and scene outputs.
4. Commit the source/docs and confirm GitHub Actions passes. CI checks formatting, portable regressions, and packaging on Python 3.11/3.12; it does not run Blender.

## Publish the installer

Create a GitHub Release with tag **v1.0.5** targeting the tested commit and title **SWTOR Terrain Tools 1.0.5 — Higher-resolution ground bakes**. Adapt `docs/PATCH_1.0.5.md` for the release page with working repository links.

Upload both:

- `dist/swtor_terrain_tools_1.0.5.zip`
- `dist/swtor_terrain_tools_1.0.5.zip.sha256`

The installer ZIP is the Blender installation asset. GitHub's automatically generated source archives are for development. CI artifacts are temporary downloads; the public Release is the intended installation link.

Verify the public README, release, named assets, sizes, version, and checksum. Do not silently replace published installers: use a new version for later changes.

## Repository description

About description: **Blender add-on for native SWTOR terrain textures, grass, and static details. Density controls, 512–16K ground bakes, update and restore.**

Topics: `blender`, `blender-addon`, `swtor`, `terrain`, `star-wars`, `tabletop-simulator`.

## Attribution

Retain GPL-3.0-or-later notices and CREDITS.md in source and installers. Copied/adapted third-party code requires its own attribution and license. The project license does not cover game assets; acknowledgments do not imply endorsement or organization ownership.
