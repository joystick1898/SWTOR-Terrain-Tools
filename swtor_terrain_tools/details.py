# SPDX-License-Identifier: GPL-3.0-or-later
"""Choose deterministic detail placements; create no Blender scene objects.

Uses mathutils for normals. Scale divisors and noise amplitudes are empirical
preview values, not verified reproductions of the game's full scatter formula.
"""

import math
import colorsys
from mathutils import Vector


def unit_hash(seed, *values):
    """Return a stable [0,1) rank, independent of Python's randomized hash()."""
    h = seed & 0xFFFFFFFF
    for v in values:
        h = ((h ^ int(v)) * 0x45D9F3B) & 0xFFFFFFFF
        h ^= h >> 16
    return h / 4294967296


def candidates(config, heights, settings):
    """Return (placements, was_capped) from painted density and settings.

    Heights are flat row-major (z*width+x); channel densities are x-major
    (x*depth+z). Placement tuple: rank, channel_id, x, y, z, scale, angle,
    rgb, flip, surface_normal. Positions are canonical Blender Z-up.
    The scene adapter supplies category densities/budgets, size, seed,
    variation and channel_<id> toggles through a small settings proxy.
    """
    width = config["width"]
    result = []
    for channel in config["channels"]:
        cid = channel["id"]
        if not getattr(settings, "channel_" + str(cid)):
            continue
        values = channel["parameters"]
        is_mesh = channel.get("kind") == "mesh"
        # Reconstructed parameter uses are documented in docs/FORMATS.md.
        # Category divisors are empirical, not proven engine constants.
        cap = 1 + int(values[1] / (12 if is_mesh else 1.5))
        density = channel["density_x_major"]
        for k in range(config["depth"] - 1):
            for j in range(width - 1):
                paint = (
                    sum(
                        density[x * config["depth"] + z]
                        for x, z in ((j, k), (j + 1, k), (j, k + 1), (j + 1, k + 1))
                    )
                    // 4
                )
                if not paint:
                    continue
                state = (j * 12263 + k * 22487 - cid + settings.seed) & 0xFFFFFFFF

                def random15():
                    nonlocal state
                    state = (state * 214013 + 2531011) & 0xFFFFFFFF
                    return (state >> 16) & 32767

                word = 0
                for index in range(cap):
                    fx = random15() / 32768
                    fz = random15() / 32768
                    if not word:
                        word = random15()
                    threshold = word & 255
                    word >>= 8
                    if threshold >= paint:
                        continue
                    rank = unit_hash(settings.seed, cid, j, k, index)
                    if rank >= (settings.mesh_density if is_mesh else settings.density):
                        continue
                    allowed = config.get("allowed")
                    if (
                        allowed is not None
                        and not allowed[k, j, 0 if fx + fz <= 1 else 1]
                    ):
                        continue
                    h00, h10, h01, h11 = (
                        heights[k * width + j],
                        heights[k * width + j + 1],
                        heights[(k + 1) * width + j],
                        heights[(k + 1) * width + j + 1],
                    )
                    if fx + fz <= 1:
                        z = h00 + (h10 - h00) * fx + (h01 - h00) * fz
                    else:
                        z = h11 + (h01 - h11) * (1 - fx) + (h10 - h11) * (1 - fz)
                    # Approximate variation; original noise algorithm is not reproduced.
                    noise = (
                        (unit_hash(settings.seed + 71, cid, j, k) - 0.5) * 0.5
                        if settings.variation
                        else 0
                    )
                    scale = (
                        values[10] / 25.64 + 0.1
                        if is_mesh
                        else (values[10] + 32) / 2400
                    )
                    scale *= 1 - (1 - paint / 255) * values[12] / 100
                    scale = (
                        max(
                            0.0001,
                            scale
                            + values[11] / 100 * noise * (1.5 if is_mesh else 1 / 15),
                        )
                        * settings.size
                    )
                    hue = ((values[3] + values[4] * noise) / 100) % 1
                    sat = max(0, min(1, (values[5] + values[6] * noise) / 100))
                    lum = max(0, min(1, (values[7] + values[8] * noise) / 100))
                    rgb = (1, 1, 1) if is_mesh else colorsys.hls_to_rgb(hue, lum, sat)
                    dx, dz = (
                        (h10 - h00, h01 - h00)
                        if fx + fz <= 1
                        else (h11 - h01, h11 - h10)
                    )
                    normal = tuple(Vector((-dx / 0.2, dz / 0.2, 1)).normalized())
                    angle = unit_hash(settings.seed + 99, cid, j, k, index) * math.tau
                    flip = unit_hash(settings.seed + 33, cid, j, k, index) < 0.5
                    result.append(
                        (
                            rank,
                            cid,
                            (j + fx - math.ceil((width - 1) / 2)) * 0.2,
                            -(k + fz - math.ceil((config["depth"] - 1) / 2)) * 0.2,
                            z,
                            scale,
                            angle,
                            rgb,
                            flip,
                            normal,
                        )
                    )
    # Global spatially distributed budget, not first-channel priority.
    model_ids = {c["id"] for c in config["channels"] if c.get("kind") == "mesh"}
    result.sort(key=lambda p: (p[0], p[1], p[2], p[3]))
    cards = [p for p in result if p[1] not in model_ids]
    models = [p for p in result if p[1] in model_ids]
    capped = len(cards) > settings.max_plants or len(models) > settings.max_models
    return cards[: settings.max_plants] + models[: settings.max_models], capped
