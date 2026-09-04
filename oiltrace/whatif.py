"""Counterfactual re-run — spec §33-34.

Given an existing incident report and a small delta on wind / current / windage,
re-run just the *drift and inversion* stages against the perturbed metocean.
Returns the new source-track and origin cell, without touching the detector or
the AIS attribution — which lets an analyst probe: *if the wind had been 20%
stronger, would this vessel still be the prime suspect?*
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sagar.core import drift, inversion
from sagar.core.environment import SyntheticOcean
from sagar.core.geoutil import Origin


class _PerturbedOcean:
    """Wrap the analytic ocean and scale currents / wind at sample time.

    Kept as a thin adapter so the drift engine is unaware anything changed —
    the physics remains the same, only the inputs are perturbed.
    """
    def __init__(self, base, wind_scale=1.0, current_scale=1.0):
        self.base = base
        self.origin = base.origin
        self.ws = wind_scale
        self.cs = current_scale

    def sample_xy(self, t, x, y):
        u, v, uw, vw = self.base.sample_xy(t, x, y)
        return u*self.cs, v*self.cs, uw*self.ws, vw*self.ws

    def sample(self, t, lat, lon):
        f = self.base.sample(t, lat, lon)
        from sagar.core.environment import Forcing
        return Forcing(f.u_cur*self.cs, f.v_cur*self.cs,
                       f.u_wind*self.ws, f.v_wind*self.ws, f.sst)

    def wind_field_xy(self, t, x, y):
        uw, vw = self.base.wind_field_xy(t, x, y)
        return uw*self.ws, vw*self.ws


def run(scene_meta, mask_data, wind_scale=1.0, current_scale=1.0, seed=11):
    """`scene_meta` = dict with origin lat/lon, epoch, size, pixel_m.
    `mask_data` = boolean mask array (or its shape + list of true pixels)."""
    origin = Origin(scene_meta["origin_lat"], scene_meta["origin_lon"])
    base = SyntheticOcean(origin, seed=seed)
    ocean = _PerturbedOcean(base, wind_scale=wind_scale, current_scale=current_scale)

    # Rebuild a minimal Scene envelope so inversion can address pixel↔metres.
    from sagar.core.sarsim import Scene, SceneSpec
    spec = SceneSpec(origin=origin, size=scene_meta["size"],
                     pixel_m=scene_meta["pixel_m"], epoch=0.0, seed=seed)
    scene = Scene(np.zeros((spec.size, spec.size), np.float32), mask_data, spec)

    hyp = inversion.invert(scene, ocean, mask_data, n_coarse=80, n_refine=60, seed=seed)
    return dict(
        t_start_h=hyp.t_start / 3600.0,
        duration_h=hyp.duration / 3600.0,
        course_deg=float(hyp.course_deg),
        speed_kn=float(hyp.speed_kn),
        start_lat=origin.to_ll(hyp.x0, hyp.y0)[0],
        start_lon=origin.to_ll(hyp.x0, hyp.y0)[1],
        iou=float(hyp.iou),
        wind_scale=wind_scale, current_scale=current_scale,
    )
