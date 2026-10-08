# Terrain Tools 1.0.3: optional layer-0 repair

## Install and use

1. Save your Blender project first. Close Blender, reopen it, then replace the old add-on through Preferences > Add-ons: remove SWTOR Terrain Tools and install `swtor_terrain_tools_1.0.3.zip`. Enable it. Restart Blender if the old version was already loaded.
2. Open your saved project and check the Resources folder setting.
3. Select the white terrain pieces that failed. Set **Apply to: Selected terrain**.
4. Enable **Repair unmapped layer 0**, below Bake size, and click **Apply / Update Terrain**.
5. Check the appearance and SWTOR Terrain Report. Save the `.blend` when satisfied.

Automatic room discovery still works. No need to rename your JSON or add it manually. For manual room selection, choose the original `default.dat`; its original sibling `area.dat` must be present. `area(1).dat` is an upload filename, not the filename the tool searches for.

## Why this is optional

The supplied Oricon room has 92 terrain patches. Three have significant texture weights for layer 0, which has no entry in its area material table. The selected patch `4611686298055754048` has one such sample; `4611686298055754063` has one; `4611686298055754077` has sixteen. This is not a missing texture file with a known material name.

Repair preserves mapped layer proportions, removes unmapped layer-0 weight, and fills samples that have no mapped weight from surrounding mapped blends. Equal-distance boundaries are averaged using four-neighbor propagation without edge wrapping. This is an approximation, not recovery of the missing original material. Inspect repaired patches, especially near sharp material boundaries.

The option defaults off. Other significant missing material IDs still fail. A patch with no mapped texture samples cannot be repaired. The existing tolerance for tiny residuals and absent terrain remains unchanged. Restore Original Terrain remains available.

## Where baked images go

Baked terrain and detail images are packed into Blender image data, not automatically saved as separate PNG files. Save the `.blend` to preserve them. Closing without saving loses new images and unsaved changes. Files already written by a separate export remain on disk. Recovery/autosave should not be relied on to preserve unsaved bakes.

## Verification

- 16 portable tests pass, including strict rejection, opt-in repair, boundary averaging, no-source rejection, and install packaging.
- All 92 supplied room patches pass weight processing with repair enabled; the other 89 produce identical weight arrays to the previous version.
- The three repaired patches pass 512px bake checks with placeholder diffuse images. Their real game textures were not supplied for a fresh visual bake or Unity test.
- JSON terrain IDs match all 92 binary room terrain IDs.

The supplied game files are not distributed with this patch.
