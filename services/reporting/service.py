"""
OilTrace — Reporting service.

Responsible for:
  - Exporting case data as GeoJSON feature collections
  - Exporting candidate evidence as CSV
  - Generating PDF investigation reports (stub)
  - Freezing a point-in-time report bundle

Scaffold pass: returns mock file paths / in-memory data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.schemas.models import CandidateResponse, Case


def export_geojson(case: Case, slicks: list[dict], contours: dict) -> dict[str, Any]:
    """
    Export case spatial data as a GeoJSON FeatureCollection.

    Scaffold: assembles slick polygons and contours into a FeatureCollection.
    Production: includes all spatial layers with proper CRS metadata.
    """
    features = []

    for slick in slicks:
        features.append({
            "type": "Feature",
            "properties": {"layer": "slick", "case_id": case.case_id},
            "geometry": slick,
        })

    if contours and "features" in contours:
        for feat in contours["features"]:
            feat_copy = dict(feat)
            feat_copy.setdefault("properties", {})["layer"] = "origin_contour"
            features.append(feat_copy)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def export_csv(candidates: CandidateResponse) -> str:
    """
    Export candidate evidence as CSV text.

    Scaffold: returns a formatted CSV string.
    """
    lines = ["vessel_key,score,space,time,forward_fit,behaviour,ais_quality,flags"]
    for c in candidates.candidates:
        flags_str = "|".join(c.flags)
        lines.append(
            f"{c.vessel_key},{c.score},"
            f"{c.components.get('space', 0)},{c.components.get('time', 0)},"
            f"{c.components.get('forward_fit', 0)},{c.components.get('behaviour', 0)},"
            f"{c.ais_quality},{flags_str}"
        )
    return "\n".join(lines)


def export_pdf_stub(case: Case) -> dict[str, str]:
    """
    Generate a PDF investigation report.

    Scaffold: returns a dict describing what would be generated.
    Production: Jinja2 → HTML → WeasyPrint/ReportLab PDF.
    """
    return {
        "format": "pdf",
        "status": "stub",
        "case_id": case.case_id,
        "message": "PDF generation is a stub in this scaffold pass.",
        "would_contain": [
            "Case summary",
            "Slick map",
            "Origin contours",
            "Candidate ranking table",
            "Evidence explanations",
            "Audit trail",
        ],
    }


def freeze_report_bundle(
    case: Case,
    candidates: CandidateResponse,
    slicks: list[dict],
    contours: dict,
) -> dict[str, Any]:
    """
    Freeze a complete report bundle (GeoJSON + CSV + PDF metadata).

    Returns a manifest describing all exported artefacts.
    """
    geojson = export_geojson(case, slicks, contours)
    csv_text = export_csv(candidates)
    pdf_meta = export_pdf_stub(case)

    return {
        "case_id": case.case_id,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "artefacts": {
            "geojson": {"type": "FeatureCollection", "feature_count": len(geojson["features"])},
            "csv": {"row_count": len(candidates.candidates)},
            "pdf": pdf_meta,
        },
    }
