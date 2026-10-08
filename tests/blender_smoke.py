# SPDX-License-Identifier: GPL-3.0-or-later
"""Run with Blender 4.1 --background --factory-startup --python-exit-code 1.

All terrain and texture data is synthetic. Temporary OBJ, PNG and .blend files
are written outside the repository and removed when the test finishes.
"""

import sys
import tempfile
import hashlib
import json
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import swtor_terrain_tools as addon


class SyntheticAssets:
    """Supply the same interface as Assets without shipping MAT/DDS/GR2 data."""

    def diffuse(self, name):
        return np.full((4, 4, 4), (0.25, 0.5, 0.75, 1.0), np.float32)

    def albedo(self, name):
        pixels = self.diffuse(name)
        pixels[0, :, 3] = 0
        return pixels, {"cutoff": 0.5, "alpha": "Test", "two_sided": True}


def main():
    # Cache reuses converted pixels, protects them, and keeps returned metadata
    # independent. Source diffuse pixels must not be mutated by opacity repair.
    assets = addon.Assets(Path("."))
    raw = np.full((4, 4, 4), 0.25, np.float32)
    assets.mats["test"] = dict(
        diffuse="d", rotation="r", alpha="Test", shader="Uber", cutoff=0.3
    )
    assets.images.update(d=raw, r=np.full((4, 4, 4), 0.75, np.float32))
    converted, metadata = assets.albedo("test")
    metadata["cutoff"] = 0
    again, metadata = assets.albedo("test")
    assert again is converted and not converted.flags.writeable
    assert metadata["cutoff"] == 0.7
    np.testing.assert_array_equal(raw, 0.25)
    np.testing.assert_array_equal(converted[..., 3], 0.25)
    addon.register()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    size = 3
    x, z = np.meshgrid(np.arange(size), np.arange(size))
    heights = (x * z * 0.03).astype(np.float32)
    vertices = np.stack(((x - 1) * 0.2, -(z - 1) * 0.2, heights), axis=2).reshape(-1, 3)
    patch = dict(
        width=size,
        depth=size,
        heights=heights,
        vertices=vertices,
        ids=[1],
        weights=np.ones((5, 5, 1)),
        color=np.ones((3, 3, 3)),
        channels={2: [255] * 9},
        holes=None,
    )
    parameters = [0] * 15
    parameters[1], parameters[7], parameters[10] = 6, 100, 2400
    table = {
        "ground": {1: "SyntheticGround"},
        "names": {2: "SyntheticGrass"},
        "params": {2: parameters},
    }
    ident = "900000000000000001"
    with tempfile.TemporaryDirectory(prefix="swtor-terrain-smoke-") as directory:
        directory = Path(directory)
        source = directory / (ident + ".obj")
        # Omit one cell to emulate a terrain hole. OBJ import drops its unused
        # corner vertex, exercising the UV-based correspondence fallback.
        with source.open("w") as file:
            for vx, vy, vz in vertices:
                file.write(f"v {vx} {vz} {-vy}\n")
            for k in range(size):
                for j in range(size):
                    file.write(f"vt {j / 2} {k / 2}\n")
            for k in range(2):
                for j in range(2):
                    if j == k == 1:
                        continue
                    a = k * size + j
                    for face in ((a, a + size, a + 1), (a + 1, a + size, a + size + 1)):
                        file.write("f " + " ".join(f"{v+1}/{v+1}" for v in face) + "\n")
        bpy.ops.wm.obj_import(filepath=str(source))
        obj = bpy.context.selected_objects[0]
        obj.name = ident
        assert len(obj.data.vertices) < 9, "Fixture must exercise dropped vertices"
        parent = bpy.data.objects.new("Synthetic parent", None)
        bpy.context.scene.collection.objects.link(parent)
        parent.location = (14, -7, 3)
        parent.rotation_euler = (0.1, 0.2, 0.4)
        parent.scale = (2, 3, 1.5)
        obj.parent = parent
        original = obj.data
        original_vertices = [tuple(v.co) for v in original.vertices]
        original_faces = [tuple(face.vertices) for face in original.polygons]
        settings = bpy.context.scene.swtor_terrain
        settings.scope = "SCENE"
        settings.resolution = "512"
        settings.density = 1
        settings.models = False
        warnings = []
        count = addon.apply_one(
            obj, ident, patch, table, SyntheticAssets(), settings, warnings
        )
        assert count > 0 and not warnings
        assert [tuple(v.co) for v in obj.data.vertices] == original_vertices
        assert [tuple(face.vertices) for face in obj.data.polygons] == original_faces
        assert len(obj.data.uv_layers) == 1
        assert obj.data.uv_layers[0].name == "SWTOR Terrain Bake"
        assert obj.children and all(child.parent == obj for child in obj.children)
        # A stable signature allows comparing complete generated output with
        # the prior release without including random ownership UUIDs.
        snapshot = []
        for item in sorted([obj, *obj.children], key=lambda o: o.name):
            snapshot.append(
                (
                    item.name,
                    [tuple(v.co) for v in item.data.vertices],
                    [tuple(f.vertices) for f in item.data.polygons],
                    [tuple(uv.uv) for uv in item.data.uv_layers[0].data],
                    [m.name for m in item.data.materials],
                )
            )
        for material in sorted(bpy.data.materials, key=lambda m: m.name):
            if material.get(addon.TAG):
                image = bpy.data.images[material["stt_albedo_image"]]
                snapshot.append(
                    (
                        material.name,
                        image.name,
                        hashlib.sha256(bytes(image.packed_file.data)).hexdigest(),
                    )
                )
        print(
            "OUTPUT_SIGNATURE",
            hashlib.sha256(json.dumps(snapshot).encode()).hexdigest(),
        )
        counts = tuple(
            len(blocks)
            for blocks in (
                bpy.data.meshes,
                bpy.data.materials,
                bpy.data.images,
                bpy.data.objects,
            )
        )
        names = sorted(m.name for m in bpy.data.materials if m.get(addon.TAG))
        addon.apply_one(obj, ident, patch, table, SyntheticAssets(), settings, [])
        assert counts == tuple(
            len(blocks)
            for blocks in (
                bpy.data.meshes,
                bpy.data.materials,
                bpy.data.images,
                bpy.data.objects,
            )
        )
        assert names == sorted(m.name for m in bpy.data.materials if m.get(addon.TAG))

        previous = obj.data
        try:
            addon.apply_one(
                obj,
                ident,
                patch,
                {**table, "ground": {}},
                SyntheticAssets(),
                settings,
                [],
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Missing ground should fail")
        assert obj.data == previous
        ground = obj.data.materials[0]
        image = bpy.data.images[ground["stt_albedo_image"]]
        packed = directory / "ground.png"
        packed.write_bytes(bytes(image.packed_file.data))
        np.testing.assert_allclose(
            addon.pixels(packed)[0, 0], (0.25, 0.5, 0.75, 1), atol=1 / 255
        )

        scene = directory / "test.blend"
        original_name = original.name
        bpy.ops.wm.save_as_mainfile(filepath=str(scene))
        bpy.ops.wm.open_mainfile(filepath=str(scene))
        obj = bpy.data.objects[ident]
        for material in bpy.data.materials:
            if material.get(addon.TAG):
                assert bpy.data.images[material["stt_albedo_image"]].packed_file
        assert bpy.ops.swtor_terrain.restore() == {"FINISHED"}
        assert obj.data.name == original_name and not obj.children
        assert not any(m.get(addon.TAG) for m in bpy.data.materials)
    addon.unregister()
    print(
        "PASS: OBJ holes, transforms, details, packed pixels, repeat update, failure retention, reopen and Restore"
    )


if __name__ == "__main__":
    main()
