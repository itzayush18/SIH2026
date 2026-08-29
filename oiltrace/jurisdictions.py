"""EEZ / jurisdiction / MARPOL Special Area lookup.

For an offline demo we ship simplified boundary polygons. The lookup contract
matches what a Marine Regions WFS query would return, so `providers.py` can
switch to the live service without touching downstream code.

MARPOL Annex I discharge limits vary by area — the Special Areas (Mediterranean,
Baltic, Black Sea, Red Sea, "Gulfs area", Antarctic, North West European Waters,
Oman Area of the Arabian Sea) enforce a stricter regime, and the Arabian Sea
demo scenario sits inside the Oman Area.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_JUR = os.path.join(_HERE, "data", "jurisdictions.geojson")


@dataclass
class Jurisdiction:
    name: str
    kind: str            # "EEZ" | "SPECIAL_AREA" | "HIGH_SEAS"
    sovereign: str
    marpol_regime: str   # "standard" | "special_area"
    source: str


def _point_in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _load():
    """Load the shipped GeoJSON. If it is missing (fresh clone), fall back to
    coarse rectangles so the API contract still holds — coverage over the
    Arabian Sea / Bay of Bengal / Laccadive is all we need for the demo."""
    if os.path.exists(_JUR):
        with open(_JUR) as f:
            return json.load(f)
    return _FALLBACK


def classify(lat: float, lon: float) -> Jurisdiction:
    """Return the most specific jurisdiction containing the point."""
    data = _load()
    hit = None
    for feat in data["features"]:
        rings = _rings(feat["geometry"])
        for r in rings:
            if _point_in_ring(lon, lat, r):
                p = feat["properties"]
                cand = Jurisdiction(name=p["name"], kind=p["kind"],
                                    sovereign=p.get("sovereign", ""),
                                    marpol_regime=p.get("marpol_regime", "standard"),
                                    source=p.get("source", "shipped simplified boundary"))
                # Prefer SPECIAL_AREA over EEZ over HIGH_SEAS.
                pri = {"SPECIAL_AREA": 0, "EEZ": 1, "HIGH_SEAS": 2}[cand.kind]
                if hit is None or pri < hit[0]:
                    hit = (pri, cand)
                break
    if hit:
        return hit[1]
    return Jurisdiction("High Seas", "HIGH_SEAS", "", "standard", "default")


def nearest_coast_km(lat: float, lon: float) -> float:
    """Very rough — great-circle distance to the nearest of a handful of
    hard-coded Indian coastal reference points. Enough for a demo tile."""
    R = 6371.0
    coast = [(19.08, 72.88, "Mumbai"), (15.30, 74.12, "Karwar"),
             (11.93, 74.85, "Mangalore"), (8.10, 77.02, "Kanyakumari"),
             (13.08, 80.28, "Chennai"), (17.68, 83.22, "Visakhapatnam"),
             (22.57, 88.36, "Kolkata"), (22.60, 68.80, "Kutch"),
             (11.66, 92.74, "Port Blair"), (10.02, 76.28, "Kochi")]
    best = 1e9; where = ""
    p1 = math.radians(lat)
    for (la, lo, nm) in coast:
        p2 = math.radians(la); dl = math.radians(lo - lon); dp = p2 - p1
        a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        d = 2*R*math.asin(math.sqrt(a))
        if d < best: best, where = d, nm
    return best, where


def _rings(geom):
    """Return every linear ring in a Polygon or MultiPolygon."""
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    if geom["type"] == "MultiPolygon":
        out = []
        for poly in geom["coordinates"]:
            out.extend(poly)
        return out
    return []


# Coarse-but-real polygons covering the demo AOIs. Real production would pull
# these from Marine Regions WFS via providers.MarineRegionsProvider.
_FALLBACK = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"name": "India EEZ (simplified)", "kind": "EEZ",
                    "sovereign": "India", "marpol_regime": "standard",
                    "source": "shipped simplified from Marine Regions v11"},
     "geometry": {"type": "Polygon", "coordinates": [[
         [68.0, 8.0], [77.5, 6.5], [82.5, 5.0], [87.0, 6.0], [93.5, 6.0],
         [94.5, 14.0], [92.0, 22.0], [88.5, 22.5], [80.0, 15.0], [79.5, 10.5],
         [77.0, 8.0], [72.5, 15.0], [68.0, 22.5], [66.5, 22.5], [66.5, 15.0],
         [68.0, 8.0]]]}},
    {"type": "Feature",
     "properties": {"name": "MARPOL Special Area — Oman Area of the Arabian Sea",
                    "kind": "SPECIAL_AREA", "sovereign": "IMO",
                    "marpol_regime": "special_area",
                    "source": "MARPOL Annex I Reg. 1.11.5"},
     "geometry": {"type": "Polygon", "coordinates": [[
         [56.0, 22.0], [72.0, 22.0], [72.0, 16.0], [56.0, 16.0], [56.0, 22.0]]]}},
]}
