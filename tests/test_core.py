# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic regression tests; no Blender installation or game assets needed."""

import gzip, importlib.util, struct, tempfile, unittest, zlib
from pathlib import Path
import numpy as np
from unittest.mock import patch as mock_patch

spec = importlib.util.spec_from_file_location(
    "terrain_core", Path(__file__).parents[1] / "swtor_terrain_tools/core.py"
)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def fixture(flag=2):
    # Small dense grid with no interiors, one material, tint and one detail map.
    # Only four border floats for a 2x2 grid.
    raw = struct.pack("<BIIB4fBb", flag, 2, 2, 0, 1, 2, 3, 4, 1, 7)
    raw += (
        bytes([255]) * 9
        + bytes([1])
        + bytes([255]) * 12
        + bytes([1, 2])
        + bytes([10, 20, 30, 40])
    )
    return raw


class TerrainTests(unittest.TestCase):
    def layered(self, size=3):
        weights = np.zeros((size, size, 2))
        weights[:, :, 0] = 1
        return dict(
            ids=[1, 0],
            weights=weights,
            width=(size + 1) // 2,
            depth=(size + 1) // 2,
            holes=None,
        )

    def test_unmapped_residual_renormalizes(self):
        p = self.layered()
        p["weights"][1, 1] = [254 / 255, 1 / 255]
        result, notes = core.ground_weights(p, {1: "valid"})
        np.testing.assert_array_equal(result[:, :, 0], 1)
        np.testing.assert_array_equal(result[:, :, 1], 0)
        self.assertTrue(notes)

    def test_substantial_visible_unknown_still_fails(self):
        for amount in (2 / 255, 1):
            p = self.layered()
            p["weights"][1, 1] = [1 - amount, amount]
            with self.assertRaisesRegex(ValueError, "visible ground"):
                core.ground_weights(p, {1: "valid"})

    def test_unmapped_sample_deep_in_hole(self):
        p = self.layered(9)
        p["weights"][7, 7] = [0, 1]
        allowed = np.zeros((4, 4, 2), bool)
        allowed[0, 0] = True
        result, notes = core.ground_weights(p, {1: "valid"}, allowed)
        self.assertTrue(np.isfinite(result).all())
        self.assertTrue(notes)
        allowed[3, 3] = True
        with self.assertRaises(ValueError):
            core.ground_weights(p, {1: "valid"}, allowed)

    def test_bilinear_support_next_to_visible_triangle(self):
        p = self.layered(5)
        p["weights"][2, 2] = [0, 1]
        allowed = np.zeros((2, 2, 2), bool)
        allowed[0, 0, 0] = True
        with self.assertRaises(ValueError):
            core.ground_weights(p, {1: "valid"}, allowed)

    def test_mapped_weights_unchanged(self):
        p = self.layered()
        result, notes = core.ground_weights(p, {1: "valid"})
        self.assertIs(result, p["weights"])
        self.assertFalse(notes)

    def test_opt_in_layer_zero_repair(self):
        p = self.layered(5)
        p["weights"][2, 2] = [0, 1]
        original = p["weights"].copy()
        result, notes = core.ground_weights(p, {1: "valid"}, repair_unmapped=True)
        np.testing.assert_array_equal(result[..., 0], 1)
        np.testing.assert_array_equal(result[..., 1], 0)
        np.testing.assert_array_equal(p["weights"], original)
        self.assertIn("REPAIRED", notes[0])
        p["ids"][1] = 99
        with self.assertRaises(ValueError):
            core.ground_weights(p, {1: "valid"}, repair_unmapped=True)

    def test_repair_averages_boundary_without_wrapping(self):
        p = self.layered(5)
        p["ids"] = [1, 2, 0]
        p["weights"] = np.zeros((5, 5, 3), np.float32)
        p["weights"][..., 2] = 1
        p["weights"][:, 0] = [1, 0, 0]
        p["weights"][:, -1] = [0, 1, 0]
        result, _ = core.ground_weights(p, {1: "a", 2: "b"}, repair_unmapped=True)
        np.testing.assert_allclose(result[:, 2], np.tile([0.5, 0.5, 0], (5, 1)))
        np.testing.assert_allclose(result.sum(2), 1)
        p["weights"][:] = [0, 0, 1]
        with self.assertRaisesRegex(ValueError, "without any mapped"):
            core.ground_weights(p, {1: "a", 2: "b"}, repair_unmapped=True)

    def write_room(self, path, ident):
        header = bytearray(32)
        header[4:28] = b"ROOM_DAT_BINARY_FORMAT_\0"
        struct.pack_into("<I", header, 28, 32)
        prop = struct.pack("<BII", 8, 0xA3AB26AE, 1) + b"x"
        path.write_bytes(
            bytes(header)
            + struct.pack("<IIBQQBIIB", 1, 0xABCD1234, 0, ident, 0, 0, 1, len(prop), 0)
            + prop
        )

    def test_discovery_cache_and_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "world/areas/planet"
            folder.mkdir(parents=True)
            first = folder / "first.dat"
            second = folder / "SECOND.DAT"
            self.write_room(first, 123)
            self.write_room(second, 456)
            (folder / "area.dat").write_bytes(b"area table")
            cache = root / "cache.json"
            self.assertEqual(set(core.room_ids(first)), {"123"})
            found, _ = core.discover_rooms(root, {"123", "456"}, cache)
            self.assertEqual(set(found), {first, second})
            with mock_patch.object(
                core, "room_ids", side_effect=AssertionError("Should use cached IDs")
            ):
                found, _ = core.discover_rooms(root, {"456"}, cache)
                self.assertEqual(found, [second])
            self.write_room(second, 789)
            found, _ = core.discover_rooms(root, {"789"}, cache)
            self.assertEqual(found, [second])
            second.unlink()
            with self.assertRaises(ValueError):
                core.discover_rooms(root, {"789"}, cache)

    def test_discovery_missing_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "original room DATs"):
                core.discover_rooms(directory, {"123"})

    def test_dense_layout(self):
        p = core.patch(zlib.compress(fixture()))
        np.testing.assert_array_equal(p["heights"], [[1, 3], [2, 4]])
        self.assertEqual(p["channels"][2], [10, 20, 30, 40])
        self.assertEqual(p["weights"].shape, (3, 3, 1))
        self.assertEqual(p["ids"], [7])

    def test_compression(self):
        for pack in (gzip.compress, zlib.compress):
            self.assertEqual(core.decompress(pack(b"terrain")), b"terrain")
        with self.assertRaises(ValueError):
            core.decompress(b"not terrain")

    def test_unsupported_and_truncated(self):
        for raw in (fixture(10), fixture(3), fixture()[:-1]):
            with self.assertRaises(ValueError):
                core.patch(zlib.compress(raw))

    def test_bake_and_missing_mapping(self):
        p = core.patch(zlib.compress(fixture()))
        color = np.full((2, 2, 4), 0.25, np.float32)
        result = core.bake(p, {7: "ground"}, lambda name: color, 8)
        np.testing.assert_allclose(result[:, :, :3], 0.25)
        np.testing.assert_allclose(result[:, :, 3], 1)
        with self.assertRaises(ValueError):
            core.bake(p, {}, lambda name: color, 8)

    def test_resource_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Art").mkdir()
            (root / "Art" / "Sample.dds").touch()
            self.assertEqual(
                core.resource(root, "resources/art/sample.dds"),
                root / "Art" / "Sample.dds",
            )
            with self.assertRaises(ValueError):
                core.resource(root, "../outside")
            with self.assertRaises(FileNotFoundError):
                core.resource(root, "art/missing.dds")

    def test_reader_bounds(self):
        with self.assertRaises(ValueError):
            core.Reader(b"abc").take(4)
        with self.assertRaises(ValueError):
            core.Reader(b"abc").take(-1)


if __name__ == "__main__":
    unittest.main()
