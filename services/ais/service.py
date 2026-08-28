"""
OilTrace — AIS service.

Responsible for:
  - Parsing raw AIS data (CSV, NMEA)
  - Quality-control filtering (out-of-range, duplicate, on-land)
  - Segmenting continuous track segments per MMSI
  - Interpolating gaps in AIS coverage

Scaffold pass: returns mock AIS observations and tracks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from packages.schemas.models import AISObservation, TrackSegment


def _demo_observations(mmsi: str, base_time: datetime) -> list[AISObservation]:
    """Generate a small set of mock AIS observations."""
    points = [
        (72.83, 18.93, 8.5, 225.0),
        (72.84, 18.94, 7.2, 230.0),
        (72.85, 18.95, 6.1, 228.0),
        (72.855, 18.955, 3.0, 220.0),
        (72.86, 18.96, 2.5, 215.0),
        (72.865, 18.965, 4.8, 210.0),
        (72.87, 18.97, 7.0, 205.0),
    ]
    obs = []
    for i, (lon, lat, sog, cog) in enumerate(points):
        obs.append(AISObservation(
            mmsi=mmsi,
            timestamp_utc=base_time + timedelta(minutes=i * 15),
            longitude=lon,
            latitude=lat,
            sog=sog,
            cog=cog,
            nav_status="under_way",
            source="terrestrial",
        ))
    return obs


def parse_ais(raw_data: Any, format: str = "csv") -> list[AISObservation]:
    """
    Parse raw AIS data into structured observations.

    Scaffold: ignores input, returns demo observations.
    Production: CSV/NMEA parser with validation.

    Args:
        raw_data: Raw AIS data (file path or bytes).
        format: Input format — 'csv' or 'nmea'.

    Returns:
        List of parsed AISObservation models.
    """
    base_time = datetime(2026, 8, 20, 2, 0, 0)
    return _demo_observations("538007689", base_time)


def quality_control(observations: list[AISObservation]) -> list[AISObservation]:
    """
    Apply QC filters to raw AIS observations.

    Scaffold: passes everything through (no filtering).
    Production: removes duplicates, out-of-range positions, on-land pings.
    """
    return observations


def segment_tracks(
    observations: list[AISObservation],
    max_gap_minutes: float = 120.0,
) -> list[TrackSegment]:
    """
    Split observations into continuous track segments.

    A new segment starts when the gap between consecutive observations
    exceeds *max_gap_minutes*.

    Scaffold: groups all observations into one segment.
    """
    if not observations:
        return []

    mmsi = observations[0].mmsi
    return [TrackSegment(
        segment_id=f"seg_{uuid.uuid4().hex[:8]}",
        mmsi=mmsi,
        case_id="",  # set by caller
        observations=observations,
        gap_seconds_max=0.0,
        interpolated=False,
    )]


def interpolate_track(
    segment: TrackSegment,
    interval_seconds: float = 60.0,
) -> TrackSegment:
    """
    Interpolate gaps within a track segment.

    Scaffold: marks the segment as interpolated, no actual interpolation.
    Production: cubic spline or great-circle interpolation.
    """
    segment.interpolated = True
    return segment
