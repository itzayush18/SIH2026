"""Sentinel-1-like SAR scene simulator.

Real Zenodo/Copernicus GRD scenes are the target input (see
`sagar/data/loaders.py`), but a judge-runnable prototype needs a scene it can
generate on the spot, with a *known* ground truth for both the slick and the
guilty vessel. This module produces VV sigma0 in dB with the properties the
detector actually keys on:

  * wind-driven Bragg background via a CMOD-like speed->NRCS relation,
  * multiplicative speckle with a configurable number of looks,
  * oil slicks as damping-ratio patches (dark, sharp-edged, elongated),
  * *look-alikes*- low-wind cells and biogenic films that are dark but
    smooth-edged and low-contrast; these are what a naive threshold gets wrong,
  * bright point targets for vessels.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from .geoutil import Origin


@dataclass
class SceneSpec:
    origin: Origin
    size: int = 1024          # pixels per side
    pixel_m: float = 40.0     # ground spacing, metres
    epoch: float = 0.0        # seconds; acquisition time of the scene
    looks: float = 4.4        # ENL of a Sentinel-1 IW GRDH product
    seed: int = 11


@dataclass
class Scene:
    sigma0_db: np.ndarray
    truth_mask: np.ndarray
    spec: SceneSpec
    meta: dict = field(default_factory=dict)

    def xy_of_pixel(self, r, c):
        """Row/col -> local ENU metres, origin at scene centre."""
        n = self.spec.size
        x = (np.asarray(c, float) - n / 2.0) * self.spec.pixel_m
        y = (n / 2.0 - np.asarray(r, float)) * self.spec.pixel_m
        return x, y

    def pixel_of_xy(self, x, y):
        n = self.spec.size
        c = np.asarray(x, float) / self.spec.pixel_m + n / 2.0
        r = n / 2.0 - np.asarray(y, float) / self.spec.pixel_m
        return r, c

    def latlon_of_pixel(self, r, c):
        x, y = self.xy_of_pixel(r, c)
        return self.spec.origin.to_ll(x, y)

    @property
    def bounds(self):
        """(south, west, north, east) for the web map."""
        half = self.spec.size * self.spec.pixel_m / 2.0
        s, w = self.spec.origin.to_ll(-half, -half)
        n, e = self.spec.origin.to_ll(half, half)
        return s, w, n, e


def cmod_like_nrcs(wind_speed, incidence_deg, look_rel_deg):
    """Cheap stand-in for CMOD5.n: sigma0 in linear units.

    Captures the two dependencies the detector cares about: sigma0 grows
    roughly as U^1.6 and falls with incidence angle. Absolute calibration is
    irrelevant here because everything downstream is contrast-based.
    """
    inc = np.radians(incidence_deg)
    base = 0.06 * np.power(np.clip(wind_speed, 0.4, None), 1.6) / np.power(np.tan(inc), 1.1)
    # Upwind/downwind/crosswind modulation.
    base *= 1.0 + 0.18 * np.cos(np.radians(look_rel_deg)) + 0.09 * np.cos(2 * np.radians(look_rel_deg))
    return base


def _gauss_blob(n, rng, cx, cy, rad, aniso=1.0, rot=0.0):
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    dx, dy = xx - cx, yy - cy
    ct, st = math.cos(rot), math.sin(rot)
    a = (dx * ct + dy * st) / (rad * aniso)
    b = (-dx * st + dy * ct) / rad
    return np.exp(-(a * a + b * b))


def _fractal_field(n, rng, beta=2.4):
    """1/f^beta noise- used to give slicks and wind cells organic texture."""
    f = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(f, f)
    r = np.sqrt(fx ** 2 + fy ** 2)
    r[0, 0] = 1e-6
    spec = np.power(r, -beta / 2.0)
    spec[0, 0] = 0.0
    ph = rng.uniform(0, 2 * math.pi, (n, n))
    img = np.real(np.fft.ifft2(spec * np.exp(1j * ph)))
    img -= img.mean()
    s = img.std()
    return img / (s if s > 0 else 1.0)


def simulate(spec: SceneSpec, ocean, slick_polys, vessels_px=(), n_lookalikes=3) -> Scene:
    """Render a scene.

    slick_polys : list of boolean masks (same shape as the scene) marking oil.
    vessels_px  : iterable of (row, col, rcs_boost) bright targets.
    """
    n = spec.size
    rng = np.random.default_rng(spec.seed)

    # --- geometry: incidence sweeps across range (columns), as in a real swath
    inc = np.linspace(30.5, 45.5, n)[None, :].repeat(n, axis=0)

    # --- wind field from the ocean model, plus small-scale gustiness
    yy, xx = np.mgrid[0:n, 0:n]
    x_m = (xx - n / 2.0) * spec.pixel_m
    y_m = (n / 2.0 - yy) * spec.pixel_m
    uw, vw = ocean.wind_field_xy(spec.epoch, x_m, y_m)
    gust = 1.0 + 0.10 * _fractal_field(n, rng, beta=3.0)
    wspd = np.hypot(uw, vw) * gust
    wdir = np.degrees(np.arctan2(uw, vw))

    # --- look-alike 1: low-wind cells. Dark, but broad and soft-edged, and the
    #     darkening comes from the wind field, so there is no sharp boundary.
    lookalike = np.zeros((n, n))
    for _ in range(n_lookalikes):
        cx, cy = rng.uniform(0.12 * n, 0.88 * n, 2)
        rad = rng.uniform(0.07 * n, 0.16 * n)
        blob = _gauss_blob(n, rng, cx, cy, rad, aniso=rng.uniform(1.0, 2.0),
                           rot=rng.uniform(0, math.pi))
        lookalike = np.maximum(lookalike, np.power(blob, 0.45))
    wspd = wspd * (1.0 - 0.72 * lookalike)

    sigma_lin = cmod_like_nrcs(wspd, inc, wdir)

    # --- look-alike 2: biogenic films. These *do* damp Bragg waves, but weakly
    #     and with diffuse edges- the single hardest negative class in the
    #     literature, and the reason a bare threshold is not enough.
    bio = np.zeros((n, n), dtype=bool)
    for _ in range(max(1, n_lookalikes - 1)):
        cx, cy = rng.uniform(0.1 * n, 0.9 * n, 2)
        rad = rng.uniform(0.05 * n, 0.10 * n)
        b = _gauss_blob(n, rng, cx, cy, rad, aniso=rng.uniform(1.5, 3.0),
                        rot=rng.uniform(0, math.pi))
        b = b * (1.0 + 0.35 * _fractal_field(n, rng, beta=1.6))
        bio |= b > 0.55
        sigma_lin *= 1.0 - 0.42 * np.clip(b, 0, 1)

    # --- oil: damping ratio applied multiplicatively to the Bragg background
    truth = np.zeros((n, n), dtype=bool)
    for poly in slick_polys:
        truth |= poly
    if truth.any():
        # Thicker in the core, feathered at the edges- mimics emulsion gradient.
        d = ndimage.distance_transform_edt(truth)
        core = np.clip(d / max(3.0, 0.06 * d.max()), 0, 1)
        texture = 0.12 * _fractal_field(n, rng, beta=2.0)
        damping = 1.0 - (0.78 * core + texture) * truth
        sigma_lin *= np.clip(damping, 0.06, 1.0)

    # --- bright targets (vessels + a couple of platforms)
    for (r, c, boost) in vessels_px:
        r, c = int(round(r)), int(round(c))
        if 2 <= r < n - 2 and 2 <= c < n - 2:
            sigma_lin[r - 1:r + 2, c - 1:c + 2] += boost * sigma_lin.mean() * 40.0

    # --- speckle: multiplicative Gamma(L, 1/L)- the defining SAR nuisance
    L = spec.looks
    speckle = rng.gamma(shape=L, scale=1.0 / L, size=(n, n))
    obs = sigma_lin * speckle
    # Thermal noise floor keeps very dark pixels from going to -inf dB.
    obs += rng.gamma(shape=2.0, scale=1e-4, size=(n, n))

    db = 10.0 * np.log10(np.clip(obs, 1e-6, None))
    return Scene(sigma0_db=db.astype(np.float32), truth_mask=truth, spec=spec,
                 meta=dict(mean_wind=float(np.mean(np.hypot(uw, vw))),
                           lookalikes=int(n_lookalikes),
                           lookalike_mask=(lookalike > 0.55) | bio))
