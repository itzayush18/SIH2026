"""Geodesy helpers: local ENU <-> WGS84 on an equirectangular tangent plane.

At the scales we work at (a Sentinel-1 IW scene is ~250 km) the error of the
equirectangular approximation is well under the 10 m pixel spacing, so we keep
the maths cheap and stay in metres everywhere inside the pipeline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

R_EARTH = 6371008.8  # mean Earth radius, metres


@dataclass(frozen=True)
class Origin:
    """Tangent-plane anchor."""
    lat: float
    lon: float

    def to_xy(self, lat, lon):
        """degrees -> (east, north) metres relative to the anchor.

        Accepts scalars or arrays; the drift engine passes whole particle sets.
        """
        k = math.cos(math.radians(self.lat))
        x = np.radians(np.subtract(lon, self.lon)) * R_EARTH * k
        y = np.radians(np.subtract(lat, self.lat)) * R_EARTH
        return x, y

    def to_ll(self, x, y):
        """(east, north) metres -> (lat, lon) degrees."""
        k = math.cos(math.radians(self.lat))
        lon = self.lon + np.degrees(np.divide(x, R_EARTH * k))
        lat = self.lat + np.degrees(np.divide(y, R_EARTH))
        return lat, lon


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def bearing(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing, degrees clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angdiff(a, b):
    """Smallest absolute difference between two bearings, in degrees."""
    return abs((a - b + 180.0) % 360.0 - 180.0)
