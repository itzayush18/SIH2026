"""Landfall + coastal impact timeline — spec §43.

Take the forward drift cloud and, at each half-hour tick, compute the fraction
of parcels within a distance threshold of the coastline. That's a crude but
honest proxy for landfall probability over time.
"""
from __future__ import annotations

import math

from .coast import load as load_coast


def _min_distance_to_coast_km(lat, lon, coast_lines):
    """Nearest great-circle distance from (lat,lon) to any coastline vertex."""
    R = 6371.0
    p1 = math.radians(lat)
    best = 1e9
    for line in coast_lines:
        for co in line:
            p2 = math.radians(co[1])
            dp = p2 - p1
            dl = math.radians(co[0] - lon)
            a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
            d = 2*R*math.asin(min(1.0, math.sqrt(a)))
            if d < best: best = d
    return best


def series(forecast, near_km=30.0):
    """Return `t_rel_h -> {landfall_frac, mean_dist_km}` across the forecast."""
    coast_gj = load_coast()
    lines = []
    for feat in coast_gj["features"]:
        g = feat["geometry"]
        if g["type"] == "LineString":
            lines.append(g["coordinates"])
        elif g["type"] == "MultiLineString":
            lines.extend(g["coordinates"])

    out = []
    for snap in forecast:
        pts = snap["points"]
        dists = [_min_distance_to_coast_km(p[1], p[0], lines) for p in pts]
        if not dists:
            continue
        near = sum(1 for d in dists if d <= near_km) / len(dists)
        out.append(dict(t_rel_h=snap["t_rel_h"],
                        landfall_frac=near,
                        mean_dist_km=sum(dists)/len(dists),
                        min_dist_km=min(dists)))
    return out
