# SWTOR Terrain Tools

**Turn imported SWTOR terrain into textured Blender scenes with grass, plants, and static 3D details.**

[Download v1.0.5](https://github.com/joystick1898/SWTOR-Terrain-Tools/releases/tag/v1.0.5) · [User guide](docs/USER_GUIDE.md) · [Version history](CHANGELOG.md) · [Credits](CREDITS.md) · [Report an issue](https://github.com/joystick1898/SWTOR-Terrain-Tools/issues)

Apply native terrain textures, grass and 3D details to SWTOR terrain meshes already imported into Blender. Designed to sit alongside [ZG SWTOR Tools](https://github.com/SWTOR-Slicers/ZG-SWTOR-Tools) and [SWTOR Terrain Extractor 2](https://github.com/UltimaKaosXIII/STE2).

The add-on matches terrain instance IDs to the original room data, blends the terrain's material layers into packed textures, and generates ordinary detail meshes. Existing terrain geometry and object placement are retained. No external engine, exporter or custom shader installation is required.

## Why use it?

- **Finish terrain that arrived as bare geometry.** Reconstruct native ground diffuse layers and painted tint from the original room data.
- **Populate scenes quickly.** Generate grass, plants, and supported static models with density, size, seed, category, and individual asset controls.
- **Choose the detail and cost you need.** Ground bakes range from 512 to 16K per patch; placement limits keep detail geometry manageable.
- **Iterate in Blender.** Apply again to replace generated results, inspect the run report, and restore the retained original terrain mesh when needed.
- **Prepare for a downstream workflow.** Packed images, standard Blender materials, baked UV0, and ordinary child meshes can be consumed by exporters. The project was developed for a Blender → TTS Bridge → Unity → Tabletop Simulator workflow; exporters are separate tools and end-to-end export has not been validated for this release.

This add-on does not extract TOR archives, import an area, or generate the base terrain mesh. ZG/extractor tools handle that part of the workflow.

## Download and install

**Current version: 1.0.5.**

**Tested in Blender 4.1.1.** This release targets the Blender 4.1 API; later versions are not yet verified. In particular, material transparency APIs changed after 4.1.

1. Download **[swtor_terrain_tools_1.0.5.zip](https://github.com/joystick1898/SWTOR-Terrain-Tools/releases/download/v1.0.5/swtor_terrain_tools_1.0.5.zip)** from the release assets. A matching `.zip.sha256` checksum is provided. If building from source, run `python scripts/build_release.py` and use the ZIP in `dist/`.
2. In Blender 4.1, open **Edit > Preferences > Add-ons > Install** and select that ZIP without extracting it.
3. Enable **SWTOR Terrain Tools**. Open the 3D View sidebar with **N**, then select **SWTOR Terrain**.

GitHub's **Source code (zip)** is the repository source, not the installable add-on. For upgrades, save your scene, install the new add-on ZIP and restart Blender. Existing 1.0.1 scenes retain their settings and generated-data identifiers.

## Requirements

| Input | Purpose |
| --- | --- |
| Blender 4.1.1 | Tested host; Blender supplies NumPy and the normal runtime APIs. |
| Imported terrain | Original extractor topology and numeric names or `swtor_id` properties from the ZG/extractor workflow. |
| Extracted `resources` folder | Preserve the original `art` and `world` directory hierarchy. |
| Original room DATs and sibling `area.dat` | Terrain IDs, paint, tint, details, and numeric asset mappings. |
| Referenced MAT / DDS / GR2 files | Ground/detail textures and supported static detail models. |
| Optional Zstandard support | gzip/zlib work directly; Zstandard inputs need a compatible module inside Blender's Python, which is not bundled. |

## First terrain pass

1. Save a scene backup, switch to **Object Mode**, and import your area and terrain with your existing ZG/terrain-extractor workflow.
2. Set **SWTOR resources** to the extracted `resources` folder containing `art` and `world`.
3. Start with one or two selected patches at the default **1024** bake size; choose a larger scope once the result looks right.
4. Leave room discovery automatic and click **Apply / Update Terrain**.
5. View the result in Material Preview. Change density, size, type toggles or limits and apply again to replace the generated details.

Automatic discovery needs original room DATs under `resources/world/areas`, with each area's `area.dat` beside its room files. The folder must also contain the referenced MAT, DDS and GR2 assets. The add-on does not extract TOR archives. A JSON by itself does not contain the binary terrain paint data.

Keep ZG's numeric terrain names or `swtor_id` properties. These identify the correct room records. Multiple source rooms are supported. If your DATs are stored elsewhere, **Choose room files (optional override)** accepts several room DATs or JSON filename hints. **Use automatic room discovery** clears those overrides.

**Restore Original Terrain** reattaches the original mesh/materials/UVs and removes generated details in the current scope. Save a backup before editing; Apply replaces manual changes to generated materials and detail children. Do not delete or rename the retained original mesh datablock if you need Restore.

## Features and limits

- Baked diffuse terrain layers, painted tint, packed images and standard Blender materials.
- Ground resolution choices from 512 through 16384 per patch; details retain their source/atlas resolution.
- Grass density, model density, size, seed, per-type toggles and per-patch limits.
- Automatic cached DAT discovery, repeat updates, preserved terrain holes and transforms.
- Ground errors leave the affected patch unchanged before commit; missing detail assets are reported and skipped.
- Supports observed dense version-2 heightmaps and static GR2 4.3/5.3 LOD0 layouts. Other terrain layouts and skinned details are unsupported.
- Grass uses crossed cutout cards. Scatter variation, scale and orientation are approximations; exact in-game distribution is not promised.
- This is a diffuse bake, not a reconstruction of the game's normal/specular lighting, wind, animation or full material graph.
- Sculpted, decimated, differently triangulated or modifier-driven terrain may not match safely. Large areas can take substantial time and memory.

Errors and skipped assets appear in Blender's Text Editor under **SWTOR Terrain Report**. See the [user guide](docs/USER_GUIDE.md) for controls, performance and troubleshooting.

## Options

| Control | What it does | Default / choices |
| --- | --- | --- |
| Apply to | Chooses candidate terrain meshes. | Selected terrain; Active collection and descendants; All matching terrain in the scene. |
| Bake size | Sets square ground texture dimensions **per patch**. | 1024 default; 512, 1024, 2048, 4096, 8192, 16384. |
| Repair unmapped layer 0 | Approximates missing layer-0 paint using surrounding mapped blends and reports repaired patches. | Off; see [repair behavior](docs/PATCH_1.0.3.md). |
| Grass and plants / 3D details | Enables each detail category independently. | Both on. |
| Grass density / Model density | Retains a fraction of deterministic candidates before limits. | 0.5 each; range 0–1. |
| Detail size | Scales detail geometry without resizing terrain. | 1.0; range 0.1–5. |
| Seed | Changes the reconstructed scatter pattern. | 0; range 0–1,000,000. |
| Plant limit / Model limit per patch | Caps placement counts, rather than resulting mesh counts. | 15,000 plants / 500 models; zero produces no placements in that category. |
| Color variation | Adds reconstructed grass color and size noise while retaining painted base color. | On. |
| Individual detail types | Enables/disables asset names found during processing. | Populated after first Apply; change toggles and apply again. |
| Choose room files / Use automatic room discovery | Sets or clears manual source overrides. | Automatic discovery until overrides are selected. |
| Restore Original Terrain | Reattaches the retained original mesh/materials/UVs and removes generated details in scope. | Keeps current object placement. |

Details are combined by type/material into ordinary child meshes that follow terrain transforms. No live particle systems, camera-facing billboards, or colliders are created. Apply replaces manual edits to generated data. Independently managing duplicates of already-prepared terrain is unsupported; use clean source terrain or a saved backup. [Complete control and ownership reference](docs/USER_GUIDE.md).

## Choosing a bake size

Start at 1024 for a quick check. Use a larger size when the ground bake visibly loses source detail and your machine and destination can handle the cost. Version 1.0.5 adds **4K, 8K, and 16K** choices. They sample the original textures again instead of upscaling old bakes. Different selections can be processed at different sizes.

| Bake size | Float RGBA output array alone, per patch |
| --- | ---: |
| 512 | 4 MiB |
| 1024 | 16 MiB |
| 2048 | 64 MiB |
| 4096 | 256 MiB |
| 8192 | 1 GiB |
| 16384 | 4 GiB |

These are array costs, **not total Blender memory or compressed file sizes**. Source textures, temporary arrays, Blender images, packing, and additional patches need more memory. Doubling width quadruples pixel count. Apply is synchronous and may make Blender appear busy.

Source ground textures repeat across a patch, so even 16K does not guarantee native pixel density or identical game rendering. Grass atlases and model-detail textures are unchanged. Destination texture import limits may downscale exported images. [Resolution details](docs/USER_GUIDE.md#choosing-ground-texture-resolution).

## What's new in 1.0.5?

- Added 4096, 8192, and 16384 ground bake choices with memory guidance in their tooltips.
- Kept the 1024 default, existing saved enum values, and ground bake arithmetic.
- Kept grass atlas and model-detail texture resolution unchanged.
- Completed the public documentation, attribution, portable CI, and reproducible installer packaging; credits accompany the installer.

Earlier versions added optional unmapped layer-0 repair (1.0.3) and smaller bake temporaries, asset conversion caching, and grouped detail processing (1.0.4). See the [full changelog](CHANGELOG.md) and [1.0.5 release notes](docs/PATCH_1.0.5.md).

Portable tests check parsers, sampling/repair, exact pixel equivalence, and reproducible packaging. Blender 4.1.1 synthetic checks cover holes, transforms, details, packed pixels, repeat Apply, failure retention, save/reopen, Restore, stable resolution choices, and a packed 4096-square bake. Full 8K/16K baking, real-game visual comparison for 1.0.5, and Unity/TTS export were not run. The [validation record](docs/VALIDATION.md) separates current checks from historical observations.

## Contributing and handoff

- [Development guide](docs/DEVELOPMENT.md): architecture, data ownership, testing and extension points.
- [Format notes](docs/FORMATS.md): binary layouts, coordinate conventions and known uncertainties.
- [Contributing](CONTRIBUTING.md): setup, code conventions and useful bug reports.
- [Publishing](docs/PUBLISHING.md): maintainer procedure for tested releases and installer uploads.
- [Validation](docs/VALIDATION.md), [changelog](CHANGELOG.md) and [credits](CREDITS.md).

Small synthetic regression tests remain in the repository because a one-byte format error or an axis reversal can silently damage a whole terrain scene. They need no game files and are excluded from the installable add-on. Generated previews, real game fixtures, private projects and old exports are not included.

From the repository root in a separate development environment:

```text
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m black --check swtor_terrain_tools tests scripts
python scripts/build_release.py
```

The build writes the installer and checksum to `dist/`. GitHub Actions runs portable checks and creates a package artifact; Blender integration remains a local check.

## Attribution and license

Maintained and published by **[joystick1898](https://github.com/joystick1898)**, with AI-assisted implementation and iterative testing. The author field credits **SWTOR Terrain Tools contributors**.

Acknowledgments: **ZeroGravitas / SWTOR Slicers** for ZG SWTOR Tools and the complementary import workflow; **UltimaKaosXIII** for SWTOR Terrain Extractor 2 and extraction/topology context; **Jedipedia** for File Reader inspection and terrain previews; **Blender** and **NumPy** for the host and numerical APIs. [CREDITS.md](CREDITS.md) records links and provenance. Acknowledgments do not imply endorsement or upstream authorship of this add-on.

Code is offered under **GPL-3.0-or-later**; see [LICENSE](LICENSE). This license covers this project, not SWTOR assets or third-party tools. No game assets are distributed. This is an independent community project, not an official SWTOR or SWTOR Slicers release.
## Earlier patches

**1.0.4:** performance update with smaller bake temporaries, converted-albedo caching, grouped detail processing, and fewer scene-wide scans. See [installation and validation](docs/PATCH_1.0.4.md).

**1.0.3:** optional **Repair unmapped layer 0** for isolated unmapped terrain texture samples. See [installation, repair behavior, and verification](docs/PATCH_1.0.3.md).
