"""Lagrangian drift engine — forward forecast and backward hindcast.

Oil parcels move with

    u_parcel = u_current + alpha * u_wind10 + u_stokes + turbulent random walk

`alpha` (windage/leeway) is the dominant uncertainty for surface oil, so the
ensemble perturbs it per particle rather than using a single nominal 3%.

Backtracking is the same integrator with dt < 0. That is only strictly valid
for the advective part; the stochastic part is not time-reversible, so instead
of pretending it is we let each backward particle carry its own diffusive
random walk and read the result as a *probability cloud*. Accumulating those
clouds over backward time gives an origin PDF in space **and** time, which is
exactly the search window the AIS attribution stage needs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .geoutil import Origin

WINDAGE_MEAN = 0.030
WINDAGE_SD = 0.006
STOKES_FRACTION = 0.011
K_DIFF = 6.0  # horizontal eddy diffusivity, m^2/s


@dataclass
class DriftResult:
    times: np.ndarray            # seconds relative to scene epoch (negative = past)
    x: np.ndarray                # (n_steps, n_particles) metres
    y: np.ndarray
    origin: Origin

    def latlon_at(self, step):
        lat, lon = self.origin.to_ll(self.x[step], self.y[step])
        return lat, lon


def _seed_from_mask(scene, mask, n_particles, rng):
    rr, cc = np.nonzero(mask)
    if len(rr) == 0:
        raise ValueError("empty slick mask")
    idx = rng.integers(0, len(rr), n_particles)
    r = rr[idx] + rng.uniform(-0.5, 0.5, n_particles)
    c = cc[idx] + rng.uniform(-0.5, 0.5, n_particles)
    return scene.xy_of_pixel(r, c)


def integrate(ocean, x0, y0, t0, duration_s, dt=300.0, backward=False,
              n_particles=None, seed=3, windage=True):
    """RK2 advection + random walk. Returns a DriftResult."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x0, float).copy()
    y = np.asarray(y0, float).copy()
    n = x.size
    alpha = np.clip(rng.normal(WINDAGE_MEAN, WINDAGE_SD, n), 0.012, 0.055)
    if not windage:
        alpha[:] = 0.0

    step = -dt if backward else dt
    nsteps = int(abs(duration_s) / dt) + 1
    xs = np.empty((nsteps, n)); ys = np.empty((nsteps, n))
    ts = np.empty(nsteps)
    sigma = math.sqrt(2.0 * K_DIFF * dt)

    t = t0
    for k in range(nsteps):
        xs[k], ys[k], ts[k] = x, y, t - t0
        u1, v1, uw1, vw1 = ocean.sample_xy(t, x, y)
        vx1 = u1 + alpha * uw1 + STOKES_FRACTION * uw1
        vy1 = v1 + alpha * vw1 + STOKES_FRACTION * vw1
        xm, ym = x + vx1 * step * 0.5, y + vy1 * step * 0.5
        u2, v2, uw2, vw2 = ocean.sample_xy(t + step * 0.5, xm, ym)
        vx2 = u2 + alpha * uw2 + STOKES_FRACTION * uw2
        vy2 = v2 + alpha * vw2 + STOKES_FRACTION * vw2
        x = x + vx2 * step + rng.normal(0, sigma, n)
        y = y + vy2 * step + rng.normal(0, sigma, n)
        t += step
    return DriftResult(times=ts, x=xs, y=ys, origin=ocean.origin)


def hindcast(scene, ocean, mask, hours_back=24.0, n_particles=4000, dt=300.0, seed=3):
    rng = np.random.default_rng(seed)
    x0, y0 = _seed_from_mask(scene, mask, n_particles, rng)
    return integrate(ocean, x0, y0, scene.spec.epoch, hours_back * 3600.0,
                     dt=dt, backward=True, seed=seed)


def forecast(scene, ocean, mask, hours_fwd=24.0, n_particles=4000, dt=300.0, seed=5):
    rng = np.random.default_rng(seed)
    x0, y0 = _seed_from_mask(scene, mask, n_particles, rng)
    return integrate(ocean, x0, y0, scene.spec.epoch, hours_fwd * 3600.0,
                     dt=dt, backward=False, seed=seed)


def origin_pdf(res: DriftResult, cell_m=500.0, time_bin_s=1800.0, extent_m=None):
    """Space-time origin probability from a backward run.

    Returns a dict with a (n_tbins, ny, nx) normalised density plus its axes.
    Each backward time slice answers: "if the release happened `dt` ago, where
    would it have been?" The AIS stage integrates a vessel's track against this.
    """
    all_x, all_y = res.x, res.y
    if extent_m is None:
        pad = 3 * cell_m
        x0, x1 = all_x.min() - pad, all_x.max() + pad
        y0, y1 = all_y.min() - pad, all_y.max() + pad
    else:
        x0, x1, y0, y1 = extent_m
    nx = max(2, int((x1 - x0) / cell_m))
    ny = max(2, int((y1 - y0) / cell_m))
    xedges = np.linspace(x0, x1, nx + 1)
    yedges = np.linspace(y0, y1, ny + 1)

    t = np.abs(res.times)
    nbins = max(1, int(math.ceil(t.max() / time_bin_s)))
    tbin = np.clip((t / time_bin_s).astype(int), 0, nbins - 1)

    vol = np.zeros((nbins, ny, nx))
    for b in range(nbins):
        sel = tbin == b
        if not sel.any():
            continue
        h, _, _ = np.histogram2d(res.y[sel].ravel(), res.x[sel].ravel(),
                                 bins=[yedges, xedges])
        vol[b] = h
    total = vol.sum()
    if total > 0:
        vol /= total
    return dict(density=vol, xedges=xedges, yedges=yedges,
                t_centers=-(np.arange(nbins) + 0.5) * time_bin_s,
                cell_m=cell_m, time_bin_s=time_bin_s, origin=res.origin)


def pdf_lookup(pdf, t_rel, x, y):
    """Probability density at a space-time point (t relative to scene epoch)."""
    tc = pdf["t_centers"]
    if len(tc) == 0:
        return 0.0
    b = int(np.argmin(np.abs(tc - t_rel)))
    if abs(tc[b] - t_rel) > pdf["time_bin_s"]:
        return 0.0
    xe, ye = pdf["xedges"], pdf["yedges"]
    if not (xe[0] <= x <= xe[-1] and ye[0] <= y <= ye[-1]):
        return 0.0
    i = min(int((x - xe[0]) / (xe[1] - xe[0])), pdf["density"].shape[2] - 1)
    j = min(int((y - ye[0]) / (ye[1] - ye[0])), pdf["density"].shape[1] - 1)
    return float(pdf["density"][b, j, i])


def pdf_peak(pdf):
    """Most likely (time, lat, lon) of release."""
    d = pdf["density"]
    b, j, i = np.unravel_index(int(np.argmax(d)), d.shape)
    xe, ye = pdf["xedges"], pdf["yedges"]
    x = 0.5 * (xe[i] + xe[i + 1]); y = 0.5 * (ye[j] + ye[j + 1])
    lat, lon = pdf["origin"].to_ll(x, y)
    return dict(t_rel_s=float(pdf["t_centers"][b]), lat=float(lat), lon=float(lon),
                prob=float(d[b, j, i]))
