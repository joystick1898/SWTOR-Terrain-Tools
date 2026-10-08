# Developer handoff

## Module boundaries

| File | Responsibility |
| --- | --- |
| `swtor_terrain_tools/core.py` | Binary readers, exact-ID discovery/cache, path resolution, MAT subset, bilinear sampling, weight repair, diffuse baking, static GR2 subset. NumPy only; no bpy. |
| `swtor_terrain_tools/details.py` | Deterministic candidate selection, density thinning, surface interpolation and variation. Uses mathutils; creates no scene data. |
| `swtor_terrain_tools/__init__.py` | Add-on registration, persisted settings, UI/operators, Blender image decoding, mesh fitting, material generation, detail geometry and lifecycle. |
| `tests/test_core.py` | Synthetic parser, weight, sampling/path and discovery-cache regressions. |
| `tests/blender_smoke.py` | Synthetic Blender integration: registration, materials, transformed geometry, details, repeat updates, saved file and restore. |
| `scripts/build_release.py` | Deterministic allowlisted installation ZIP; does not import bpy. |

`__init__.py` remains larger than ideal to preserve the proven code and saved-file interfaces. A later extraction into scene/material/UI modules should keep class names, operator IDs and property identifiers stable. This release formats and documents the implementation without rewriting its algorithms.

## Processing flow

1. `targets` collects meshes in scope and excludes generated details. `object_id` walks custom properties/names on each mesh and its parents.
2. `resolve_rooms` uses overrides or `core.discover_rooms`. The scanner indexes terrain IDs from room property headers without decompression. The cache uses the resources root, relative path, byte size and nanosecond mtime; it is not a content-hash cache.
3. The Apply operator loads matching compressed records and each room's table, rejecting conflicting records with the same ID before scene edits.
4. `apply_one` fits the source grid to the existing mesh and derives its actual surviving triangles. `core.bake` blends source colors using valid weights and tint.
5. Missing/unsupported detail assets append diagnostics. Candidate placements are thinned and capped, then expanded into batched mesh geometry. Grass tint is baked into a small padded palette atlas.
6. Newly generated datablocks are staged under a fresh ownership token. The original mesh is retained on the first successful commit; new mesh data is attached and previous owned resources are cleaned.
7. A shared Blender text datablock records results. Failures on individual patches do not prevent later patches from being attempted.

## Coordinates and image encoding

Source terrain is canonical Blender Z-up `(x, -z, height)`, grid spacing 0.2. The least-squares fit maps homogeneous source row vectors to existing object-local coordinates. Parent/object transforms are not applied again. The fit checks error relative to mesh extent and handles planar grids by reconstructing a normal axis.

The fast path assumes source vertex order. The fallback reconstructs vertex-grid correspondence from UVs when OBJ import has removed unused vertices at holes. Scene triangles, not just source hole bits, determine detail placement and visibility for unknown-weight repair. Alternate triangulation is rejected.

Source pixel arrays are top-down encoded RGBA, not linear-light RGB. Blender images are read Non-Color with CHANNEL_PACKED alpha. New arrays are packed while Non-Color, then marked sRGB for shading. UV generation handles the vertical convention change. Changing any of these conventions requires pixel and orientation regression checks.

## Ownership and saved-file contract

| Property / name | Stored on | Purpose |
| --- | --- | --- |
| `Scene.swtor_terrain` | Scene | Persistent settings and room/type lists |
| `swtor_terrain_generated` | Generated object/mesh/material/image | Private build owner token; limits cleanup |
| `stt_owner` | Source terrain object | Current build token |
| `stt_original_mesh` | Source terrain object | Original mesh datablock name for Restore |
| `stt_instance_id` | Source terrain object | Stable source ID independent of its display name |
| `stt_label` | Generated images/materials | Preferred readable name after replacing staged data |
| `stt_instances` | Generated detail child | Number of batched placements |
| `SWTOR Terrain Bake` | Prepared mesh UV layer | Baked UV0; recognized during repeat matching |
| `SWTOR Terrain Report` | Text datablock | Latest diagnostics |

Materials also retain a small optional metadata contract: `stt_generated_version=1`, `stt_albedo_image`, `stt_cutout`, `stt_cutoff`, `stt_two_sided`, and ground-only `stt_kind='ground'`. These are plain custom properties with no exporter dependency. They are kept for existing scenes and downstream consumers; renaming them is a compatibility change.

Cleanup removes owned objects first, then unused meshes, materials and images. Retained original meshes use a fake user. Shared generated data with remaining users is kept. Do not use a broad name-prefix deletion: user-created data can share names.

Pre-commit failures clean staged data. This is not fully transactional after `obj.data` is swapped: an unexpected cleanup/rename failure could leave a partially committed patch. The whole scene is also not atomic. Blender Undo and saved backups remain important. Name-based original-mesh tracking and copied ownership tags on duplicated prepared objects are known limitations.

## Testing

```
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m black --check swtor_terrain_tools tests scripts
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
python scripts/build_release.py
```

Run from repository root; Blender must be on PATH or invoked by full executable path. Do not install desktop-Python packages into Blender to run the synthetic smoke test: Blender supplies NumPy/mathutils/bpy. GitHub CI runs the portable tests and packaging; the Blender check is a local release gate and is not represented as a CI pass.

For real-data validation, use private local assets and a saved test scene. Check several material mixes, a terrain hole, grass, cutout models and multiple rooms. Compare visible texture orientation/scale to a trusted reference, repeat Apply, save/reopen and Restore. Keep fixtures and generated files outside the repository. Historical testing decoded 201 patches from one Belsavis room and exercised 16 layer-0 cases; it does not establish universal planet coverage.

## Extension priorities and risks

- **New Blender versions:** adapt removed material transparency properties; retain 4.1 behavior and test both renderers/versions before claiming support.
- **New binary layouts:** dispatch explicitly by version/flags, add synthetic boundary fixtures, and document field evidence. Avoid guessed offsets in the dense-v2 reader.
- **Scatter parity:** replace empirical constants only with measured evidence; deterministic placement and saved size controls should remain predictable.
- **Shader coverage:** add explicit per-family texture/opacity conversion. Do not silently treat animated/inherited materials as direct diffuse.
- **Memory/progress:** current Apply is synchronous and asset caches are unbounded for a run. Very large areas can be expensive. A future cancellable operator needs careful per-patch staging and cleanup.
- **Parser hardening:** Reader bounds-checks reads; direct struct/unpack and text lookup can still raise other exceptions. gzip/zlib decompression is not output-size capped. Inputs are expected to be locally extracted game resources; do not present these readers as a hardened untrusted-file service.
- **Cache:** mtime/size invalidation can miss content changes that preserve both. Deleting the cache forces reindexing. Multiple simultaneous Blender writers are not coordinated.

Keep format uncertainty visible. A clear unsupported-format report is preferable to a plausible-looking wrong material or mesh.
