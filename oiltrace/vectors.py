"""Current + wind vector grids sampled from the ocean model.

Returned as GeoJSON LineStrings so a MapLibre `line` layer can render them
directly- an animated GL streamline layer would look prettier but requires a
custom shader and a lot of ceremony. The line style already conveys direction
via a small arrowhead offset and the fill colour scales with magnitude.
"""
from __future__ import annotations

import numpy as np

from sagar.core.environment import SyntheticOcean
from sagar.core.geoutil import Origin


def _bbox_grid(bounds, n):
    """`bounds` = [[s,w],[n,e]]. Returns a (ny, nx) lat/lon grid."""
    (s, w), (n_, e) = bounds
    lats = np.linspace(s, n_, n)
    lons = np.linspace(w, e, n)
    return lats, lons


def sample(bounds, t_rel_h=0.0, n=24, origin=None):
    """Return a FeatureCollection of small direction lines for currents & wind.

    Each line is a 3-vertex polyline: base -> midpoint -> tip, with the tip
    perturbed to give the line an arrowhead when rendered thick.
    """
    if origin is None:
        origin = Origin((bounds[0][0] + bounds[1][0]) / 2,
                        (bounds[0][1] + bounds[1][1]) / 2)
    ocean = SyntheticOcean(origin)

    lats, lons = _bbox_grid(bounds, n)
    feats = []
    span = max(bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1])
    L = span / n * 0.85     # arrow length in degrees; scales with cell size

    t_s = t_rel_h * 3600.0
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            x, y = origin.to_xy(lat, lon)
            u, v, uw, vw = ocean.sample_xy(t_s, np.array([x]), np.array([y]))
            for kind, ex, ey, cap in (("current", float(u[0]), float(v[0]), 0.7),
                                      ("wind",    float(uw[0]), float(vw[0]), 14.0)):
                m = (ex * ex + ey * ey) ** 0.5
                if m < 1e-3:
                    continue
                # Normalise to a fixed visual length so calm and gale don't span
                # 40x on-screen. Magnitude is reported as a property instead.
                s = min(m / cap, 1.0)
                dx = ex / m * L * s
                dy = ey / m * L * s
                tip = (lon + dx, lat + dy)
                # Two small barbs behind the tip to imply an arrow head.
                bx = tip[0] - 0.28 * dx; by = tip[1] - 0.28 * dy
                perp_x = -dy * 0.22; perp_y = dx * 0.22
                feats.append({
                    "type": "Feature",
                    "properties": {"kind": kind, "magnitude": m,
                                   "unit": "m/s"},
                    "geometry": {"type": "LineString", "coordinates": [
                        [lon, lat], list(tip),
                        [bx + perp_x, by + perp_y], list(tip),
                        [bx - perp_x, by - perp_y]]}})
    return {"type": "FeatureCollection", "features": feats,
            "meta": {"t_rel_h": t_rel_h, "grid": n,
                     "cap": {"current_ms": 0.7, "wind_ms": 14.0}}}
