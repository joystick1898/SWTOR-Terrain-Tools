# User guide

## Files and setup

Use Blender 4.1 with terrain already imported from the extractor/ZG workflow. This add-on does not import room objects, extract TOR archives or generate the base terrain mesh. It reads your extracted resources and changes the chosen Blender scene meshes.

| Input | Purpose |
| --- | --- |
| `resources/world/areas/<area-id>/<room>.dat` | Terrain instance IDs, compressed heightmaps, layer weights, tint and detail paint |
| `area.dat` beside each room | Maps numeric texture/detail IDs to asset names and parameters |
| `resources/art/shaders/materials/*.mat` | Diffuse and cutout texture references |
| DDS files in their original resource paths | Ground/detail textures |
| GR2 files in their original resource paths | Static 3D detail geometry |

Use the original directory structure. Do not rename a JSON or OBJ to DAT. Downloaded names such as `hub1green(1).dat` work when selected directly, but a `hub1green.json` filename hint looks for `hub1green.dat`.

Automatic lookup scans original DATs under `world/areas` and matches exact terrain IDs, not approximate names. The first scan indexes room headers; later runs reuse unchanged entries. Changed or removed files are refreshed. The cache is `swtor_terrain_tools/room-index.json` inside Blender's user configuration directory. It can be deleted while Blender is closed to force rebuilding. It does not modify game files.

Manual overrides are useful when files are elsewhere or multiple conflicting room records share an ID. The list takes priority until **Use automatic room discovery** clears it. You may select multiple files and add sources from several folders; each uses its own sibling `area.dat`. Do not select `area.dat` as a room.

## Scope and controls

Start with one or two patches to check alignment and appearance. Large imports work, but bake size and detail limits multiply by the number of patches. Blender may appear busy while the synchronous operation runs.

| Control | Meaning |
| --- | --- |
| Selected terrain | Candidate mesh objects currently selected; generated children are excluded |
| Active collection | Candidate meshes in the active collection and its descendants |
| All matching terrain | Scene meshes whose IDs appear in the chosen/discovered terrain records |
| Bake size | Square ground texture resolution per patch: 512, 1024 (default), 2048, 4096, 8192 or 16384 |
| Repair unmapped layer 0 | Off by default. Approximate isolated missing layer-0 paint from surrounding mapped blends; see [repair notes](PATCH_1.0.3.md). This cannot supply a missing source texture or repair other significant missing material IDs. |
| Grass and plants / 3D details | Independent category toggles |
| Grass density / Model density | Fraction of deterministic candidate placements retained, before limits |
| Detail size | Multiplier for detail geometry, not terrain size |
| Seed | Changes the reconstructed scatter pattern |
| Plant limit / Model limit per patch | Maximum placement counts, not mesh counts |
| Color variation | Reconstructed grass color/size noise; painted base color remains |
| Individual detail types | Asset-name toggles populated after the first Apply; change them and apply again |

Defaults are 0.5 grass density, 0.5 model density, 1.0 detail size, seed 0, 15,000 plants and 500 model placements per patch. Both detail categories and color variation start enabled. Density ranges from 0 to 1, detail size from 0.1 to 5, seed from 0 to 1,000,000, plant limit from 0 to 100,000, and model limit from 0 to 10,000. A limit of zero produces no placements in that category. Limits apply after candidate selection; raising a limit does not create placements beyond the source's reconstructed candidates.

Detail instances are combined by type/material into ordinary child meshes. The child relationship makes them follow terrain transforms. They are not live particle systems or camera-facing billboards. No colliders are created.

## Choosing ground texture resolution

Version 1.0.5 adds 4K, 8K, and 16K choices. Select the patches to change, choose **Bake size**, then run **Apply / Update Terrain**. Existing bakes remain unchanged until Apply; it also regenerates details using the current settings. Different selections can be baked at different sizes. This setting affects ground images, not grass atlases or model-detail textures.

Higher resolution samples the original source textures again; it does not upscale the old bake. Doubling the width creates four times as many pixels, increasing processing time, memory, and potential export size. The float RGBA bake output alone uses 256 MiB at 4096, 1 GiB at 8192, and 4 GiB at 16384. Source textures, temporary arrays, Blender images and packing require additional memory, and images accumulate across patches. Try high resolutions on a small selection first.

There is no single native bake resolution: ground textures repeat across the patch. With the current mapping, a 65-by-65 grid has 32.5 repeats per axis. A 1024-by-1024 source would need about 33,280 pixels across a full-patch bake to retain its source pixel density. Even 16K can therefore be below native density. Actual requirements depend on each source texture's dimensions and patch dimensions; these presets do not promise lossless reproduction of the game's rendering.

When exporting, check the destination's texture import size limit as well: a larger Blender bake can still be downscaled downstream. Existing Bridge material metadata is unchanged.

## Update and restore

Apply regenerates the chosen patches' ground materials and details. It replaces previous tool-owned children rather than accumulating copies. Ground vertex coordinates and faces remain the same; the prepared mesh uses a single baked UV layer. Original UVs and material assignments remain on a retained original mesh datablock.

Restore works on the current scope and reattaches that original mesh. It leaves the object's current placement alone. The backup has a fake user so it survives saving; do not delete or rename it. Manual edits to the generated mesh, materials or details are replaced on update. If preserving custom detail work, make a separate copy outside the managed terrain and remove its `swtor_terrain_generated` ownership property; make shared data single-user before editing it.

Duplicating an already-prepared terrain object also duplicates ownership properties. Independent management of such duplicates is not supported: prefer duplicating/importing clean source terrain, or keep a separate scene backup. Duplicates can otherwise refer to the same backup or generated resources.

## Materials and moving a scene

Ground and detail images are packed into the `.blend`. Save the file to retain them. Materials use Principled BSDF and regular image nodes; grass and supported cutout models use alpha clipping. Baked grass atlases carry their tints so a separate vertex-color shader is unnecessary.

The ground bake occupies UV0. If using an external exporter, include the generated children and check that exporter's image, alpha and two-sided-material handling. This repository contains no external-engine exporter. A valid Blender material does not guarantee automatic shader translation in every destination application.

## Troubleshooting

Open **Text Editor > SWTOR Terrain Report** for the complete run report.

| Report or symptom | Action |
| --- | --- |
| No terrain IDs found | Select original terrain meshes and retain the numeric names or `swtor_id` properties. |
| No matching room / zero patches changed | Check the resources root and extracted room DATs; try a manual override. Ordinary architecture IDs are skipped. |
| Missing `area.dat` | Place the correct area table beside the room DAT. Do not use another planet's table. |
| Conflicting terrain ID | Manually choose the intended room source. Identical duplicated records are accepted; different records are not guessed. |
| Ignored unmapped ground samples | Informational: tiny residual weights or samples wholly outside visible geometry were removed. Valid layers were renormalized. |
| Missing visible material | Extract the listed material/textures. Substantial unmapped visible paint is still an error. |
| Skipped detail / unknown detail channel | The ground may succeed while unsupported or missing details are omitted. Extract listed assets where available. |
| Unsupported grid / shape / triangulation | Use the original extractor topology. Object and parent transforms are supported; sculpting, decimation and alternate diagonals are not. |
| Modifiers warning | Work on a backup; apply or remove modifiers before processing. |
| Detail limit reached | Raise the appropriate per-patch limit or accept a thinner scatter. |
| Detail triangle guard | Reduce density/limits; the guard is 1.5 million estimated detail triangles per patch. |
| Operation too slow / high memory | Process smaller selections, lower bake resolution or density, and disable unnecessary detail types. |
| Unsupported compression | gzip/zlib work without extra installation. Zstandard requires a module available inside Blender's Python; it is not bundled. |
| Transparency error on newer Blender | Use the tested 4.1 version and report the exact version/traceback; later material APIs are not yet ported. |

For a bug report, include add-on/Blender versions, terrain ID, source room basename, settings and the report text. Crop screenshots to relevant details and redact personal filesystem paths. Do not attach an extracted game directory to a public issue.
