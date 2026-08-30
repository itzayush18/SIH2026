"""Metocean forcing.

The drift engine only ever asks the environment for `sample(t, lat, lon)`.
That keeps the Lagrangian solver agnostic to where the fields came from, so a
CMEMS/ERA5 NetCDF reader can be dropped in behind the same interface without
touching `drift.py`.

`SyntheticOcean` is what the prototype ships with: a tidal + mesoscale-eddy +
mean-flow current field and a slowly veering wind, all analytic and therefore
reproducible and dependency-free.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .geoutil import Origin


@dataclass
class Forcing:
    u_cur: float   # eastward current, m/s
    v_cur: float   # northward current, m/s
    u_wind: float  # eastward wind at 10 m, m/s
    v_wind: float
    sst: float = 28.0

    @property
    def wind_speed(self):
        return math.hypot(self.u_wind, self.v_wind)


class SyntheticOcean:
    """Analytic stand-in for a CMEMS current + ERA5 wind hindcast."""

    def __init__(self, origin: Origin, seed: int = 7):
        self.origin = origin
        rng = np.random.default_rng(seed)
        # Mean flow: the along-shore current, roughly north-westward here.
        self.mean = (0.18, 0.09)
        # Two mesoscale eddies, parameterised in local metres.
        self.eddies = [
            dict(x=rng.uniform(-4e4, 4e4), y=rng.uniform(-4e4, 4e4),
                 r=rng.uniform(1.5e4, 3.0e4), g=rng.uniform(0.15, 0.35) * s)
            for s in (1.0, -1.0)
        ]
        self.tide_period = 12.42 * 3600.0  # M2
        self.tide_amp = 0.22
        self.wind_base = 6.5   # m/s
        self.wind_dir0 = 225.0  # meteorological "from" direction

    # -- vectorised sampling -------------------------------------------------
    def sample_xy(self, t, x, y):
        """t: seconds since scene epoch. x,y: metres (scalar or ndarray)."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        u = np.full(x.shape, self.mean[0])
        v = np.full(x.shape, self.mean[1])

        # Eddies: solid-body-ish rotation with Gaussian decay.
        for e in self.eddies:
            dx, dy = x - e["x"], y - e["y"]
            rr = (dx * dx + dy * dy) / (e["r"] ** 2)
            amp = e["g"] * np.exp(-rr)
            u += -amp * dy / e["r"]
            v += amp * dx / e["r"]

        # Barotropic tide: reversing ellipse, spatially uniform at this scale.
        ph = 2 * math.pi * t / self.tide_period
        u += self.tide_amp * math.cos(ph)
        v += 0.6 * self.tide_amp * math.sin(ph)

        # Wind veers slowly and strengthens through the diurnal cycle.
        spd = self.wind_base + 1.8 * math.sin(2 * math.pi * t / 86400.0)
        d = math.radians(self.wind_dir0 + 12.0 * math.sin(2 * math.pi * t / 172800.0))
        uw = -spd * math.sin(d)   # "from" convention -> vector the wind blows to
        vw = -spd * math.cos(d)
        return u, v, np.full(x.shape, uw), np.full(x.shape, vw)

    def sample(self, t, lat, lon) -> Forcing:
        x, y = self.origin.to_xy(lat, lon)
        u, v, uw, vw = self.sample_xy(t, x, y)
        return Forcing(float(u), float(v), float(uw), float(vw))

    def wind_field_xy(self, t, x, y):
        """Wind only- used by the SAR simulator for the backscatter background."""
        _, _, uw, vw = self.sample_xy(t, x, y)
        return uw, vw
