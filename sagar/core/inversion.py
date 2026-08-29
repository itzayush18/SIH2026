"""Source-term inversion: recover the release as a *moving line source*.

A pure backward particle cloud cannot localise this kind of spill, and it is
worth being explicit about why. An operational discharge from a vessel underway
is not a point release — it is a line laid down over tens of minutes to hours.
Run the cloud backwards and it never collapses to a point, because the slick's
along-track extent was there from the start. Empirically the backward spread of
our reference scenario contracts by under 2% over 26 h; the "minimum-area
instant" is therefore not a usable estimator.

So instead of inverting the cloud, we invert the *source*. We hypothesise a
release by a vessel steaming at constant course and speed:

    theta = (t_start, duration, course, speed, x0, y0)

forward-advect that line source through the same metocean fields to the
acquisition time, rasterise it, and score it against the observed slick by IoU.
Optimising theta gives a sharp, physically constrained answer *and* — the part
that matters for attribution — a candidate **source track**, which can be
matched directly against AIS tracks rather than only against a probability blob.

Search is a coarse random scan followed by a shrinking-neighbourhood refine
(a poor man's CMA-ES). The objective is multi-modal but broad-basined, so this
is robust enough and stays dependency-free.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
from scipy import ndimage

from .drift import integrate
from .geoutil import Origin


@dataclass
class SourceHypothesis:
    t_start: float      # s relative to scene epoch (negative)
    duration: float     # s
    course_deg: float
    speed_kn: float
    x0: float           # release start, local metres
    y0: float
    iou: float = 0.0

    def track_xy(self, n=40):
        v = self.speed_kn * 0.514444
        ts = np.linspace(self.t_start, self.t_start + self.duration, n)
        d = v * (ts - self.t_start)
        return ts, self.x0 + d * math.sin(math.radians(self.course_deg)), \
            self.y0 + d * math.cos(math.radians(self.course_deg))

    def to_dict(self, origin: Origin):
        ts, xs, ys = self.track_xy()
        pts = []
        for t, x, y in zip(ts, xs, ys):
            lat, lon = origin.to_ll(x, y)
            pts.append(dict(t_rel_s=float(t), lat=float(lat), lon=float(lon)))
        d = asdict(self)
        lat0, lon0 = origin.to_ll(self.x0, self.y0)
        d.update(start_lat=float(lat0), start_lon=float(lon0), track=pts)
        return d


def _simulate_footprint(hyp: SourceHypothesis, ocean, scene, n_rel=16, per_rel=40,
                        dt=600.0, seed=1):
    """Forward-advect the hypothesised line source to the acquisition time."""
    ts, xs, ys = hyp.track_xy(n_rel)
    rng = np.random.default_rng(seed)
    n = scene.spec.size
    acc_r, acc_c = [], []
    for t, x, y in zip(ts, xs, ys):
        span = scene.spec.epoch - t
        if span <= 0:
            continue
        x0 = x + rng.normal(0, 150, per_rel)
        y0 = y + rng.normal(0, 150, per_rel)
        res = integrate(ocean, x0, y0, t, span, dt=dt, backward=False, seed=seed)
        r, c = scene.pixel_of_xy(res.x[-1], res.y[-1])
        acc_r.append(r); acc_c.append(c)
    if not acc_r:
        return np.zeros((n, n), bool)
    r = np.concatenate(acc_r); c = np.concatenate(acc_c)
    ok = (r >= 0) & (r < n) & (c >= 0) & (c < n)
    sim = np.zeros((n, n), bool)
    if ok.any():
        sim[r[ok].astype(int), c[ok].astype(int)] = True
    # Dilate to the parcel footprint so sparse sampling is not penalised.
    return ndimage.binary_dilation(sim, np.ones((9, 9)))


def _iou(a, b):
    inter = float((a & b).sum())
    union = float((a | b).sum())
    return inter / union if union else 0.0


def invert(scene, ocean, mask, n_coarse=180, n_refine=120, seed=3,
           t_window_h=(2.0, 26.0), verbose=False, keep_frac=0.85, keep_max=40):
    """Return the best-fitting SourceHypothesis for the observed slick.

    The returned object also carries `.ensemble` — every hypothesis whose fit
    came within `keep_frac` of the best. This matters: the forward map is not
    fully identifiable. A later release by a faster source can reproduce a very
    similar footprint, so a longer search buys a higher IoU without buying a
    better estimate (measured: 3x the budget raised fit IoU 0.56 -> 0.61 and
    left the position error unchanged at ~14 km). Reporting a single point
    estimate would hide that. Downstream, `source_track_match` scores AIS
    tracks against the whole ensemble, weighted by fit, so attribution degrades
    gracefully instead of hanging on one possibly-degenerate optimum.
    """
    rng = np.random.default_rng(seed)

    # Seed the search near the observed slick, offset upstream by the mean drift.
    rr, cc = np.nonzero(mask)
    cx, cy = scene.xy_of_pixel(rr.mean(), cc.mean())
    u, v, uw, vw = ocean.sample_xy(scene.spec.epoch - 6 * 3600.0, cx, cy)
    dxdt = float(u) + 0.03 * float(uw)
    dydt = float(v) + 0.03 * float(vw)

    def sample():
        th = rng.uniform(*t_window_h) * 3600.0
        t_start = -th
        dur = rng.uniform(0.3, 3.5) * 3600.0
        # Upstream displacement plus generous jitter.
        x0 = cx - dxdt * th + rng.normal(0, 6000)
        y0 = cy - dydt * th + rng.normal(0, 6000)
        return SourceHypothesis(t_start, dur, float(rng.uniform(0, 360)),
                                float(rng.uniform(3.0, 16.0)), float(x0), float(y0))

    best = None
    seen = []
    for i in range(n_coarse):
        h = sample()
        h.iou = _iou(_simulate_footprint(h, ocean, scene, seed=seed + i), mask)
        seen.append(h)
        if best is None or h.iou > best.iou:
            best = h
            if verbose:
                print(f"  coarse {i}: IoU {h.iou:.3f}")

    # Refine: shrink the proposal scale geometrically around the incumbent.
    scale = 1.0
    for i in range(n_refine):
        scale = max(0.08, 1.0 * (0.97 ** i))
        h = SourceHypothesis(
            t_start=float(np.clip(best.t_start + rng.normal(0, 3 * 3600 * scale),
                                  -t_window_h[1] * 3600, -t_window_h[0] * 3600)),
            duration=float(np.clip(best.duration + rng.normal(0, 3600 * scale),
                                   900.0, 5 * 3600.0)),
            course_deg=float((best.course_deg + rng.normal(0, 45 * scale)) % 360),
            speed_kn=float(np.clip(best.speed_kn + rng.normal(0, 4 * scale), 2.0, 20.0)),
            x0=float(best.x0 + rng.normal(0, 5000 * scale)),
            y0=float(best.y0 + rng.normal(0, 5000 * scale)))
        h.iou = _iou(_simulate_footprint(h, ocean, scene, seed=seed + 1000 + i), mask)
        seen.append(h)
        if h.iou > best.iou:
            best = h
            if verbose:
                print(f"  refine {i} (scale {scale:.2f}): IoU {h.iou:.3f}")

    ens = sorted([h for h in seen if h.iou >= keep_frac * best.iou],
                 key=lambda h: -h.iou)[:keep_max]
    best.ensemble = ens
    return best


def search_dispersion(best, origin: Origin):
    """How tightly the near-optimal solutions cluster.

    This is a diagnostic of the *search*, not a calibrated uncertainty, and the
    difference is worth being blunt about: measured across 10 scenarios it
    reports ~1 km while the true position error averages ~9 km and reaches
    17 km. The optimiser converges confidently onto a solution that can still
    be wrong, because the forward map is only weakly identifiable along the
    drift direction. Read a *wide* dispersion as "this inversion is ill-posed,
    distrust it"; do not read a narrow one as "this answer is right".
    """
    ens = getattr(best, "ensemble", None) or [best]
    t = np.array([h.t_start for h in ens]) / 3600.0
    x = np.array([h.x0 for h in ens])
    y = np.array([h.y0 for h in ens])
    # Circular standard deviation for course (Mardia): sqrt(-2 ln R).
    c = np.radians(np.array([h.course_deg for h in ens]))
    R = abs(np.mean(np.exp(1j * c)))
    course_sd = math.degrees(math.sqrt(-2.0 * math.log(max(R, 1e-9))))
    return dict(n=len(ens),
                t_start_sd_h=float(t.std()),
                position_sd_km=float(math.hypot(x.std(), y.std()) / 1000.0),
                course_sd_deg=float(min(course_sd, 180.0)),
                iou_range=[float(min(h.iou for h in ens)),
                           float(max(h.iou for h in ens))])


def _match_one(vessel, hyp, origin, n):
    ts, xs, ys = hyp.track_xy(n)
    seps, used = [], 0
    for t, x, y in zip(ts, xs, ys):
        pos = vessel.position_at(float(t))
        if pos is None:
            continue
        lat, lon, *_ = pos
        vx, vy = origin.to_xy(lat, lon)
        seps.append(math.hypot(vx - x, vy - y))
        used += 1
    if used < max(3, n // 3):
        return 0.0, float("nan")
    mean_sep = float(np.mean(seps))
    coverage = used / n
    # 5 km half-width: inside it the match is decisive, beyond ~15 km it is noise.
    return float(coverage * math.exp(-(mean_sep / 5000.0) ** 2)), mean_sep / 1000.0


def source_track_match(vessel, hyp: SourceHypothesis, origin: Origin, n=25):
    """How well does an AIS track coincide with the inverted source?

    Returns (score in 0..1, mean separation in km). Sampled at the hypothesised
    release *times*, so it tests space and time simultaneously — a vessel that
    sailed the same line six hours later scores zero.

    Scored against the whole retained ensemble, IoU-weighted, so a single
    degenerate optimum cannot decide the attribution on its own. The reported
    separation is that of the best-matching ensemble member, which is what an
    analyst wants to see.
    """
    ens = getattr(hyp, "ensemble", None) or [hyp]
    num = den = 0.0
    best_s, best_sep = 0.0, float("nan")
    for h in ens:
        s, sep = _match_one(vessel, h, origin, n)
        w = max(h.iou, 1e-6)
        num += w * s
        den += w
        if s > best_s:
            best_s, best_sep = s, sep
    return float(num / den) if den else 0.0, best_sep
