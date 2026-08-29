"""Spill-to-vessel attribution.

The hindcast gives a space-time origin PDF. Attribution asks, for every vessel
in the reconstructed traffic picture: *how much of that PDF did this vessel
actually sail through, and did it behave like a ship that was discharging?*

Score = sigmoid( sum_i w_i * z_i ), over five evidence axes:

  0. **Source-track match** — the strongest term. `inversion.py` recovers the
     hypothesised release as a moving line source; this measures how closely an
     AIS track shadows that line *at the hypothesised release times*. A vessel
     that sailed the same water six hours later scores ~0.
  1. **Spatio-temporal coincidence** — the vessel track integrated against the
     backward origin PDF. Coarser than term 0 but robust when the inversion
     fits poorly (weak drift, ambiguous slick shape).
  2. **Track/slick axis alignment** — an operational discharge is laid along the
     ship's course, so the slick's major axis should match the vessel's COG.
  3. **Behavioural anomaly** — speed reduction, course alteration, loitering.
  4. **AIS dark period** overlapping the release window.
  5. **Vessel prior** — type, size and draft. Weakest term by design; it must
     never be able to convict on its own.

Every term is reported with a human-readable reason so an analyst can audit the
ranking rather than trust a black box. The output is explicitly a *lead*, not a
finding of guilt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .drift import pdf_lookup
from .geoutil import angdiff
from .inversion import source_track_match

WEIGHTS = dict(source_match=3.2, spatiotemporal=2.4, alignment=1.0,
               behaviour=1.6, dark=1.2, prior=0.7)
BIAS = -3.4

# Vessel-type prior: how plausible is an operational oil discharge?
TYPE_PRIOR = {80: 1.0, 70: 0.65, 60: 0.35, 52: 0.4, 30: 0.15}


@dataclass
class Suspect:
    mmsi: str
    name: str
    type_name: str
    length: float
    score: float
    terms: dict
    evidence: List[str] = field(default_factory=list)
    closest_approach_km: float = float("nan")
    closest_approach_t: float = float("nan")
    source_separation_km: float = float("nan")
    track: list = field(default_factory=list)

    def to_dict(self):
        d = self.__dict__.copy()
        return d


def _sample_track(vessel, pdf, origin, t_lo, t_hi, step=300.0):
    """Walk the vessel's interpolated track through the PDF's time span."""
    hits = []
    t = t_lo
    while t <= t_hi:
        pos = vessel.position_at(t)
        if pos is not None:
            lat, lon, sog, cog, _ = pos
            x, y = origin.to_xy(lat, lon)
            hits.append((t, x, y, sog, cog, pdf_lookup(pdf, t, x, y)))
        t += step
    return hits


def _behaviour_terms(vessel, t_lo, t_hi):
    """Speed-drop, course-change and loiter anomalies inside the release window."""
    ps = vessel.sorted_pings()
    if len(ps) < 6:
        return 0.0, []
    sogs = np.array([p.sog for p in ps])
    base = float(np.median(sogs))
    inwin = [p for p in ps if t_lo <= p.t <= t_hi]
    reasons = []
    score = 0.0
    if inwin and base > 3.0:
        smin = min(p.sog for p in inwin)
        drop = (base - smin) / base
        if drop > 0.25:
            score += min(drop / 0.5, 1.0) * 0.55
            reasons.append(f"speed fell {drop*100:.0f}% below its own transit median "
                           f"({base:.1f} kn -> {smin:.1f} kn) inside the release window")
    if len(inwin) >= 2:
        cogs = [p.cog for p in inwin]
        turn = max(angdiff(a, b) for a in cogs for b in cogs)
        if turn > 12.0:
            score += min(turn / 45.0, 1.0) * 0.35
            reasons.append(f"altered course by {turn:.0f} deg during the window")
    if inwin and min(p.sog for p in inwin) < 2.0:
        score += 0.25
        reasons.append("effectively stopped/loitering at the origin")
    return min(score, 1.0), reasons


def _dark_term(vessel, t_lo, t_hi):
    gaps = vessel.gaps()
    if not gaps:
        return 0.0, []
    win = max(t_hi - t_lo, 1.0)
    overlap = sum(max(0.0, min(b, t_hi) - max(a, t_lo)) for a, b in gaps)
    if overlap <= 0:
        return 0.0, []
    frac = min(overlap / win, 1.0)
    return frac, [f"AIS silent for {overlap/60:.0f} min "
                  f"({frac*100:.0f}% of the release window) — transponder gap"]


def _alignment_term(hits, slick_orientation_deg):
    """Mean |cos| between vessel COG and the slick's major axis, weighted by PDF."""
    wsum = sum(h[5] for h in hits)
    if wsum <= 0:
        return 0.0, []
    a = 0.0
    for _, _, _, _, cog, p in hits:
        d = angdiff(cog % 180.0, slick_orientation_deg % 180.0)
        a += p * math.cos(math.radians(2 * d)) * 0.5 + p * 0.5
    val = max(0.0, min(a / wsum, 1.0))
    if val > 0.6:
        return val, [f"course lies within {angdiff(hits[0][4] % 180, slick_orientation_deg % 180):.0f} deg "
                     f"of the slick's major axis ({slick_orientation_deg:.0f} deg) — "
                     f"consistent with a slick laid along track"]
    return val, []


def rank(vessels: Dict[str, object], pdf, detection, origin, min_prob_frac=1e-4,
         top_n=10, source_hyp=None) -> List[Suspect]:
    t_centers = pdf["t_centers"]
    if len(t_centers) == 0:
        return []
    t_lo, t_hi = float(min(t_centers)), float(max(t_centers))
    # Widen slightly so a vessel that transited just outside the binning is
    # still evaluated rather than silently dropped.
    t_lo -= pdf["time_bin_s"]; t_hi += pdf["time_bin_s"]

    raw = []
    for v in vessels.values():
        hits = _sample_track(v, pdf, origin, t_lo, t_hi)
        if not hits:
            continue
        st = sum(h[5] for h in hits)
        raw.append((v, hits, st))
    if not raw:
        return []

    # --- Stage 1: filter irrelevant traffic. A vessel whose track never
    # intersects the origin envelope, and which does not shadow the inverted
    # source track, cannot be scored and is dropped before ranking.
    st_max = max(r[2] for r in raw) or 1.0
    kept = []
    for v, hits, st in raw:
        sm, sep = ((0.0, float("nan")) if source_hyp is None else
                   source_track_match(v, source_hyp, origin))
        if st >= min_prob_frac * st_max or sm > 0.05:
            kept.append((v, hits, st, sm, sep))

    suspects = []
    for v, hits, st, sm, sep in kept:
        st_n = st / st_max                       # 0..1 spatio-temporal coincidence
        align, r_align = _alignment_term(hits, detection.orientation_deg)
        beh, r_beh = _behaviour_terms(v, t_lo, t_hi)
        dark, r_dark = _dark_term(v, t_lo, t_hi)
        prior = TYPE_PRIOR.get(v.vtype, 0.3) * min(1.0, 0.4 + v.length / 300.0)

        z = (BIAS + WEIGHTS["source_match"] * sm
             + WEIGHTS["spatiotemporal"] * st_n + WEIGHTS["alignment"] * align
             + WEIGHTS["behaviour"] * beh + WEIGHTS["dark"] * dark
             + WEIGHTS["prior"] * prior)
        score = 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, z))))

        # Closest approach to the PDF peak cell, for the analyst's report.
        best = max(hits, key=lambda h: h[5])
        px, py = origin.to_xy(*_peak_ll(pdf))
        d_km = math.hypot(best[1] - px, best[2] - py) / 1000.0

        ev = []
        if sm > 0.2:
            ev.append(f"shadows the inverted source track — mean separation "
                      f"{sep:.1f} km at the hypothesised release times "
                      f"(match {sm*100:.0f}%)")
        if st_n > 0.15:
            ev.append(f"track passes through the reconstructed origin envelope "
                      f"(coincidence {st_n*100:.0f}% of the best-scoring vessel)")
        ev += r_align + r_beh + r_dark
        if prior > 0.7:
            ev.append(f"{v.type_name.lower()}, {v.length:.0f} m — carries the cargo/bunkers "
                      f"consistent with the observed slick volume")
        if not ev:
            ev.append("present in the search window but no corroborating evidence")

        suspects.append(Suspect(
            mmsi=v.mmsi, name=v.name, type_name=v.type_name, length=v.length,
            score=score,
            terms=dict(source_match=sm, spatiotemporal=st_n, alignment=align,
                       behaviour=beh, dark=dark, prior=prior),
            source_separation_km=sep,
            evidence=ev, closest_approach_km=d_km, closest_approach_t=best[0],
            track=v.track_geojson()))

    suspects.sort(key=lambda s: -s.score)
    return suspects[:top_n]


def _peak_ll(pdf):
    d = pdf["density"]
    b, j, i = np.unravel_index(int(np.argmax(d)), d.shape)
    x = 0.5 * (pdf["xedges"][i] + pdf["xedges"][i + 1])
    y = 0.5 * (pdf["yedges"][j] + pdf["yedges"][j + 1])
    return pdf["origin"].to_ll(x, y)
