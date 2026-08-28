"""
OilTrace — Drift hindcasting service.

Responsible for:
  - Configuring OpenDrift/OpenOil simulations
  - Running backward-in-time ensemble particle releases
  - Generating origin-probability contour polygons
  - Estimating the temporal window of the spill event

Scaffold pass: returns static contour GeoJSON. No real OpenDrift call.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from packages.schemas.models import DriftRun, JobState


# Static demo contours — concentric rings around the demo slick area
_DEMO_CONTOURS: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"probability": 0.9, "label": "90% origin"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [72.84, 18.94],
                    [72.88, 18.94],
                    [72.88, 18.99],
                    [72.84, 18.99],
                    [72.84, 18.94],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {"probability": 0.5, "label": "50% origin"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [72.82, 18.92],
                    [72.90, 18.92],
                    [72.90, 19.01],
                    [72.82, 19.01],
                    [72.82, 18.92],
                ]],
            },
        },
    ],
}


def configure_ensemble(
    case_id: str,
    slick_id: str,
    horizon_hours: float = 48.0,
    ensemble_size: int = 100,
    seed: int = 42,
) -> DriftRun:
    """
    Create a drift-run configuration.

    Scaffold: returns a pre-configured DriftRun.
    Production: builds OpenDrift YAML config, resolves forcing data.
    """
    return DriftRun(
        drift_id=f"dft_{uuid.uuid4().hex[:12]}",
        case_id=case_id,
        slick_id=slick_id,
        forcing_ids=["era5_stub", "hycom_stub"],
        ensemble_size=ensemble_size,
        seed=seed,
        horizon_hours=horizon_hours,
        contours={},
        status=JobState.queued,
    )


def run_ensemble(drift_run: DriftRun) -> DriftRun:
    """
    Execute the drift-hindcast ensemble.

    Scaffold: immediately marks complete and attaches demo contours.
    Production: calls OpenDrift, runs particle simulations, computes KDE.

    Args:
        drift_run: Configured DriftRun to execute.

    Returns:
        Updated DriftRun with contours and completed status.
    """
    drift_run.contours = _DEMO_CONTOURS
    drift_run.status = JobState.completed
    return drift_run


def generate_contours(particle_positions: Any) -> dict[str, Any]:
    """
    Generate origin-probability contour polygons from particle positions.

    Scaffold: ignores input, returns demo contours.
    Production: KDE on final particle positions, marching-squares contouring.
    """
    return _DEMO_CONTOURS
