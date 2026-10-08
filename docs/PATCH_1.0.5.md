# Version 1.0.5 — Higher-resolution ground bakes

Released October 8, 2026. [Release assets](https://github.com/joystick1898/SWTOR-Terrain-Tools/releases/tag/v1.0.5).

## Why update?

Choose a larger ground bake when a terrain patch looks soft at the previous maximum of 2048. The new 4096, 8192, and 16384 choices sample the original textures again and retain more ground detail where output resolution was the bottleneck. They cannot reconstruct missing data or the game's complete shader.

## Changes

- Add **4096 (4K)**, **8192 (8K)**, and **16384 (16K)** to Bake size.
- Preserve existing 512/1024/2048 choices and their saved numeric enum values.
- Keep **1024** as the default and retain the previous ground bake calculations.
- Add memory guidance to the option tooltips and repeating source texture density guidance to the user guide.
- Keep grass atlases, model-detail textures, scatter settings, and downstream material metadata unchanged.
- Prepare public documentation, credits, version history, and portable CI. Include credits alongside the GPL license in reproducible installers. Apply Black formatting to source/tests without changing terrain algorithms.

## Install or upgrade

Save your scene. Download `swtor_terrain_tools_1.0.5.zip` from the release assets and install it without extracting through Blender 4.1's **Edit → Preferences → Add-ons → Install**. Enable the add-on; restart Blender after upgrading. GitHub's **Source code (zip)** is not the installer.

Select the patches, choose **Bake size** in the **SWTOR Terrain** sidebar, and click **Apply / Update Terrain**. Old bakes remain unchanged until Apply. Apply also regenerates details with the current settings; keep custom edits separately.

## Resolution costs

The float RGBA output buffer alone uses **256 MiB at 4K, 1 GiB at 8K, and 4 GiB at 16K per patch**. Actual memory is higher because source images, temporary buffers, Blender images, and packing also consume memory. Start with a small selection. Doubling width quadruples pixel count and can increase processing time and export size.

These presets affect ground images only. Source textures repeat across a patch, so there is no single native full-patch bake size. Destination limits may downscale exported images. See the [user guide](USER_GUIDE.md#choosing-ground-texture-resolution).

## Verification and limits

Portable regression coverage checks parsers, sampling, repair, exact pixel equivalence with the earlier full-frame bake, and reproducible installer content. Blender 4.1.1 synthetic checks cover holes/transforms, details, packed pixels, repeat Apply, failed-ground retention, save/reopen, Restore, stable resolution choices, and a packed 4096-square bake. See the [validation record](VALIDATION.md).

Full 8K/16K baking and real-game visual comparison were not run. Unity/Tabletop Simulator export was not tested. Support remains the observed dense-v2 terrain and static GR2 subset on Blender 4.1; later transparency APIs are not validated.

## Earlier improvements included

- **1.0.4:** strip baking, converted-albedo caching, grouped details, tracked generated resources, and shared area-table caching. [Performance notes](PATCH_1.0.4.md).
- **1.0.3:** optional, default-off unmapped layer-0 repair. [Repair notes](PATCH_1.0.3.md).
- **1.0.2:** community source preparation, documentation, packaging, and tests.
- **1.0.1:** exact-ID automatic discovery, terrain support handling, and conflict reporting.
- **1.0.0:** native ground diffuse/tint baking, grass/static details, update and Restore.

## Credits and license

Maintained by [joystick1898](https://github.com/joystick1898), with AI-assisted implementation and acknowledgments in [CREDITS.md](../CREDITS.md). Code is GPL-3.0-or-later. No game assets are included; their ownership and redistribution rights are separate.
