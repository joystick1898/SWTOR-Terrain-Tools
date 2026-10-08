# SPDX-License-Identifier: GPL-3.0-or-later
"""SWTOR terrain readers and image math, usable without Blender.

Binary scalars are little-endian. Images use top-down rows; heights use [z,x].
Some disk arrays are x-major and are transposed at the boundary. This reader
supports observed layouts, not all HeroEngine formats. See docs/FORMATS.md.
"""

import struct
import gzip
import zlib
import math
import json
import mmap
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np


class Reader:
    """Checked bytes/mmap cursor; skip avoids copying large embedded payloads."""

    def __init__(self, data, pos=0):
        self.data = data
        self.pos = pos

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("Truncated terrain data at byte " + str(self.pos))
        v = self.data[self.pos : self.pos + n]
        self.pos += n
        return v

    def get(self, fmt):
        v = struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))
        return v[0] if len(v) == 1 else v

    def string(self):
        return self.take(self.get("I")).rstrip(b"\0").decode("utf8")

    def skip(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("Truncated terrain data at byte " + str(self.pos))
        self.pos += n


def room_ids(path):
    """Index terrain IDs without loading/decompressing embedded texture payloads."""
    with Path(path).open("rb") as file:
        if b"ROOM_DAT_BINARY_FORMAT_" not in file.read(28):
            return []
        with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data:
            r = Reader(data, struct.unpack_from("<I", data, 28)[0])
            count = r.get("I")
            ids = []
            for _ in range(count):
                if r.get("I") != 0xABCD1234:
                    raise ValueError("Invalid room instance marker")
                r.skip(1)
                ident = str(r.get("Q"))
                r.skip(9)
                n = r.get("I")
                r.skip(5)
                terrain = False
                for _ in range(n):
                    kind, key = r.get("BI")
                    if kind in (8, 9):
                        size = r.get("I")
                    elif kind in (0, 1, 3, 4, 5, 6, 7):
                        size = {0: 1, 1: 4, 3: 4, 4: 4, 5: 8, 6: 12, 7: 16}[kind]
                    else:
                        raise ValueError("Unsupported room property type " + str(kind))
                    if key == 0xA3AB26AE and size:
                        terrain = True
                    r.skip(size)
                if terrain:
                    ids.append(ident)
            return ids


def discover_rooms(root, wanted, cache_path=None, progress=None):
    """Exact terrain-ID lookup under world/areas; changed files are reindexed."""
    root = Path(root).resolve()
    folder = root / "world/areas"
    wanted = set(wanted)
    if not folder.is_dir():
        raise ValueError(
            "Automatic discovery needs resources/world/areas with the original room DATs. Extract them there, or choose room files manually."
        )
    files = sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() == ".dat" and p.name.lower() != "area.dat"
    )
    cached = {}
    notes = []
    entries = {}
    matches = []
    scanned = 0
    reused = 0
    if cache_path:
        try:
            saved = json.loads(Path(cache_path).read_text())
            if saved.get("version") == 1 and saved.get("root") == str(root):
                cached = saved.get("files", {})
        except (OSError, ValueError, TypeError):
            pass
    for index, path in enumerate(files):
        if progress:
            progress(index, len(files))
        key = path.relative_to(root).as_posix()
        try:
            stat = path.stat()
            stamp = [stat.st_size, stat.st_mtime_ns]
            entry = cached.get(key)
            if not isinstance(entry, dict) or entry.get("stamp") != stamp:
                entry = {"stamp": stamp, "ids": room_ids(path)}
                scanned += 1
            else:
                reused += 1
            entries[key] = entry
            if wanted.intersection(entry["ids"]):
                matches.append(path)
        except (OSError, ValueError, struct.error) as e:
            notes.append("Discovery skipped " + key + ": " + str(e))
    if cache_path:
        try:
            cache_path = Path(cache_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"version": 1, "root": str(root), "files": entries})
            )
            os.replace(temporary, cache_path)
        except OSError as e:
            notes.append(
                "Room index could not be saved; discovery still completed: " + str(e)
            )
    notes.insert(
        0,
        f"Automatic discovery: {len(matches)} matching room files; {scanned} indexed, {reused} cached.",
    )
    if not matches:
        raise ValueError(
            "No matching terrain IDs found under resources/world/areas. Extract the original room DATs and sibling area.dat, or choose room files manually."
        )
    return matches, notes


def area(path):
    """Read ground-ID names, detail-ID names and 15-word channel parameters.

    Header offsets 44/48/52 locate the observed tables. IDs are keys, not list
    indexes. Parameter types 2/3 have skip layouts but are not rendered here.
    """
    data = Path(path).read_bytes()
    if data[4:28] != b"AREA_DAT_BINARY_FORMAT_\0":
        raise ValueError("Unsupported area.dat header")
    result = {"ground": {}, "names": {}, "params": {}}
    for off, key, layer in [(44, "ground", True), (48, "names", False)]:
        r = Reader(data, struct.unpack_from("<I", data, off)[0])
        n = r.get("I")
        if n > 100000:
            raise ValueError("Unreasonable area table count")
        for _ in range(n):
            i = r.get("I")
            if layer:
                r.get("I")
            result[key][i] = r.string()
    r = Reader(data, struct.unpack_from("<I", data, 52)[0])
    n = r.get("I")
    for _ in range(n):
        kind, i = r.get("II")
        if kind == 0:
            result["params"][i] = list(r.get("15I"))
        elif kind == 2:
            r.take(4)
        elif kind == 3:
            r.string()
            r.take(28)
            for _ in range(r.get("I")):
                r.take(8)
                r.string()
                r.take(35)
        else:
            raise ValueError("Unsupported detail parameter type " + str(kind))
    return result


def room(path, wanted=None):
    """Return terrain IDs mapped to compressed VertexData and source positions.

    VertexData hash is 0xa3ab26ae; Position is 0x4f77e269. Placement actually
    comes from existing scene meshes. wanted filters results, not traversal.
    """
    data = Path(path).read_bytes()
    if b"ROOM_DAT_BINARY_FORMAT_" not in data[:28]:
        raise ValueError("Unsupported room DAT header: " + str(path))
    r = Reader(data, struct.unpack_from("<I", data, 28)[0])
    n = r.get("I")
    result = {}
    for _ in range(n):
        if r.get("I") != 0xABCD1234:
            raise ValueError("Invalid room instance marker")
        r.take(1)
        ident = str(r.get("Q"))
        r.get("Q")
        r.take(1)
        count = r.get("I")
        r.get("I")
        r.take(1)
        blob = None
        position = None
        for _ in range(count):
            kind, key = r.get("BI")
            if kind in (8, 9):
                v = r.take(r.get("I"))
            elif kind in (0, 1, 3, 4, 5, 6, 7):
                v = r.get(
                    {0: "B", 1: "I", 3: "I", 4: "f", 5: "Q", 6: "3f", 7: "4f"}[kind]
                )
            else:
                raise ValueError("Unsupported room property type " + str(kind))
            if key == 0xA3AB26AE:
                blob = v
            if key == 0x4F77E269:
                position = v
        if blob and (wanted is None or ident in wanted):
            result[ident] = {"blob": blob, "position": position}
    return result


def decompress(blob):
    """Decode gzip/zlib or optional Zstandard; reject unknown compression."""
    if blob[:2] == b"\x1f\x8b":
        return gzip.decompress(blob)
    if blob[:4] == b"\x28\xb5\x2f\xfd":
        try:
            import zstandard
        except ImportError:
            raise ValueError(
                "Zstandard-compressed terrain requires the optional zstandard Python module; gzip/zlib work without it"
            )
        return zstandard.ZstdDecompressor().decompress(
            blob, max_output_size=128 * 1024 * 1024
        )
    try:
        return zlib.decompress(blob)
    except zlib.error:
        raise ValueError("Unsupported terrain compression")


def patch(blob):
    """Decode dense version-2 terrain into bake/scatter arrays.

    A typical 65x65 grid has 129x129 splat samples. Border heights are floats;
    interior heights are x-major u16/512. IDs are signed bytes (-1 may be an
    unused slot). Density remains x-major; tint/heights become row-z arrays.
    """
    r = Reader(decompress(blob))
    flag = r.get("B")
    w, d = r.get("II")
    if flag & 8:
        raise ValueError(
            "Legacy sparse terrain format is not supported in this release"
        )
    if flag != 2:
        raise ValueError("Unsupported dense terrain version " + str(flag))
    if not 2 <= w <= 513 or not 2 <= d <= 513:
        raise ValueError("Unsupported terrain grid size")
    holes = r.take((w * d + 7) // 8) if r.get("B") else None
    h = np.empty((d, w), np.float32)
    for x in range(w):
        h[0, x], h[-1, x] = r.get("ff")
    for z in range(1, d - 1):
        h[z, 0], h[z, -1] = r.get("ff")
    h[1:-1, 1:-1] = (
        np.frombuffer(r.take((w - 2) * (d - 2) * 2), "<u2").reshape(w - 2, d - 2).T
        / 512
    )
    n = r.get("B")
    if not 1 <= n <= 64:
        raise ValueError("Invalid texture channel count")
    ids = list(struct.unpack("<" + str(n) + "b", r.take(n)))
    weights = (
        np.frombuffer(r.take((2 * w - 1) * (2 * d - 1) * n), np.uint8)
        .reshape(2 * d - 1, 2 * w - 1, n)
        .copy()
    )
    totals = weights.sum(axis=2)
    if np.any(totals == 0):
        raise ValueError("Terrain contains unpainted texture samples")
    weights = weights.astype(np.float32) / totals[..., None]
    color = np.ones((d, w, 3), np.float32)
    channels = {}
    if r.get("B"):
        color = (
            np.frombuffer(r.take(w * d * 3), np.uint8)
            .reshape(w, d, 3)
            .transpose(1, 0, 2)
            .copy()
            / 255
        )
        n = r.get("B")
        if n > 64:
            raise ValueError("Invalid detail channel count")
        for _ in range(n):
            cid = r.get("B")
            density = np.frombuffer(r.take(w * d), np.uint8).copy()
            if density.any():
                channels[cid] = density.tolist()
    # Game Y-up becomes canonical Blender Z-up (x,-z,height). ceil preserves
    # the extractor origin for even-sized grids too.
    xx, zz = np.meshgrid(
        (np.arange(w) - math.ceil((w - 1) / 2)) * 0.2,
        (np.arange(d) - math.ceil((d - 1) / 2)) * 0.2,
    )
    vertices = np.stack((xx, -zz, h), axis=2).reshape(-1, 3)
    return dict(
        width=w,
        depth=d,
        heights=h,
        vertices=vertices,
        ids=ids,
        weights=weights,
        color=color,
        channels=channels,
        holes=holes,
    )


def resource(root, ref):
    """Resolve resource/# references, enforcing containment and tolerant casing.

    Resolve before containment checks, so escaping symlinks/traversal fail.
    """
    ref = ref.replace("\\", "/").lstrip("/")
    if ref.startswith("#"):
        ref = "art/defaultassets/" + ref[1:]
    if ref.lower().startswith("resources/"):
        ref = ref[10:]
    root = Path(root).resolve()
    p = (root / ref).resolve()
    if not p.is_relative_to(root):
        raise ValueError("Resource path is outside the resources folder")
    if p.exists():
        return p
    # Linux/macOS case-sensitive filesystems; Windows usually resolves directly.
    p = root
    for part in Path(ref).parts:
        if not p.is_dir():
            raise FileNotFoundError(ref)
        matches = [c for c in p.iterdir() if c.name.lower() == part.lower()]
        if len(matches) != 1:
            raise FileNotFoundError(ref)
        p = matches[0]
    return p


def material(root, name):
    """Read direct diffuse/cutout MAT inputs, not inherited shader graphs."""
    node = ET.parse(resource(root, "art/shaders/materials/" + name + ".mat")).getroot()
    inputs = {
        x.findtext("semantic"): x.findtext("value") for x in node.findall("input")
    }
    diffuse = inputs.get("DiffuseMap")
    if not diffuse:
        raise ValueError("No direct DiffuseMap in " + name)
    return dict(
        name=name,
        shader=node.findtext("Derived"),
        diffuse=diffuse,
        rotation=inputs.get("RotationMap1"),
        alpha=node.findtext("AlphaMode") or "None",
        cutoff=float(node.findtext("AlphaTestValue") or 0.5),
        two_sided=node.findtext("IsTwoSided") == "True",
    )


def sample(a, u, v, repeat=False):
    """Bilinear sample scalar/RGB(A) arrays at compatible UV arrays.

    Repeat uses texel centers; clamp maps endpoints to edge samples. Scalar
    inputs gain a trailing singleton channel for vectorized blending.
    """
    h, w = a.shape[:2]
    xx = u * w - 0.5 if repeat else u * (w - 1)
    yy = v * h - 0.5 if repeat else v * (h - 1)
    ix = np.floor(xx).astype(int)
    iy = np.floor(yy).astype(int)
    fx = (xx - ix)[..., None]
    fy = (yy - iy)[..., None]
    if a.ndim == 2:
        a = a[..., None]
    if repeat:
        x0 = ix % w
        x1 = (ix + 1) % w
        y0 = iy % h
        y1 = (iy + 1) % h
    else:
        x0 = ix.clip(0, w - 1)
        x1 = (ix + 1).clip(0, w - 1)
        y0 = iy.clip(0, h - 1)
        y1 = (iy + 1).clip(0, h - 1)
    return (a[y0, x0] * (1 - fx) + a[y0, x1] * fx) * (1 - fy) + (
        a[y1, x0] * (1 - fx) + a[y1, x1] * fx
    ) * fy


def source_triangles(p):
    """Return [z,x,2] triangle visibility from an MSB-first x-major bitmap.

    Set bits mean present vertices. The extractor uses the anti-diagonal
    between top-right and bottom-left vertices within each cell.
    """
    w, d = p["width"], p["depth"]
    valid = (
        np.ones((d, w), bool)
        if p["holes"] is None
        else np.unpackbits(np.frombuffer(p["holes"], np.uint8))[: w * d]
        .reshape(w, d)
        .T.astype(bool)
    )
    common = valid[:-1, 1:] & valid[1:, :-1]
    return np.stack((common & valid[:-1, :-1], common & valid[1:, 1:]), axis=2)


def ground_weights(p, table, allowed=None, repair_unmapped=False):
    """Remove tolerable unknown weights; return (weights, diagnostic notes).

    Real fixtures contain layer-0 residuals <=1/255 and a strong sample inside
    a hole. Reject combined unknown mass above 1/255 on visible support, never
    guess a replacement texture. Actual scene triangles override source holes.
    Return fully mapped input unchanged to preserve existing bakes. Optional
    layer-0 repair approximates missing blends and always reports that choice.
    """
    weights = p["weights"]
    known = np.array([tid in table for tid in p["ids"]], bool)
    unknown = weights[:, :, ~known].sum(axis=2)
    if not np.any(unknown):
        return weights, []
    if allowed is None:
        allowed = source_triangles(p)
    # Conservatively cover all 3x3 splat samples touching any present triangle.
    # Bilinear samples outside this support cannot contribute to visible terrain.
    visible = np.zeros(weights.shape[:2], bool)
    cells = allowed.any(axis=2)
    for dz in range(3):
        for dx in range(3):
            visible[
                dz : dz + 2 * cells.shape[0] : 2, dx : dx + 2 * cells.shape[1] : 2
            ] |= cells
    significant = unknown > 1 / 255 + 1e-8
    repair = bool(repair_unmapped and np.any(significant & visible))
    if np.any(significant & visible):
        ids = sorted(
            {
                tid
                for i, tid in enumerate(p["ids"])
                if not known[i] and np.any(weights[:, :, i][significant & visible])
            }
        )
        if not repair or ids != [0]:
            raise ValueError(
                "No area material mapping for visible ground layer(s) "
                + ", ".join(map(str, ids))
                + "; weight exceeds the 1/255 residual tolerance"
            )
    result = weights.copy()
    result[:, :, ~known] = 0
    total = result.sum(axis=2)
    if repair:
        # Layer 0 has no source material. With explicit user consent, preserve
        # all available mapped proportions and extend them into empty samples.
        # Synchronous four-neighbor waves average equally distant boundaries;
        # never wrap across patch edges or invent a new material ID.
        valid = total > 0
        if not valid.any():
            raise ValueError("Cannot repair terrain without any mapped ground samples")
        np.divide(result, total[:, :, None], out=result, where=valid[:, :, None])
        while not valid.all():
            sums = np.zeros_like(result)
            counts = np.zeros(valid.shape, np.int32)
            for dst, src in (
                ((slice(1, None), slice(None)), (slice(None, -1), slice(None))),
                ((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                ((slice(None), slice(1, None)), (slice(None), slice(None, -1))),
                ((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
            ):
                sums[dst] += result[src] * valid[src][..., None]
                counts[dst] += valid[src]
            fill = ~valid & (counts > 0)
            result[fill] = sums[fill] / counts[fill, None]
            valid[fill] = True
        return result, [
            f"REPAIRED unmapped layer 0: {int(np.count_nonzero(significant & visible))} significant samples on visible terrain; used surrounding mapped blends. This is an approximation, not recovered source texture data."
        ]
    if np.any((total <= 0) & visible):
        raise ValueError("Visible terrain has no mapped ground material")
    np.divide(result, total[:, :, None], out=result, where=total[:, :, None] > 0)
    residual = int(np.count_nonzero((unknown > 0) & ~significant))
    hidden = int(np.count_nonzero(significant))
    return result, [
        f"Ignored unmapped ground samples: {residual} residuals (at most 1/255), {hidden} inside absent terrain; remaining weights renormalized."
    ]


def bake(
    p,
    table,
    read_diffuse,
    resolution,
    allowed=None,
    warnings=None,
    repair_unmapped=False,
):
    """Blend encoded diffuse arrays and tint into a square top-down RGBA bake.

    read_diffuse(name) supplies source pixels. Tiling width/2, depth/2 matches
    the tested preview (32.5 repeats on 65x65), not every possible MAT setting.
    No normal/specular bake or linear-light blend is performed.
    """
    weights, notes = ground_weights(p, table, allowed, repair_unmapped)
    if warnings is not None:
        warnings.extend(notes)
    q = (np.arange(resolution, dtype=np.float32) + 0.5) / resolution
    out = np.zeros((resolution, resolution, 4), np.float32)
    out[:, :, 3] = 1
    layers = []
    for i, tid in enumerate(p["ids"]):
        if not weights[:, :, i].any():
            continue
        if tid not in table:
            raise ValueError("No area material mapping for ground layer " + str(tid))
        tex = read_diffuse(table[tid])[:, :, :3]
        layers.append((i, tex))
    # Keep the original global coordinates, dtype, layer order and arithmetic.
    # Only temporary array sizes change; strip boundaries introduce no seams.
    for start in range(0, resolution, 64):
        u, v = np.meshgrid(q, q[start : start + 64])
        part = out[start : start + 64, :, :3]
        for i, tex in layers:
            part += sample(tex, u * p["width"] / 2, v * p["depth"] / 2, True) * sample(
                weights[:, :, i], u, v
            )
        part *= sample(p["color"], u, v)
    return np.clip(out, 0, 1, out=out)


def gr2(path):
    """Read observed static SWTOR GR2 4.3/5.3 LOD0 submeshes, not general Granny.

    Reject skinned/unknown strides; read positions and half-float UV0, skipping
    packed normals/tangents. Submesh start/count values are triangle units;
    indices are u16. Separate material ranges remain separate submeshes.
    """
    b = Path(path).read_bytes()
    r = Reader(b)
    magic, version, minor = r.get("III")
    if magic != 1113014599 or version not in (4, 5) or minor != 3:
        raise ValueError("Unsupported GR2 format")

    def u32(off):
        return struct.unpack_from("<I", b, off)[0]

    def text(off):
        return b[off : b.index(0, off)].decode()

    ptr = 8 if version == 5 else 4
    nm, nmat, bones = struct.unpack_from("<HHH", b, 24)
    if bones:
        raise ValueError("Skinned detail GR2 is unsupported")
    mp = u32(96 if version == 5 else 88)
    mats = [text(u32(mp + i * ptr)) for i in range(nmat)]
    r.pos = u32(88 if version == 5 else 84)
    meshes = []
    for _ in range(nm):
        name = text(r.get("I"))
        r.take(ptr - 4)
        lod, flag, ns, nb = r.get("hHHH")
        flags, stride = r.get("II" if version == 5 else "HH")
        nv, ni = r.get("II")
        offsets = []
        for j in range(4):
            offsets.append(r.get("I"))
            r.take(ptr - 4)
        if lod != 0:
            continue
        if flags & 256 or flags & 35 != 35:
            raise ValueError("Unsupported static GR2 vertex attributes")
        uv_offset = 20 + (4 if flags & 16 else 0)
        expected = uv_offset + 4 + (4 if flags & 64 else 0) + (4 if flags & 128 else 0)
        if stride != expected:
            raise ValueError("Unsupported GR2 vertex stride")
        vb, sm, ib, bo = offsets
        vertices = [struct.unpack_from("<fff", b, vb + i * stride) for i in range(nv)]
        uvs = [
            struct.unpack_from("<ee", b, vb + i * stride + uv_offset) for i in range(nv)
        ]
        inds = struct.unpack_from("<" + str(ni) + "H", b, ib)
        if inds and max(inds) >= nv:
            raise ValueError("GR2 index out of range")
        for j in range(ns):
            start, count, mi, group = struct.unpack_from("<IIii", b, sm + j * 48)
            if not 0 <= mi < len(mats):
                raise ValueError("GR2 material index out of range")
            idx = inds[start * 3 : (start + count) * 3]
            if len(idx) != count * 3:
                raise ValueError("GR2 submesh range is invalid")
            meshes.append(
                dict(
                    name=name,
                    vertices=vertices,
                    uvs=uvs,
                    faces=[idx[k : k + 3] for k in range(0, len(idx), 3)],
                    material=mats[mi],
                )
            )
    if not meshes:
        raise ValueError("GR2 has no static LOD0 submeshes")
    return meshes
