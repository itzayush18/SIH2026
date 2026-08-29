"""Ground-truth scenario builder.

Rather than painting an arbitrary dark blob, the reference scenario *derives*
the slick from the same physics the hindcast will later invert: a vessel steams
along a course discharging for a period, and every released parcel is advected
forward by the ocean model to the acquisition time. The resulting shape is what
the SAR simulator darkens.

That matters for evaluation — it means "did we recover the origin?" is a fair
question with a known answer, instead of being baked in.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .drift import integrate
from .environment import SyntheticOcean
from .geoutil import Origin
from .sarsim import Scene, SceneSpec, simulate


@dataclass
class Truth:
    origin_xy: tuple
    release_t0: float
    release_t1: float
    course_deg: float
    speed_kn: float
    mmsi: str = "419001234"


def build(origin: Origin, seed=11, release_h_ago=13.0, discharge_h=1.6,
          course=312.0, speed_kn=5.8, size=1024, pixel_m=60.0):
    ocean = SyntheticOcean(origin, seed=seed)
    spec = SceneSpec(origin=origin, size=size, pixel_m=pixel_m, epoch=0.0, seed=seed)

    t0 = -release_h_ago * 3600.0
    t1 = t0 + discharge_h * 3600.0

    # Release points along the discharging vessel's track, placed so the drifted
    # slick lands near the scene centre.
    v = speed_kn * 0.514444
    n_rel = 60
    rel_t = np.linspace(t0, t1, n_rel)
    ox, oy = -9000.0, -13000.0
    rx = ox + v * math.sin(math.radians(course)) * (rel_t - t0)
    ry = oy + v * math.cos(math.radians(course)) * (rel_t - t0)

    # Advect every release point forward to the acquisition time; parcels
    # released earlier drift further, which is what stretches the slick.
    parts_x, parts_y = [], []
    per_release = 220
    rng = np.random.default_rng(seed)
    for i in range(n_rel):
        x0 = rx[i] + rng.normal(0, 120, per_release)
        y0 = ry[i] + rng.normal(0, 120, per_release)
        res = integrate(ocean, x0, y0, rel_t[i], -rel_t[i], dt=300.0,
                        backward=False, seed=seed + i)
        parts_x.append(res.x[-1]); parts_y.append(res.y[-1])
    px = np.concatenate(parts_x); py = np.concatenate(parts_y)

    # Rasterise the parcel cloud into a slick mask.
    tmp = Scene(np.zeros((size, size), np.float32), np.zeros((size, size), bool), spec)
    r, c = tmp.pixel_of_xy(px, py)
    mask = np.zeros((size, size), bool)
    ok = (r >= 0) & (r < size) & (c >= 0) & (c < size)
    mask[r[ok].astype(int), c[ok].astype(int)] = True
    mask = ndimage.binary_dilation(mask, np.ones((5, 5)))
    mask = ndimage.binary_closing(mask, np.ones((9, 9)))
    mask = ndimage.binary_fill_holes(mask)

    # Bright targets: a handful of vessels visible in the scene at acquisition.
    vessels_px = []
    for (vx, vy, boost) in [(18000, 9000, 1.0), (-24000, 15000, 0.8),
                            (8000, -21000, 0.9), (26000, -6000, 0.7)]:
        vr, vc = tmp.pixel_of_xy(vx, vy)
        vessels_px.append((float(vr), float(vc), boost))

    scene = simulate(spec, ocean, [mask], vessels_px=vessels_px, n_lookalikes=3)
    truth = Truth(origin_xy=(float(rx[0]), float(ry[0])), release_t0=t0,
                  release_t1=t1, course_deg=course, speed_kn=speed_kn)
    return scene, ocean, truth
