# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender scene adapter, generated materials, and terrain sidebar.

core handles formats/image arrays; details chooses placements. This module owns
the stage/commit/restore lifecycle. Saved property identifiers are an API for
existing .blend files; keep them stable when reorganizing the implementation.
"""

bl_info = {
    "name": "SWTOR Terrain Tools",
    "author": "SWTOR Terrain Tools contributors",
    "version": (1, 0, 5),
    "blender": (4, 1, 0),
    "location": "3D View > Sidebar > SWTOR Terrain",
    "category": "Import-Export",
}
import math
import re
import uuid
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector, Euler
from bpy.props import (
    StringProperty,
    FloatProperty,
    IntProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
)
from bpy_extras.io_utils import ImportHelper
from . import core, details

# Private build ownership token, not a display name or source terrain ID.
TAG = "swtor_terrain_generated"


def pixels(path):
    """Decode DDS to top-down encoded RGBA samples, without gamma conversion.

    CHANNEL_PACKED prevents premultiplication. Remove the temporary Blender
    image even on failure; cached NumPy arrays belong to Assets instead.
    """
    im = bpy.data.images.load(str(path), check_existing=False)
    try:
        im.colorspace_settings.name = "Non-Color"
        im.alpha_mode = "CHANNEL_PACKED"
        w, h = im.size
        if not w or not h:
            raise ValueError("Cannot decode " + str(path))
        a = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(a)
        return a.reshape(h, w, 4)[::-1].copy()
    finally:
        bpy.data.images.remove(im)


def texture_path(root, ref):
    """Resolve a MAT texture reference, appending its often-omitted DDS suffix."""
    return core.resource(root, ref if ref.lower().endswith(".dds") else ref + ".dds")


class Assets:
    """Per-Apply source cache; extracted resources are never modified.

    Cached arrays are read-only by convention. albedo() copies before replacing
    opacity, so one shader's conversion cannot change another material's input.
    """

    def __init__(self, root):
        self.root = root
        self.mats = {}
        self.images = {}
        self.models = {}
        self.albedos = {}

    def mat(self, name):
        if name not in self.mats:
            self.mats[name] = core.material(self.root, name)
        return self.mats[name]

    def texture(self, ref):
        if ref not in self.images:
            self.images[ref] = pixels(texture_path(self.root, ref))
        return self.images[ref]

    def diffuse(self, name):
        return self.texture(self.mat(name)["diffuse"])

    def albedo(self, name):
        """Return diffuse RGBA and metadata for supported detail shaders.

        Uber cutouts use inverse RotationMap1 red; Grass uses diffuse alpha.
        Unsupported blend modes are rejected, not approximated as opaque.
        """
        if name in self.albedos:
            a, m = self.albedos[name]
            return a, dict(m)
        m = dict(self.mat(name))
        a = self.diffuse(name).copy()
        if m["alpha"] not in ("None", "Test"):
            raise ValueError(
                "Unsupported detail alpha mode " + m["alpha"] + " on " + name
            )
        if m["alpha"] == "Test" and m["shader"] == "Uber":
            if not m["rotation"]:
                raise ValueError("Cutout Uber material has no RotationMap1: " + name)
            opacity = 1 - self.texture(m["rotation"])[:, :, 0]
            q = (np.arange(a.shape[1]) + 0.5) / a.shape[1]
            v = (np.arange(a.shape[0]) + 0.5) / a.shape[0]
            u, v = np.meshgrid(q, v)
            a[:, :, 3] = core.sample(opacity, u, v)[:, :, 0]
            # SWTOR's inverse opacity threshold must be inverted with the mask,
            # so the comparison uses opacity rather than transparency.
            m["cutoff"] = 1 - m["cutoff"]
        elif m["alpha"] == "None":
            a[:, :, 3] = 1
        elif m["shader"] != "Grass":
            raise ValueError("Unsupported cutout detail shader " + str(m["shader"]))
        # Consumers only read this array (palette_atlas copies its frames).
        # Make accidental mutation fail rather than corrupt later patches.
        a.flags.writeable = False
        self.albedos[name] = (a, dict(m))
        return a, m

    def model(self, path):
        if path not in self.models:
            self.models[path] = core.gr2(core.resource(self.root, path))
        return self.models[path]


def fit_grid(obj, p):
    """Fit source to existing object-local geometry without moving vertices.

    Return (coef, inverse, allowed): [x,y,z,1] @ coef transforms source points;
    inverse maps mesh vertex indices to original grid indices; allowed[z,x,2]
    records surviving triangles. Object/parent transforms remain untouched.
    Grid UVs recover correspondence when OBJ import drops vertices at holes.
    Reject edited/ambiguous geometry instead of guessing texture placement.
    """
    w, d = p["width"], p["depth"]
    n = w * d
    nv = len(obj.data.vertices)
    if not 3 <= nv <= n:
        raise ValueError("Terrain topology is not a supported heightmap grid")
    actual = np.empty(nv * 3, np.float64)
    obj.data.vertices.foreach_get("co", actual)
    actual = actual.reshape(nv, 3)
    canonical = p["vertices"]
    design = np.column_stack((canonical, np.ones(n)))
    inverse = np.arange(nv)

    def fit(inverse):
        selected = design[inverse]
        coef, _, rank, _ = np.linalg.lstsq(selected, actual, rcond=None)
        error = np.max(np.linalg.norm(selected @ coef - actual, axis=1))
        return coef, rank, error

    coef, rank, error = fit(inverse)
    extent = max(np.linalg.norm(np.ptp(actual, axis=0)), 0.001)
    if nv != n:
        error = float("inf")
    if error > extent * 0.0002 and obj.data.uv_layers:
        uv = np.empty(len(obj.data.loops) * 2, np.float64)
        obj.data.uv_layers[0].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        m = np.full(nv, -1, int)
        for loop, (u, v) in zip(obj.data.loops, uv):
            vertex = loop.vertex_index
            if obj.data.uv_layers[0].name == "SWTOR Terrain Bake":
                v = 1 - v
            j = int(round(u * (w - 1)))
            k = int(round(v * (d - 1)))
            if (
                0 <= j < w
                and 0 <= k < d
                and abs(u * (w - 1) - j) < 0.01
                and abs(v * (d - 1) - k) < 0.01
            ):
                grid = k * w + j
                if m[vertex] not in (-1, grid):
                    raise ValueError("Terrain UVs disagree across shared vertices")
                m[vertex] = grid
        if np.all(m >= 0) and len(set(m)) == nv:
            inverse = m
            coef, rank, error = fit(inverse)
    if error > extent * 0.0002:
        raise ValueError(
            "Terrain vertex order/shape does not match source; cannot safely align textures"
        )
    if rank < 4:
        # Flat grid: use its oriented surface normal to recover the missing axis.
        axis = np.cross(coef[0, :], coef[1, :])
        length = np.linalg.norm(axis)
        if length < 1e-10:
            raise ValueError("Degenerate terrain transform")
        z = axis / length * math.sqrt(length)
        old = coef[2].copy()
        coef[2] = z
        coef[3] += (old - z) * float(np.mean(canonical[inverse, 2]))
    linear = coef[:3].T
    if abs(np.linalg.det(linear)) < 1e-12:
        raise ValueError("Terrain transform is singular")
    allowed = np.zeros((d - 1, w - 1, 2), bool)
    obj.data.calc_loop_triangles()
    for triangle in obj.data.loop_triangles:
        ids = set(int(inverse[i]) for i in triangle.vertices)
        j = min(i % w for i in ids)
        k = min(i // w for i in ids)
        if j >= w - 1 or k >= d - 1:
            continue
        a = k * w + j
        if ids == {a, a + 1, a + w}:
            allowed[k, j, 0] = True
        elif ids == {a + 1, a + w, a + w + 1}:
            allowed[k, j, 1] = True
        else:
            raise ValueError(
                "Terrain triangulation differs from the supported STE heightmap grid"
            )
    if not allowed.any():
        raise ValueError("Terrain has no supported triangles")
    return coef, inverse, allowed


def image_material(name, array, owner, cutout=False, cutoff=0.5, two_sided=False):
    """Create a packed image and standard Principled material.

    Pack encoded color while Non-Color, then mark the stored image sRGB for
    display. That order avoids double gamma and must survive pixel tests.
    """
    h, w = array.shape[:2]
    im = bpy.data.images.new(name + " Color", width=w, height=h, alpha=True)
    im[TAG] = owner
    im["stt_label"] = (name + " Color")[:63]
    im.colorspace_settings.name = "Non-Color"
    im.alpha_mode = "CHANNEL_PACKED"
    im.pixels.foreach_set(np.asarray(array[::-1], np.float32).ravel())
    im.pack()
    # Image encoded values are sRGB color; changing interpretation does not rewrite pixels.
    im.colorspace_settings.name = "sRGB"
    mat = bpy.data.materials.new(name)
    mat[TAG] = owner
    mat["stt_label"] = name[:63]
    mat.use_nodes = True
    mat.use_backface_culling = not two_sided
    mat.blend_method = "CLIP" if cutout else "OPAQUE"
    mat.alpha_threshold = cutoff
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = im
    links.new(tex.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 1
    if cutout:
        clip = nodes.new("ShaderNodeMath")
        clip.operation = "GREATER_THAN"
        clip.inputs[1].default_value = cutoff
        links.new(tex.outputs["Alpha"], clip.inputs[0])
        links.new(clip.outputs[0], shader.inputs["Alpha"])
    # Optional exporter metadata; no external exporter is required or imported.
    mat["stt_generated_version"] = 1
    mat["stt_albedo_image"] = im.name
    mat["stt_cutout"] = cutout
    mat["stt_cutoff"] = cutoff
    mat["stt_two_sided"] = two_sided
    return mat


def palette_atlas(array, plants, params):
    """Bake up to 16 quantized plant tints and source frames into a padded atlas.

    Return atlas RGBA, per-placement Blender UV rectangles, and card aspect.
    Observed frame modes 1/2 mean 2x2/2x1 source layouts, respectively.
    """
    # Bake tint into the atlas so exported meshes need no vertex-color shader.
    colors = np.array([p[7] for p in plants], np.float32)
    rounded = np.round(colors * 8) / 8
    unique, count = np.unique(rounded, axis=0, return_counts=True)
    palette = unique[np.argsort(-count)[:16]]
    if not len(palette):
        palette = np.ones((1, 3))
    h, w = array.shape[:2]
    columns = 4
    rows = math.ceil(len(palette) / columns)
    pad = 2
    # Frame support for source 2x2 or 2x1 grass atlases.
    sx = 2 if params[0] in (1, 2) else 1
    sy = 2 if params[0] == 1 else 1
    fw, fh = w // sx, h // sy
    entries = len(palette) * sx * sy
    columns = math.ceil(math.sqrt(entries))
    rows = math.ceil(entries / columns)
    tw, th = fw + 2 * pad, fh + 2 * pad
    atlas = np.zeros((rows * th, columns * tw, 4), np.float32)
    for pi, color in enumerate(palette):
        for frame in range(sx * sy):
            index = pi * sx * sy + frame
            x = index % columns * tw
            y = index // columns * th
            a = array[
                (frame // sx) * fh : (frame // sx + 1) * fh,
                (frame % sx) * fw : (frame % sx + 1) * fw,
            ].copy()
            a[:, :, :3] *= color
            atlas[y : y + th, x : x + tw] = np.pad(
                a, ((pad, pad), (pad, pad), (0, 0)), mode="edge"
            )
    choices = np.argmin(
        np.sum((colors[:, None, :] - palette[None, :, :]) ** 2, axis=2), axis=1
    )
    rects = []
    for i, p in enumerate(plants):
        frame = int(details.unit_hash(27, int(p[0] * 2**32)) * sx * sy)
        index = int(choices[i]) * sx * sy + frame
        x = index % columns * tw + pad
        y = index // columns * th + pad
        rects.append(
            (
                x / atlas.shape[1],
                1 - (y + fh) / atlas.shape[0],
                fw / atlas.shape[1],
                fh / atlas.shape[0],
            )
        )
    return atlas, rects, fw / fh


def mesh_object(name, verts, faces, uvs, mat, collection, parent, owner):
    """Create a tagged child using parent-local positions and per-loop UVs.

    Identity child transforms make details follow later terrain transforms.
    """
    mesh = bpy.data.meshes.new(name)
    mesh[TAG] = owner
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.uv_layers.new(name="UVMap").data.foreach_set(
        "uv", np.asarray(uvs, np.float32).ravel()
    )
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.parent = parent
    obj[TAG] = owner
    return obj


def cleanup(owner, keep=()):
    """Delete owned objects, then unused meshes/materials/images in that order.

    Keep unrelated data and owned datablocks that still have other users.
    """
    keep = set(keep)
    for obj in list(bpy.data.objects):
        if obj.get(TAG) == owner and obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for block in list(blocks):
            if block.get(TAG) == owner and block.users == 0:
                blocks.remove(block)


def apply_one(obj, ident, p, table, assets, settings, warnings):
    """Stage and commit one patch; return its generated detail-instance count.

    Ground errors stop this patch. Missing/unsupported detail assets become
    warnings so valid ground and detail types can still succeed. Build the new
    owner-tagged data before swapping obj.data; clean staging on pre-commit
    failure. This is per-patch staging, not a whole-scene transaction.
    """
    if obj.library or obj.data.library:
        raise ValueError("Make linked terrain local first")
    if obj.modifiers:
        raise ValueError("Apply or remove terrain modifiers before texturing")
    coef, inverse, allowed = fit_grid(obj, p)
    bake_notes = []
    color = core.bake(
        p,
        table["ground"],
        assets.diffuse,
        int(settings.resolution),
        allowed,
        bake_notes,
        repair_unmapped=settings.repair_unmapped,
    )
    warnings.extend(ident + ": " + note for note in bake_notes)
    config = dict(width=p["width"], depth=p["depth"], allowed=allowed, channels=[])
    for cid, density in p["channels"].items():
        is_mesh = cid >= 32
        if (is_mesh and not settings.models) or (not is_mesh and not settings.grass):
            continue
        name = table["names"].get(cid)
        params = table["params"].get(cid)
        if any(t.name == name and not t.enabled for t in settings.types):
            continue
        if not name or not params:
            warnings.append(ident + ": unresolved detail channel " + str(cid))
            continue
        try:
            if is_mesh:
                geometry = assets.model(name)
                for submesh in geometry:
                    assets.albedo(submesh["material"])
            else:
                geometry = None
                assets.albedo(name)
            config["channels"].append(
                dict(
                    id=cid,
                    name=name,
                    kind="mesh" if is_mesh else "billboard",
                    parameters=params,
                    density_x_major=density,
                    geometry=geometry,
                )
            )
        except Exception as e:
            warnings.append(ident + ": skipped detail " + str(cid) + ": " + str(e))

    class Proxy:
        def __getattr__(self, name):
            return True if name.startswith("channel_") else getattr(settings, name)

    placements, capped = details.candidates(config, p["heights"].ravel(), Proxy())
    if capped:
        warnings.append(ident + ": detail limit reached")
    groups = {}
    for placement in placements:
        groups.setdefault(placement[1], []).append(placement)
    estimated = sum(
        (sum(len(g["faces"]) for g in c["geometry"]) if c["kind"] == "mesh" else 4)
        * len(groups.get(c["id"], ()))
        for c in config["channels"]
    )
    if estimated > 1500000:
        raise ValueError(
            "Detail geometry exceeds 1.5 million triangles on one patch; reduce density/limits"
        )
    owner = uuid.uuid4().hex
    created = []
    created_materials = []
    ground_mesh = None
    collection = (
        obj.users_collection[0]
        if obj.users_collection
        else bpy.context.scene.collection
    )
    try:
        mat = image_material("Terrain " + ident, color, owner)
        created_materials.append(mat)
        mat["stt_kind"] = "ground"
        ground_mesh = obj.data.copy()
        ground_mesh[TAG] = owner
        ground_mesh.name = "Terrain " + ident
        ground_mesh.materials.clear()
        ground_mesh.materials.append(mat)
        for layer in list(ground_mesh.uv_layers):
            ground_mesh.uv_layers.remove(layer)
        uv = ground_mesh.uv_layers.new(name="SWTOR Terrain Bake")
        ground_mesh.uv_layers.active = uv
        uv.active_render = True
        coords = np.array(
            [
                (
                    int(inverse[l.vertex_index]) % p["width"] / (p["width"] - 1),
                    1 - int(inverse[l.vertex_index]) // p["width"] / (p["depth"] - 1),
                )
                for l in ground_mesh.loops
            ],
            np.float32,
        )
        uv.data.foreach_set("uv", coords.ravel())

        def local(v):
            return tuple(np.append(v, 1) @ coef)

        for ch in config["channels"]:
            group = groups.get(ch["id"], ())
            if not group:
                continue
            if ch["kind"] == "billboard":
                arr, source = assets.albedo(ch["name"])
                atlas, rects, aspect = palette_atlas(arr, group, ch["parameters"])
                material = image_material(
                    "STT " + ident + " " + ch["name"][:35],
                    atlas,
                    owner,
                    True,
                    source["cutoff"],
                    True,
                )
                verts = []
                created_materials.append(material)
                faces = []
                uvs = []
                for pl, rect in zip(group, rects):
                    rank, cid, x, y, z, scale, angle, rgb, flip, normal = pl
                    height = 1.8 * scale
                    half = height * aspect / 2
                    u, v, du, dv = rect
                    for theta in (angle, angle + math.pi / 2):
                        dx, dy = math.cos(theta) * half, math.sin(theta) * half
                        start = len(verts)
                        verts.extend(
                            local(q)
                            for q in (
                                (x - dx, y - dy, z),
                                (x + dx, y + dy, z),
                                (x + dx, y + dy, z + height),
                                (x - dx, y - dy, z + height),
                            )
                        )
                        faces.append((start, start + 1, start + 2, start + 3))
                        u0, u1 = (u + du, u) if flip else (u, u + du)
                        uvs.extend(((u0, v), (u1, v), (u1, v + dv), (u0, v + dv)))
                child = mesh_object(
                    "Grass " + ch["name"],
                    verts,
                    faces,
                    uvs,
                    material,
                    collection,
                    obj,
                    owner,
                )
                child["stt_instances"] = len(group)
                created.append(child)
            else:
                for geo in ch["geometry"]:
                    arr, source = assets.albedo(geo["material"])
                    material = image_material(
                        "STT " + ident + " " + geo["material"][:35],
                        arr,
                        owner,
                        source["alpha"] == "Test",
                        source["cutoff"],
                        source["two_sided"],
                    )
                    verts = []
                    created_materials.append(material)
                    faces = []
                    uvs = []
                    baseverts = [Vector((x, -z, y)) for x, y, z in geo["vertices"]]
                    for rank, cid, x, y, z, scale, angle, rgb, flip, normal in group:
                        if ch["parameters"][14] == 1:
                            rot = Euler(
                                (
                                    details.unit_hash(11, int(angle * 1000000))
                                    * math.tau,
                                    details.unit_hash(29, int(angle * 1000000))
                                    * math.tau,
                                    angle,
                                ),
                                "ZXY",
                            ).to_matrix()
                        else:
                            rot = (
                                Vector((0, 0, 1))
                                .rotation_difference(Vector(normal))
                                .to_matrix()
                                if ch["parameters"][0] == 1
                                else Matrix.Identity(3)
                            )
                            if ch["parameters"][14] == 3:
                                rot = rot @ Matrix.Rotation(angle, 3, "Z")
                        start = len(verts)
                        verts.extend(
                            local(Vector((x, y, z)) + rot @ (v * scale))
                            for v in baseverts
                        )
                        for face in geo["faces"]:
                            faces.append(tuple(start + i for i in face))
                            uvs.extend(
                                (geo["uvs"][i][0], 1 - geo["uvs"][i][1]) for i in face
                            )
                    child = mesh_object(
                        "Detail " + geo["name"],
                        verts,
                        faces,
                        uvs,
                        material,
                        collection,
                        obj,
                        owner,
                    )
                    child["stt_instances"] = len(group)
                    created.append(child)
        # Commit only after the whole patch is built. Keep the original mesh for Restore.
        old_owner = obj.get("stt_owner")
        previous = obj.data
        if "stt_original_mesh" not in obj:
            previous.use_fake_user = True
            obj["stt_original_mesh"] = previous.name
        obj.data = ground_mesh
        obj["stt_owner"] = owner
        obj["stt_instance_id"] = ident
        if old_owner:
            cleanup(old_owner)
        # Match Blender datablock iteration order to preserve name suffixes.
        images = [
            n.image
            for m in created_materials
            for n in m.node_tree.nodes
            if n.type == "TEX_IMAGE"
        ]
        for blocks in (images, created_materials):
            for block in sorted(blocks, key=lambda b: b.name):
                if block.get(TAG) == owner and block.get("stt_label"):
                    block.name = block["stt_label"]
        for material in created_materials:
            if material.get(TAG) == owner:
                material["stt_albedo_image"] = next(
                    n.image.name
                    for n in material.node_tree.nodes
                    if n.type == "TEX_IMAGE"
                )
        for child in created:
            if old_owner:
                # Blender adds suffixes during staging; readable names are retained.
                child.name = re.sub(r"\.\d{3}$", "", child.name)
        return len(placements)
    except Exception:
        cleanup(owner)
        raise


def object_id(obj):
    """Find the 17-20 digit source ID on this object or its ancestor chain."""
    chain = []
    o = obj
    while o is not None:
        chain.append(o)
        o = o.parent
    for o in chain:
        for value in (o.get("stt_instance_id", ""), o.get("swtor_id", ""), o.name):
            m = re.search(r"(?<!\d)(\d{17,20})(?!\d)", str(value))
            if m:
                return m.group(1)
    return None


def targets(context, settings):
    """Collect candidate meshes in scope, excluding generated detail children.

    Room lookup filters ordinary architecture IDs from these candidates later.
    """
    if settings.scope == "SELECTED":
        objects = set(context.selected_objects)
    elif settings.scope == "COLLECTION":
        objects = set(context.view_layer.active_layer_collection.collection.all_objects)
    else:
        objects = set(context.scene.objects)
    return [
        (o, object_id(o))
        for o in objects
        if o.type == "MESH" and not o.get(TAG) and object_id(o)
    ]


def resolve_rooms(settings, root, wanted=None, messages=None, progress=None):
    """Use explicit room overrides or discover exact IDs under resources.

    JSON is a filename hint; binary terrain data still comes from room DATs.
    Cache metadata lives in Blender's config directory, never the game tree.
    """
    paths = []
    for entry in settings.sources:
        p = Path(bpy.path.abspath(entry.path)).resolve()
        if p.suffix.lower() == ".json":
            sibling = p.with_suffix(".dat")
            if sibling.is_file():
                p = sibling
            else:
                matches = list((root / "world/areas").rglob(p.stem + ".dat"))
                if len(matches) != 1:
                    raise ValueError(
                        "JSON "
                        + p.name
                        + " needs a unique matching room DAT. Add that DAT directly."
                    )
                p = matches[0]
        if p.name.lower() == "area.dat":
            raise ValueError(
                "Add room DAT files, not area.dat; the area table is loaded automatically"
            )
        if not p.is_file():
            raise FileNotFoundError(str(p))
        paths.append(p)
    if not paths:
        cache = (
            Path(
                bpy.utils.user_resource(
                    "CONFIG", path="swtor_terrain_tools", create=True
                )
            )
            / "room-index.json"
        )
        paths, notes = core.discover_rooms(root, wanted or set(), cache, progress)
        if messages is not None:
            messages.extend(notes)
    return list(dict.fromkeys(paths))


class Source(bpy.types.PropertyGroup):
    """One optional room override persisted in the .blend."""

    path: StringProperty()


class DetailType(bpy.types.PropertyGroup):
    """Per-asset toggle shared by matching names across source rooms."""

    name: StringProperty()
    enabled: BoolProperty(default=True)


class Settings(bpy.types.PropertyGroup):
    """Scene settings; identifiers and defaults form a saved-file interface."""

    types: CollectionProperty(type=DetailType)
    show_types: BoolProperty(name="Individual detail types", default=False)
    resources: StringProperty(name="SWTOR resources", subtype="DIR_PATH")
    sources: CollectionProperty(type=Source)
    scope: EnumProperty(
        name="Apply to",
        items=[
            ("SELECTED", "Selected terrain", ""),
            ("COLLECTION", "Active collection", ""),
            ("SCENE", "All matching terrain", ""),
        ],
        default="SELECTED",
    )
    resolution: EnumProperty(
        name="Bake size",
        description="Ground texture dimensions per patch; higher sizes retain more source detail",
        items=[
            ("512", "512", "512 x 512 pixels per patch", 0),
            ("1024", "1024", "1024 x 1024 pixels per patch", 1),
            ("2048", "2048", "2048 x 2048 pixels per patch", 2),
            ("4096", "4096 (4K)", "Bake output array alone uses 256 MiB per patch", 3),
            ("8192", "8192 (8K)", "Bake output array alone uses 1 GiB per patch", 4),
            ("16384", "16384 (16K)", "Bake output array alone uses 4 GiB per patch", 5),
        ],
        default="1024",
    )
    repair_unmapped: BoolProperty(
        name="Repair unmapped layer 0",
        description="Approximate missing layer-0 texture samples using surrounding mapped blends. Reported per patch; leave off for strict source validation",
        default=False,
    )
    grass: BoolProperty(name="Grass and plants", default=True)
    models: BoolProperty(name="3D details", default=True)
    density: FloatProperty(
        name="Grass density", default=0.5, min=0, max=1, subtype="FACTOR"
    )
    mesh_density: FloatProperty(
        name="Model density", default=0.5, min=0, max=1, subtype="FACTOR"
    )
    size: FloatProperty(name="Detail size", default=1, min=0.1, max=5)
    seed: IntProperty(name="Seed", default=0, min=0, max=1000000)
    max_plants: IntProperty(
        name="Plant limit per patch", default=15000, min=0, max=100000
    )
    max_models: IntProperty(name="Model limit per patch", default=500, min=0, max=10000)
    variation: BoolProperty(name="Color variation", default=True)


class AddSources(bpy.types.Operator, ImportHelper):
    """Append source overrides selected in Blender's multi-file browser."""

    bl_idname = "swtor_terrain.add_sources"
    bl_label = "Choose room files (optional override)"
    filter_glob: StringProperty(default="*.json;*.dat", options={"HIDDEN"})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        s = context.scene.swtor_terrain
        for item in self.files:
            path = str(Path(self.directory) / item.name)
            if path not in {i.path for i in s.sources}:
                s.sources.add().path = path
        return {"FINISHED"}


class ClearSources(bpy.types.Operator):
    """Empty overrides to return to automatic discovery."""

    bl_idname = "swtor_terrain.clear_sources"
    bl_label = "Use automatic room discovery"

    def execute(self, context):
        context.scene.swtor_terrain.sources.clear()
        return {"FINISHED"}


class Apply(bpy.types.Operator):
    """Resolve rooms once, share a source cache, and process patches independently."""

    bl_idname = "swtor_terrain.apply"
    bl_label = "Apply / Update Terrain"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            self.report({"ERROR"}, "Switch to Object Mode")
            return {"CANCELLED"}
        s = context.scene.swtor_terrain
        messages = []
        count = 0
        instances = 0
        try:
            root = Path(bpy.path.abspath(s.resources)).resolve()
            if not (root / "art/shaders/materials").is_dir():
                raise ValueError("Choose resources containing art/shaders/materials")
            objects = targets(context, s)
            if not objects:
                raise ValueError(
                    "No terrain instance IDs found in the chosen scope. Preserve ZG terrain names or swtor_id properties."
                )
            wanted = {i for o, i in objects}
            records = {}
            tables = {}

            def progress(index, total):
                if index == 0:
                    context.window_manager.progress_begin(0, max(total, 1))
                context.window_manager.progress_update(index)

            rooms = resolve_rooms(s, root, wanted, messages, progress)
            for path in rooms:
                found = core.room(path, wanted)
                if not found:
                    continue
                area_path = path.parent / "area.dat"
                if area_path not in tables:
                    tables[area_path] = core.area(area_path)
                table = tables[area_path]
                existing = {t.name for t in s.types}
                for name in table["names"].values():
                    if name and name not in existing:
                        entry = s.types.add()
                        entry.name = name
                        existing.add(name)
                for ident, record in found.items():
                    if ident in records:
                        prior, prior_table = records[ident]
                        if prior["blob"] == record["blob"] and prior_table == table:
                            continue
                        raise ValueError(
                            "Conflicting terrain ID across source rooms: "
                            + ident
                            + ". Choose the intended room files manually."
                        )
                    records[ident] = (record, table)
            assets = Assets(root)
            context.window_manager.progress_begin(0, len(objects))
            for index, (obj, ident) in enumerate(objects):
                context.window_manager.progress_update(index)
                if ident not in records:
                    continue
                try:
                    record, table = records[ident]
                    p = core.patch(record["blob"])
                    instances += apply_one(obj, ident, p, table, assets, s, messages)
                    count += 1
                except Exception as e:
                    messages.append(obj.name + ": UNCHANGED: " + str(e))
            missing = wanted - set(records)
            if missing:
                messages.append(
                    f"{len(missing)} object IDs were not terrain in the chosen source rooms (ordinary area objects are skipped)."
                )
            messages.insert(
                0,
                f"Applied {count} terrain patches; generated {instances} detail instances.",
            )
            if count == 0:
                messages.append(
                    "No terrain was changed. Check source rooms, scope, and errors above."
                )
        except Exception as e:
            messages.insert(0, "ERROR: " + str(e))
        finally:
            context.window_manager.progress_end()
        report = bpy.data.texts.get("SWTOR Terrain Report") or bpy.data.texts.new(
            "SWTOR Terrain Report"
        )
        report.clear()
        report.write("\n".join(messages))
        self.report(
            {"INFO"} if count else {"ERROR"},
            messages[0] + " See SWTOR Terrain Report in Text Editor.",
        )
        return {"FINISHED"} if count else {"CANCELLED"}


class Restore(bpy.types.Operator):
    """Reattach retained original meshes and remove owned generated data."""

    bl_idname = "swtor_terrain.restore"
    bl_label = "Restore Original Terrain"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj, ident in targets(context, context.scene.swtor_terrain):
            original = bpy.data.meshes.get(obj.get("stt_original_mesh", ""))
            if original:
                owner = obj.get("stt_owner")
                obj.data = original
                if owner:
                    cleanup(owner)
                for key in ("stt_owner", "stt_original_mesh"):
                    if key in obj:
                        del obj[key]
                count += 1
        self.report({"INFO"}, f"Restored {count} terrains")
        return {"FINISHED"}


class Panel(bpy.types.Panel):
    """The 3D View sidebar; UI options map directly to persistent Settings."""

    bl_label = "SWTOR Terrain Tools"
    bl_idname = "SWTOR_PT_terrain_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SWTOR Terrain"

    def draw(self, context):
        l = self.layout
        s = context.scene.swtor_terrain
        l.prop(s, "resources")
        l.label(
            text=(
                "Manual room override"
                if s.sources
                else "Room files: automatic discovery"
            )
        )
        l.operator("swtor_terrain.add_sources")
        for source in s.sources:
            l.label(text=Path(source.path).name, icon="FILE")
        if s.sources:
            l.operator("swtor_terrain.clear_sources")
        for field in (
            "scope",
            "resolution",
            "repair_unmapped",
            "grass",
            "models",
            "density",
            "mesh_density",
            "size",
            "seed",
            "max_plants",
            "max_models",
            "variation",
        ):
            l.prop(s, field)
        l.prop(s, "show_types")
        if s.show_types:
            for t in s.types:
                l.prop(t, "enabled", text=Path(t.name.replace(chr(92), "/")).stem)
            if not s.types:
                l.label(text="Types appear after the first Apply.")
        l.operator("swtor_terrain.apply")
        l.operator("swtor_terrain.restore")
        l.label(text="Details follow terrain transforms.")


CLASSES = (
    Source,
    DetailType,
    Settings,
    AddSources,
    ClearSources,
    Apply,
    Restore,
    Panel,
)


def register():
    """Register dependencies before attaching the Scene pointer property."""
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.swtor_terrain = PointerProperty(type=Settings)


def unregister():
    """Remove the Scene pointer before unregistering types in reverse order."""
    del bpy.types.Scene.swtor_terrain
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
