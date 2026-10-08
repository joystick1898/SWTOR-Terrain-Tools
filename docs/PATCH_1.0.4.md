# Terrain Tools 1.0.4: performance update

## Install

Save your Blender project. Extract the release download, replace the old add-on
in Preferences > Add-ons with the enclosed `swtor_terrain_tools_1.0.4.zip`, enable
it, and restart Blender. The sidebar, settings, resource discovery, and export
workflow are unchanged. No need to rebuild already prepared terrain unless you
want to change it. Existing textures will not become smaller or sharper.

## Changes

- Bake images in 64-row strips, retaining the same global pixel coordinates,
  arithmetic, precision, and material accumulation order. This reduces temporary
  memory use. Clipping uses the output buffer instead of allocating another image.
- Cache converted detail albedos for each Apply operation. Original DDS decoding
  was already cached; now opacity conversion and diffuse copies are reused too.
  Cached arrays are read-only and returned metadata is independent. The cache
  expires at the end of Apply; this trades retained converted pixels during that
  operation for fewer repeated conversions.
- Group detail placements once, preserving their order. Reuse groups for geometry
  limits and mesh construction instead of rescanning every placement per channel.
- Track newly created materials/images directly for final naming and exporter
  metadata, avoiding scene-wide scans at that step. Cleanup retains its existing
  ownership and user-count checks, including its scene scans.
- Parse each shared area.dat once per Apply.

Plant selection, randomness, mesh transforms, atlas construction, bake sizes,
repair rules, shader settings, and export metadata are unchanged. This update
does not attempt smaller bundles or a different terrain shader.

## Verification

17 portable tests pass. Exact array comparisons against the original 1.0.3 bake
cover 512, 1024, 2048, and non-multiple-of-64 sizes, rectangular source textures,
multiple materials, tinting, and optional layer-0 repair. Report messages match.

Blender 4.1.1 integration passes: OBJ holes, transformed terrain, generated grass,
packed texture pixels, repeated Apply, failed-ground retention, save/reopen, and
Restore. The baseline and optimized fixture have identical output signatures
covering geometry, UVs, names, and packed image bytes. Converted-albedo caching
also passes source immutability and independent metadata checks.

The earlier synthetic strip-bake experiment measured roughly 30-38% faster bake
computation at 512/1024. This is not a measured end-to-end speedup on a full game
area. No new Unity/TTS export test was run for this update.

## Developer notes

Run `python -m unittest discover -s tests -v` for portable tests. Run Blender 4.1
with `--background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py`
for integration. Build with `python scripts/build_release.py`.

The full-frame reference in tests/test_bake_equivalence.py is intentionally
retained as an independent arithmetic regression baseline. No game assets are
included in the tests or release.
