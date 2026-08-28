"""
OilTrace — Geospatial utility functions.

Uses shapely for geometry operations (prebuilt wheels, no GDAL needed).
All coordinates are EPSG:4326 (lon/lat) unless noted otherwise.
"""

from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Polygon, shape, mapping


# Earth radius in km (WGS-84 mean)
_EARTH_RADIUS_KM = 6371.0


def geodesic_distance_km(
    lon1: float, lat1: float, lon2: float, lat2: float
) -> float:
    """
    Approximate geodesic distance using the Haversine formula.

    Args:
        lon1, lat1: First point (degrees).
        lon2, lat2: Second point (degrees).

    Returns:
        Distance in kilometres.
    """
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def polygon_area_km2(geojson_polygon: dict[str, Any]) -> float:
    """
    Estimate the area of a GeoJSON polygon in km².

    Uses shapely planar area as a rough proxy (adequate for scaffold).
    A proper geodesic area calculation would use pyproj in production.
    """
    geom = shape(geojson_polygon)
    # Very rough: 1 degree ≈ 111 km at equator
    return abs(geom.area) * (111.0 ** 2)


def polygon_perimeter_km(geojson_polygon: dict[str, Any]) -> float:
    """Estimate the perimeter of a GeoJSON polygon in km."""
    geom = shape(geojson_polygon)
    return geom.length * 111.0


def make_circle_geojson(
    center_lon: float, center_lat: float, radius_km: float, segments: int = 64
) -> dict[str, Any]:
    """
    Generate a GeoJSON Polygon approximating a circle.

    Useful for creating AOI boundaries and search radii.
    """
    coords = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        # Approximate offset in degrees
        dlat = (radius_km / 111.0) * math.cos(angle)
        dlon = (radius_km / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(angle)
        coords.append((center_lon + dlon, center_lat + dlat))
    return mapping(Polygon(coords))


def ensure_epsg4326(crs_string: str) -> bool:
    """Check whether a CRS string looks like EPSG:4326."""
    normalised = crs_string.strip().upper().replace(" ", "")
    return normalised in ("EPSG:4326", "WGS84", "WGS 84", "CRS84")
