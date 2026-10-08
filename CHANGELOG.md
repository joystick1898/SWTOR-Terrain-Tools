# Changelog

## 1.0.5 - Higher-resolution ground bakes

- Add 4096, 8192, and 16384 pixel Bake Size choices per terrain patch.
- Preserve existing saved resolution values, the 1024 default, and bake calculations.
- Explain memory costs in option tooltips and native texture density in the user guide.
- Detail texture and grass atlas resolution are unchanged.
- Complete public installation/usage documentation, control/default reference, attribution, release notes, and portable CI.
- Include CREDITS.md alongside LICENSE in the deterministic installer.
- Normalize source/test formatting with Black without changing terrain algorithms.
- See [1.0.5 release notes](docs/PATCH_1.0.5.md) and [validation](docs/VALIDATION.md).

## 1.0.4 - Performance update

- Bake in 64-row strips while preserving pixel calculations and material accumulation order.
- Cache converted detail albedos per Apply operation and group detail placements once.
- Track newly created materials/images directly for final naming and export metadata.
- Parse shared area tables once per Apply operation.
- Preserve UI, settings, detail selection, geometry, repair rules, and output quality.
- See [patch notes](docs/PATCH_1.0.4.md) for historical validation and performance measurements.

## 1.0.3 - Optional unmapped layer-0 repair

- Add opt-in **Repair unmapped layer 0**, disabled by default.
- Preserve mapped layer proportions and fill wholly unmapped samples from surrounding mapped blends using four-neighbor propagation.
- Continue rejecting other significant missing material IDs and patches without mapped source samples.
- Add repair regression coverage. See [patch notes](docs/PATCH_1.0.3.md) for limitations and historical validation.

## 1.0.2 - Community source preparation

- Standalone repository and installable add-on packaging; no external-engine project or private exporter files.
- Conventional Python formatting, function documentation, coordinate/format comments and ownership explanations.
- Installation, troubleshooting, contributor, format and publishing guides.
- Synthetic tests, Blender smoke test and portable GitHub Actions checks.
- Retains 1.0.1 terrain algorithms, controls, saved properties and optional material metadata.

## 1.0.1 - Terrain fixes and discovery

- Automatic room DAT discovery by exact terrain ID with a persistent index.
- Manual multi-room overrides retained.
- Unmapped layer residuals up to 1/255 are removed and valid weights renormalized.
- Strong unmapped samples wholly outside surviving terrain support no longer block a patch.
- Conflicting duplicated source IDs are reported; identical records are accepted.

## 1.0.0 - Initial working add-on

- Dense-v2 native ground diffuse/tint bake onto existing terrain.
- Grass cards and static model details with density, size, type and budget controls.
- Packed materials, update-in-place staging and original-mesh restoration.
- Terrain-hole and transform-aware matching.
