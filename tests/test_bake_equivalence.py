# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare strip baking to the original 1.0.3 full-frame arithmetic."""
import unittest
import numpy as np
from test_core import core

sample = core.sample
ground_weights = core.ground_weights


def reference_bake(
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
    u, v = np.meshgrid(q, q)
    out = np.zeros((resolution, resolution, 4), np.float32)
    out[:, :, 3] = 1
    for i, tid in enumerate(p["ids"]):
        if not weights[:, :, i].any():
            continue
        if tid not in table:
            raise ValueError("No area material mapping for ground layer " + str(tid))
        tex = read_diffuse(table[tid])[:, :, :3]
        out[:, :, :3] += sample(
            tex, u * p["width"] / 2, v * p["depth"] / 2, True
        ) * sample(weights[:, :, i], u, v)
    out[:, :, :3] *= sample(p["color"], u, v)
    return out.clip(0, 1)


class BakeEquivalence(unittest.TestCase):
    def test_exact_pixels_and_reports(self):
        rng = np.random.default_rng(82)
        for resolution in (63, 65, 512, 1024, 2048):
            weights = rng.random((7, 9, 3))
            weights /= weights.sum(axis=2)[..., None]
            p = dict(
                width=5,
                depth=4,
                ids=[1, 2, 0],
                weights=weights,
                color=rng.random((4, 5, 3)),
                holes=None,
            )
            textures = {i: rng.random((13, 17, 4), dtype=np.float32) for i in (1, 2, 0)}
            for repair in (False, True):
                table = {i: i for i in ((1, 2) if repair else (1, 2, 0))}
                notes_old, notes_new = [], []
                old = reference_bake(
                    p,
                    table,
                    textures.__getitem__,
                    resolution,
                    warnings=notes_old,
                    repair_unmapped=repair,
                )
                new = core.bake(
                    p,
                    table,
                    textures.__getitem__,
                    resolution,
                    warnings=notes_new,
                    repair_unmapped=repair,
                )
                np.testing.assert_array_equal(old, new)
                self.assertEqual(notes_old, notes_new)
