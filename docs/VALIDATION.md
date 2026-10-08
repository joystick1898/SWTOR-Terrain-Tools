# Community release validation

## 1.0.5 local validation — October 8, 2026

- Publication checks rerun after documentation, attribution packaging, and Black formatting: all 17 portable tests, formatting of all nine Python files, both Blender 4.1.1 smoke scripts, and the installer build passed. The installer includes CREDITS.md and LICENSE; the packaging test checks exact contents and byte-for-byte reproducibility.
- All 17 portable tests pass on Python 3.14.7 / NumPy 2.5.3, including unchanged-resolution pixel equivalence and deterministic packaging.
- Blender 4.1.1 passes the existing synthetic scene smoke test covering holes, transforms, details, packed pixels, repeat Apply, failed-ground retention, save/reopen, and Restore.
- `tests/blender_resolution_smoke.py` verifies the unchanged 1024 default, stable numeric enum values, and save/reopen of all six resolution choices. A synthetic 4096-square bake produces expected sampled colors, packs into a Blender image, and survives save/reopen at its full dimensions.
- Full 8K/16K baking and real-game visual comparison were not run. Unity/TTS export was not tested. Installed Blender add-on files were not modified.

Run the added check from `Source/` with Blender 4.1:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 4.1/blender.exe' --background --factory-startup --python-exit-code 1 --python tests/blender_resolution_smoke.py
```

## Historical validation

For 1.0.2, the following local checks passed:

- **14 portable tests:** 13 synthetic terrain/core regressions plus an install-ZIP content/reproducibility check.
- **Blender 4.1.1 synthetic smoke test:** OBJ import with a hole and dropped unused vertex; transformed parent; packed ground/detail materials; detail generation; repeated update with stable names/counts; missing-ground failure retaining the previous mesh; encoded PNG pixel values; save/reopen; original-mesh restoration and cleanup.
- **Behavior preservation:** AST comparison against the delivered 1.0.1 source confirmed all 38 top-level function/class implementations were unchanged after removing docstrings. Changes to runtime files are comments, formatting, module documentation, unused-import cleanup and release metadata.
- **Black formatting check and deterministic installation build.**

The GitHub workflow checks formatting, portable tests, and packaging on Python 3.11/3.12 and creates installer artifacts. It does not execute Blender. Hosted run results are on the repository's Actions page; local checks alone do not establish a hosted pass.

Earlier 1.0.1 validation decoded all 201 patches in a private Belsavis room, processed 16 layer-0 cases in Blender, and checked a four-patch scene with grass/static details. The original user subsequently confirmed successful large-scene use. Those fixtures and outputs are not included, and this evidence does not establish support for every terrain or newer Blender API.

Repeat these checks after behavior changes. See [DEVELOPMENT.md](DEVELOPMENT.md) for commands and known test gaps.
