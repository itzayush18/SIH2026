"""Coastline lookup.

Ships a hand-simplified Indian coast polyline for the demo. If
`oiltrace/data/coast.geojson` (a Natural Earth 50m file, ~2 MB) is present,
that gets loaded instead. Contract is identical.
"""
from __future__ import annotations

import json
import math
import os
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_HERE, "data", "coast.geojson")

# Simplified Indian coast (west, south, east)- ~40 vertices, good to ~15 km.
_SIMPLE = {
    "type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"name": "Indian coast (simplified)"},
        "geometry": {"type": "MultiLineString", "coordinates": [
            [[68.8, 23.7], [69.2, 22.5], [70.1, 21.8], [72.5, 21.7],
             [72.9, 20.7], [72.7, 19.1], [73.2, 17.0], [74.1, 15.3],
             [74.9, 12.9], [75.4, 11.7], [76.3, 10.0], [77.5, 8.1],
             [78.2, 8.4], [79.3, 10.3], [79.9, 11.9], [80.3, 13.1],
             [82.3, 16.9], [83.2, 17.7], [86.5, 20.3], [87.5, 21.5],
             [88.9, 21.7], [89.1, 22.2]],
            [[92.7, 11.7], [93.0, 12.6], [93.0, 13.3], [92.7, 13.7]],
            [[91.4, 6.8], [92.7, 6.8], [93.0, 7.2]]]}}]}


def load():
    if os.path.exists(_PATH):
        with open(_PATH) as f:
            return json.load(f)
    return _SIMPLE


def geojson():
    """Return the coastline for the /api/coast.geojson endpoint."""
    return load()
