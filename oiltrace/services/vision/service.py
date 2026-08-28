"""
OilTrace — Vision service.

Responsible for:
  - Preprocessing SAR imagery (calibration, speckle filter, land masking)
  - Running oil-spill segmentation inference
  - Vectorising binary mask to GeoJSON polygons
  - Computing geometry metrics (area, perimeter, compactness)

Scaffold pass: returns a hardcoded demo polygon.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from packages.schemas.models import DetectionRun, Slick, JobState


# A small demo polygon (roughly in the Arabian Sea, off Mumbai coast)
_DEMO_POLYGON: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [[
        [72.85, 18.95],
        [72.87, 18.95],
        [72.87, 18.97],
        [72.86, 18.98],
        [72.85, 18.97],
        [72.85, 18.95],
    ]],
}


def preprocess_sar(asset_uri: str) -> dict[str, Any]:
    """
    Preprocess a SAR image for segmentation.

    Scaffold: returns a stub metadata dict.
    Production: calibration, speckle filtering, land masking.
    """
    return {
        "asset_uri": asset_uri,
        "preprocessed": True,
        "steps": ["calibration_stub", "speckle_filter_stub", "land_mask_stub"],
    }


def run_detection(case_id: str, asset_id: str) -> DetectionRun:
    """
    Execute oil-spill detection on a registered asset.

    Scaffold: immediately returns a completed run with one stub slick.
    Production: queues GPU inference, streams tiles, merges outputs.

    Args:
        case_id: Parent case identifier.
        asset_id: The source asset to analyse.

    Returns:
        DetectionRun with status and slick count.
    """
    run_id = f"det_{uuid.uuid4().hex[:12]}"
    return DetectionRun(
        run_id=run_id,
        case_id=case_id,
        asset_id=asset_id,
        status=JobState.completed,
        model_version="stub_v0",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        slick_count=1,
    )


def get_stub_slick(run_id: str, case_id: str) -> Slick:
    """Return a single hardcoded slick for demo purposes."""
    return Slick(
        slick_id=f"slk_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        case_id=case_id,
        polygon=_DEMO_POLYGON,
        area_km2=4.2,
        perimeter_km=9.7,
        compactness=0.56,
    )


def vectorise_mask(binary_mask: Any) -> list[dict[str, Any]]:
    """
    Convert a binary segmentation mask to GeoJSON polygons.

    Scaffold: ignores input, returns the demo polygon.
    Production: rasterio.features.shapes + simplification.
    """
    return [_DEMO_POLYGON]
