"""AIS ingestion, track reconstruction and behavioural feature extraction.

Column names follow the MarineCadastre AIS export schema
(https://marinecadastre.gov/accessais/) so a real CSV drops straight in:

    MMSI, BaseDateTime, LAT, LON, SOG, COG, Heading, VesselName, IMO,
    CallSign, VesselType, Status, Length, Width, Draft, Cargo

`synthesize()` builds a demonstrative traffic picture for a region when no real
feed is available, including one true polluter and three decoys designed to
defeat naive scoring (right place/wrong time, right time/wrong place, and a
transit with no anomalous behaviour).
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .geoutil import Origin, haversine, bearing, angdiff

# AIS reporting interval is 2-10 s underway; anything beyond this is a gap.
GAP_THRESHOLD_S = 900.0

VESSEL_TYPES = {80: "Tanker", 70: "Cargo", 60: "Passenger", 30: "Fishing", 52: "Tug"}


@dataclass
class Ping:
    t: float      # seconds relative to scene epoch
    lat: float
    lon: float
    sog: float    # knots
    cog: float    # degrees


@dataclass
class Vessel:
    mmsi: str
    name: str
    vtype: int
    length: float
    draft: float
    pings: List[Ping] = field(default_factory=list)

    @property
    def type_name(self):
        return VESSEL_TYPES.get(self.vtype, f"Type{self.vtype}")

    def sorted_pings(self):
        return sorted(self.pings, key=lambda p: p.t)

    def position_at(self, t):
        """Linear interpolation between reports; None outside coverage.

        Deliberately does *not* extrapolate across a gap boundary- a dark
        period is evidence, not something to paper over. `gaps()` exposes it.
        """
        ps = self.sorted_pings()
        if not ps or t < ps[0].t or t > ps[-1].t:
            return None
        for a, b in zip(ps, ps[1:]):
            if a.t <= t <= b.t:
                span = b.t - a.t
                if span <= 0:
                    return (a.lat, a.lon, a.sog, a.cog, span)
                f = (t - a.t) / span
                return (a.lat + f * (b.lat - a.lat), a.lon + f * (b.lon - a.lon),
                        a.sog + f * (b.sog - a.sog), a.cog, span)
        p = ps[-1]
        return (p.lat, p.lon, p.sog, p.cog, 0.0)

    def gaps(self, threshold=GAP_THRESHOLD_S):
        ps = self.sorted_pings()
        return [(a.t, b.t) for a, b in zip(ps, ps[1:]) if b.t - a.t > threshold]

    def track_geojson(self):
        """[lon, lat, t_rel_s] triples- the time is what lets the map animate
        vessel positions rather than only draw static polylines."""
        return [[p.lon, p.lat, p.t] for p in self.sorted_pings()]


# ------------------------------------------------------------------ ingestion
def load_csv(path, epoch_iso=None) -> Dict[str, Vessel]:
    """Read a MarineCadastre-style CSV. Times become seconds relative to
    `epoch_iso` (defaults to the latest timestamp in the file)."""
    import datetime as dt

    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                ts = dt.datetime.fromisoformat(row["BaseDateTime"])
            except (KeyError, ValueError):
                continue
            rows.append((ts, row))
    if not rows:
        return {}
    epoch = dt.datetime.fromisoformat(epoch_iso) if epoch_iso else max(r[0] for r in rows)

    vessels: Dict[str, Vessel] = {}
    for ts, row in rows:
        mmsi = str(row.get("MMSI", "")).strip()
        if not mmsi:
            continue
        v = vessels.get(mmsi)
        if v is None:
            v = vessels[mmsi] = Vessel(
                mmsi=mmsi, name=row.get("VesselName") or f"MMSI {mmsi}",
                vtype=int(float(row.get("VesselType") or 0)),
                length=float(row.get("Length") or 0), draft=float(row.get("Draft") or 0))
        v.pings.append(Ping(t=(ts - epoch).total_seconds(),
                            lat=float(row["LAT"]), lon=float(row["LON"]),
                            sog=float(row.get("SOG") or 0), cog=float(row.get("COG") or 0)))
    return vessels


def write_csv(path, vessels: Dict[str, Vessel], epoch_iso="2026-03-14T06:00:00"):
    import datetime as dt
    epoch = dt.datetime.fromisoformat(epoch_iso)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading",
                    "VesselName", "IMO", "CallSign", "VesselType", "Status",
                    "Length", "Width", "Draft", "Cargo"])
        for v in vessels.values():
            for p in v.sorted_pings():
                ts = (epoch + dt.timedelta(seconds=p.t)).isoformat()
                w.writerow([v.mmsi, ts, f"{p.lat:.6f}", f"{p.lon:.6f}", f"{p.sog:.1f}",
                            f"{p.cog:.1f}", f"{p.cog:.0f}", v.name, "", "",
                            v.vtype, 0, f"{v.length:.0f}",
                            f"{v.length/7:.0f}", f"{v.draft:.1f}", ""])


# ----------------------------------------------------------------- synthesis
def _lay_track(origin: Origin, start_xy, course_deg, speed_kn, t0, t1, dt=120.0,
               jitter=25.0, rng=None, waypoints=None):
    """Emit pings along a constant-course leg (or through waypoints)."""
    rng = rng or np.random.default_rng(0)
    x, y = start_xy
    pings = []
    t = t0
    c = course_deg
    while t <= t1:
        if waypoints:
            for wt, wc, ws in waypoints:
                if t >= wt:
                    c, speed_kn = wc, ws
        lat, lon = origin.to_ll(x + rng.normal(0, jitter), y + rng.normal(0, jitter))
        pings.append(Ping(t=t, lat=lat, lon=lon, sog=speed_kn + rng.normal(0, 0.15),
                          cog=(c + rng.normal(0, 1.5)) % 360))
        v = speed_kn * 0.514444
        x += v * math.sin(math.radians(c)) * dt
        y += v * math.cos(math.radians(c)) * dt
        t += dt
    return pings


def synthesize(origin: Origin, true_origin_xy, true_release_t, seed=17,
               t_start=-30 * 3600.0, t_end=1 * 3600.0) -> Dict[str, Vessel]:
    """Build a traffic picture containing one true polluter and several decoys.

    `true_origin_xy` / `true_release_t` are the ground-truth spill location and
    time in local metres / seconds-relative-to-scene-epoch.
    """
    rng = np.random.default_rng(seed)
    vessels: Dict[str, Vessel] = {}
    ox, oy = true_origin_xy

    def add(mmsi, name, vtype, length, draft, pings):
        vessels[mmsi] = Vessel(mmsi, name, vtype, length, draft, pings)

    # -- 1. The polluter: transits the origin at the release time, slows to a
    #       crawl while discharging, alters course, and goes dark for 40 min.
    course = 312.0
    speed = 12.4
    v = speed * 0.514444
    lead = 6 * 3600.0
    sx = ox - v * math.sin(math.radians(course)) * lead
    sy = oy - v * math.cos(math.radians(course)) * lead
    pings = _lay_track(origin, (sx, sy), course, speed, true_release_t - lead,
                       true_release_t + 8 * 3600.0, rng=rng,
                       waypoints=[(true_release_t - 1200.0, 306.0, 5.8),
                                  (true_release_t + 3600.0, 318.0, 12.9)])
    pings = [p for p in pings
             if not (true_release_t + 600 <= p.t <= true_release_t + 3000)]  # dark period
    add("419001234", "MT KAVERI STAR", 80, 244.0, 12.6, pings)

    # -- 2. Decoy A: same lane, right place, but 14 h too early.
    early = true_release_t - 14 * 3600.0
    sx = ox - v * math.sin(math.radians(course)) * lead
    sy = oy - v * math.cos(math.radians(course)) * lead
    add("419005678", "MV KONKAN PRIDE", 70, 190.0, 9.1,
        _lay_track(origin, (sx, sy), course, 13.8, early - lead, early + 5 * 3600.0, rng=rng))

    # -- 3. Decoy B: right time, but 45 km cross-track away.
    add("419009012", "MT ARABIAN DAWN", 80, 210.0, 11.2,
        _lay_track(origin, (ox + 45000.0, oy - 38000.0), 95.0, 11.0,
                   true_release_t - 4 * 3600.0, true_release_t + 6 * 3600.0, rng=rng))

    # -- 4. Decoy C: passes near the origin near the time, but steady speed,
    #       steady course, no gap- behaviourally clean.
    add("419003456", "MV SAHYADRI", 70, 176.0, 8.4,
        _lay_track(origin, (ox - 21000.0, oy + 26000.0), 150.0, 15.2,
                   true_release_t - 3 * 3600.0, true_release_t + 5 * 3600.0, rng=rng))

    # -- 5. Background traffic on the lane and a fishing fleet.
    for i in range(8):
        c0 = rng.choice([128.0, 308.0]) + rng.normal(0, 4)
        off = rng.uniform(-6e4, 6e4)
        st = rng.uniform(t_start, t_end - 6 * 3600.0)
        add(f"41901{i:04d}", f"MV TRANSIT {i+1}", int(rng.choice([70, 70, 80, 60])),
            float(rng.uniform(120, 260)), float(rng.uniform(6, 13)),
            _lay_track(origin, (ox + off, oy + rng.uniform(-6e4, 6e4)), c0,
                       float(rng.uniform(9, 17)), st, st + 8 * 3600.0, rng=rng))
    for i in range(5):
        st = rng.uniform(t_start, t_end - 5 * 3600.0)
        add(f"41902{i:04d}", f"FV MATSYA {i+1}", 30, float(rng.uniform(18, 32)), 2.5,
            _lay_track(origin, (ox + rng.uniform(-5e4, 5e4), oy + rng.uniform(-5e4, 5e4)),
                       float(rng.uniform(0, 360)), 4.0, st, st + 5 * 3600.0, rng=rng,
                       jitter=180.0))
    return vessels
