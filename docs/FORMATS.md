# Observed format and algorithm notes

These describe the implemented reader, not an official or exhaustive specification. Offsets are byte offsets, integers are little-endian, and strings are length-prefixed UTF-8 with trailing NULs stripped unless stated otherwise. The source code is authoritative where this summary omits a skip layout.

## Room DAT and discovery

The first 28 bytes contain `ROOM_DAT_BINARY_FORMAT_`. A u32 at offset 28 points to the instance block, beginning with a u32 count. Each record starts with marker `0xabcd1234`, then a byte, u64 instance ID, u64 asset ID, a byte, u32 property count, u32 length and a byte. Each property starts with a u8 type and u32 hashed key.

| Type | Payload read/skipped |
| --- | --- |
| 0 | u8 |
| 1, 3 | u32 |
| 4 | f32 |
| 5 | u64 |
| 6 | 3 x f32 |
| 7 | 4 x f32 |
| 8, 9 | u32 byte length, then that many bytes |

Key `0xa3ab26ae` is the compressed VertexData used to identify terrain; `0x4f77e269` is Position. IDs are represented as decimal strings to avoid floating-point precision loss. `room_ids` memory-maps the file and skips property bytes; it does not decompress payloads. Unknown property types stop that room's parse.

## Area DAT

The implemented header check uses bytes 4:28, `AREA_DAT_BINARY_FORMAT_` plus its NUL. U32 pointers at 44, 48 and 52 locate the ground table, detail-name table and detail-parameter table.

- Ground entries: u32 ID, u32 layer/flag (currently skipped), string material name.
- Detail-name entries: u32 ID, string asset name.
- Parameter entries: u32 kind and u32 ID. Kind 0 carries 15 u32 values; kind 2 skips an i32; kind 3 skips the observed string/float/material-record structure. Other kinds are rejected.

The initial Belsavis table had ground IDs 1-23; zero was not a valid material entry. Do not assume IDs are contiguous or subtract one from them.

## Dense heightmap payload

Compression is detected as gzip or Zstandard by magic, otherwise attempted as zlib. Sparse flag bit 8 is rejected; the dense format byte must equal 2. Width and depth are u32 and accepted from 2 through 513.

1. Optional hole/presence bitmap after a u8 flag: ceil(width*depth/8) bytes, MSB-first, x-major. A set bit means a present vertex.
2. Border height pairs as f32, first top/bottom for each x, then left/right for inner z rows.
3. Interior heights: `(width-2)*(depth-2)` u16 values, x-major; height is value/512.
4. U8 texture-channel count, then that many signed i8 IDs. Unused slots can contain -1.
5. Interleaved u8 weights: `(2*width-1)*(2*depth-1)*channels`, reshaped as `[z,x,channel]` and normalized by per-sample sum. Zero-sum samples are rejected.
6. U8 color-map flag. When present: width*depth RGB bytes, x-major; then u8 detail-channel count and repeated u8 channel ID + width*depth density bytes.

Height/tint arrays are transposed into row-z order. Density arrays retain x-major order; mixing those conventions rotates/transposes scatter. Typical 65x65 grids use 129x129 splats and span 12.8 source units at spacing 0.2. The renderer/extractor scene can apply its own scale; fitting accounts for existing geometry instead of imposing another world scale.

The texture bake uses width/2 and depth/2 repeats, matching the validated preview. It blends encoded diffuse colors and multiplies terrain tint. It does not apply arbitrary MAT UV transforms or reconstruct normal/specular layers. Patch-to-patch seam parity across all game areas remains unverified.

## Unmapped layer repair

For each splat sample, sum weights assigned to IDs absent from the area's ground table. Combined unknown mass at most 1/255 is treated as residual. Larger unknown mass is allowed only outside conservative visible support: every surviving terrain cell marks its 3x3 splat neighborhood, including bilinear contributors. This can reject a borderline invisible sample rather than risk discarding visible paint.

Unknown weights are zeroed and remaining weights renormalized. Completely unmapped invisible samples remain zero. Visible samples without a valid material are rejected. This avoids assigning an arbitrary texture to layer 0 and preserves fully mapped bakes unchanged.

## Detail parameters and approximations

Channels below 32 are treated as billboard plants; channels 32 and above as mesh details. This threshold and the following parameter uses describe the observed implementation and need validation for new area formats.

| Word index | Current use |
| --- | --- |
| 0 | Billboard atlas mode (0 single, 1 2x2, 2 2x1); for mesh details, value 1 enables surface-normal alignment |
| 1 | Candidate-density input; empirical divisors differ for cards and meshes |
| 3, 4 | Hue base / variation |
| 5, 6 | Saturation base / variation |
| 7, 8 | Lightness base / variation |
| 10 | Size input; empirical category-specific conversion |
| 11 | Size variation amplitude |
| 12 | Density-related scale attenuation |
| 14 | Mesh orientation mode: 1 randomized Euler, 3 yaw; other values follow the default branch |
| 2, 9, 13 | Not used by this implementation |

A cell's average painted density controls acceptance. The generator uses deterministic integer state, stable hashes and triangle-based height interpolation. Seed, densities and category budgets thin/cap the candidate list. Holes use actual scene triangle visibility. These choices reproduce useful authored distribution, not proven exact game RNG/noise behavior.

Grass is two crossed quads, clipped and two-sided. Up to 16 quantized tint colors are baked into an atlas with two-pixel padding. Atlas modes choose source frames deterministically. Mesh details retain separate material ranges and use geometry with converted axes. Source normals/tangents and model vertex colors are not reconstructed.

## Static GR2 subset

The reader expects magic 1113014599 and version 4.3 or 5.3. Pointer slots are four/eight bytes respectively, with current offsets read from their low u32. Global bone count must be zero. Only LOD 0 meshes are emitted; other LODs, including collision LODs, are skipped.

Positions are f32 triples. UV0 is half-float2 at byte 20 plus four bytes if the color flag is set. Stride checks account for the observed optional UV sets; skin flags and unknown layouts fail. Indices are u16. Material subrecords are 48 bytes with triangle start/count and material index. Bounds checks reject invalid indices/ranges.

This is SWTOR's observed static wrapper/layout, not a general Granny library. The validated model fixtures were 5.3; the 4.3 reader branch needs additional real-world coverage.

## Material subset

MAT XML must provide direct `DiffuseMap`. Opaque materials use alpha 1. `Grass` cutouts use diffuse alpha. `Uber` cutouts use `1 - RotationMap1.red`, with the threshold inverted too. Other cutout families and non-opaque/non-test alpha modes are skipped. Two-sided metadata is honored for models; cards are always two-sided.

Research context and upstream tools are listed in [CREDITS.md](../CREDITS.md). None of their browser/runtime binaries or game fixtures are bundled here.
