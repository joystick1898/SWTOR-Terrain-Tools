"""Verify resolution settings persist and a 4K bake packs at its actual size."""

import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import swtor_terrain_tools as addon

addon.register()
settings = bpy.context.scene.swtor_terrain
assert settings.resolution == "1024"
choices = ["512", "1024", "2048", "4096", "8192", "16384"]
prop = settings.bl_rna.properties["resolution"]
assert [(i.identifier, i.value) for i in prop.enum_items] == list(
    zip(choices, range(len(choices)))
)
with tempfile.TemporaryDirectory(prefix="terrain-resolution-") as folder:
    for choice in choices:
        settings = bpy.context.scene.swtor_terrain
        settings.resolution = choice
        path = str(Path(folder) / "settings.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        assert bpy.context.scene.swtor_terrain.resolution == choice

    patch = dict(
        width=3,
        depth=3,
        ids=[1],
        weights=np.ones((5, 5, 1)),
        color=np.ones((3, 3, 3)),
        holes=None,
    )
    source = np.full((2, 2, 4), (0.25, 0.5, 0.75, 1), np.float32)
    baked = addon.core.bake(patch, {1: "ground"}, lambda _: source, 4096)
    assert baked.shape == (4096, 4096, 4)
    np.testing.assert_array_equal(
        baked[::127, ::127], np.broadcast_to(source[0, 0], baked[::127, ::127].shape)
    )
    material = addon.image_material("4K test", baked, "resolution-test")
    image = bpy.data.images[material["stt_albedo_image"]]
    assert tuple(image.size) == (4096, 4096)
    assert image.packed_file
    path = str(Path(folder) / "bake.blend")
    image_name = image.name
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    image = bpy.data.images[image_name]
    assert tuple(image.size) == (4096, 4096) and image.packed_file
print("PASS: all resolution settings persist; 4K bake packs and reopens at 4096 x 4096")
