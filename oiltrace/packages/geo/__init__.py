"""OilTrace geo utilities — CRS, distance, geometry helpers."""

from packages.geo.utils import (
    geodesic_distance_km,
    polygon_area_km2,
    polygon_perimeter_km,
    make_circle_geojson,
    ensure_epsg4326,
)

__all__ = [
    "geodesic_distance_km",
    "polygon_area_km2",
    "polygon_perimeter_km",
    "make_circle_geojson",
    "ensure_epsg4326",
]
