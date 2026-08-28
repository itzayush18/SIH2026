"""
OilTrace — API route definitions.

All 8 scaffold endpoints, returning realistic mock payloads.
Uses FastAPI BackgroundTasks for async job processing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from packages.schemas.models import (
    Case,
    CaseStatus,
    CandidateResponse,
    DetectionRun,
    DriftRun,
    JobState,
    ReviewState,
    SourceAsset,
    Slick,
    AuditEvent,
    SCORE_TYPE,
)
from apps.api.store import store
from services.ingestion.service import register_asset, compute_checksum
from services.vision.service import run_detection, get_stub_slick
from services.drift.service import configure_ensemble, run_ensemble
from services.attribution.service import gate_candidates, score_candidates
from services.reporting.service import freeze_report_bundle

router = APIRouter()


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateCaseRequest(BaseModel):
    aoi: dict[str, Any] = Field(default_factory=dict)
    start_utc: datetime = Field(default_factory=datetime.utcnow)
    end_utc: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "analyst"


class RegisterAssetRequest(BaseModel):
    uri: str
    asset_type: str = "other"
    crs: str = "EPSG:4326"
    acquisition_time: Optional[datetime] = None
    licence: str = "unknown"


class ReviewRequest(BaseModel):
    slick_ids: list[str] = Field(default_factory=list)
    verdict: str = "accepted"  # accepted | rejected | uncertain
    reason: str = ""


# ---------------------------------------------------------------------------
# POST /cases — Create a new case
# ---------------------------------------------------------------------------

@router.post("/cases")
async def create_case(body: CreateCaseRequest) -> dict[str, Any]:
    """Create a new investigation case."""
    case_id = f"case_{uuid.uuid4().hex[:10]}"
    case = Case(
        case_id=case_id,
        aoi=body.aoi,
        start_utc=body.start_utc,
        end_utc=body.end_utc,
        status=CaseStatus.created,
        created_by=body.created_by,
    )
    store.create_case(case)
    store.append_audit(AuditEvent(
        event_id=f"aud_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        actor=body.created_by,
        action="case_created",
    ))
    return {"case_id": case_id, "status": case.status.value}


# ---------------------------------------------------------------------------
# POST /cases/{id}/assets — Register a source asset
# ---------------------------------------------------------------------------

@router.post("/cases/{case_id}/assets")
async def add_asset(case_id: str, body: RegisterAssetRequest) -> dict[str, Any]:
    """Register a source asset and compute its checksum."""
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    asset_id = f"ast_{uuid.uuid4().hex[:10]}"
    asset = register_asset(
        case_id=case_id,
        asset_id=asset_id,
        uri=body.uri,
        crs=body.crs,
        licence=body.licence,
    )
    store.add_asset(asset)
    store.update_case_status(case_id, CaseStatus.assets_registered)

    return {
        "asset_id": asset_id,
        "checksum": asset.checksum,
        "case_id": case_id,
    }


# ---------------------------------------------------------------------------
# POST /cases/{id}/detect — Queue detection run
# ---------------------------------------------------------------------------

def _run_detection_job(case_id: str, asset_id: str, job_id: str) -> None:
    """Background task: run detection and store results."""
    det_run = run_detection(case_id, asset_id)
    store.add_detection_run(det_run)

    slick = get_stub_slick(det_run.run_id, case_id)
    store.add_slick(slick)

    store.update_case_status(case_id, CaseStatus.detection_review)
    store.complete_job(job_id, message=f"Detection complete: {det_run.slick_count} slick(s)")


@router.post("/cases/{case_id}/detect")
async def detect(case_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Queue an oil-spill detection run (stub)."""
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    assets = store.get_assets_for_case(case_id)
    asset_id = assets[0].asset_id if assets else "stub_asset"

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    store.create_job(job_id, message="Detection queued")

    background_tasks.add_task(_run_detection_job, case_id, asset_id, job_id)

    return {"job_id": job_id, "case_id": case_id, "status": "queued"}


# ---------------------------------------------------------------------------
# POST /detections/{run}/review — Accept/reject/uncertain
# ---------------------------------------------------------------------------

@router.post("/detections/{run_id}/review")
async def review_detection(run_id: str, body: ReviewRequest) -> dict[str, Any]:
    """Review slick detections from a run."""
    det_run = store.get_detection_run(run_id)

    # If run_id not found, review slicks by ID directly
    slicks = store.get_slicks_for_run(run_id) if det_run else []

    # Apply verdict to matching slicks (or all if no IDs specified)
    verdict_map = {
        "accepted": ReviewState.accepted,
        "rejected": ReviewState.rejected,
        "uncertain": ReviewState.uncertain,
    }
    review_state = verdict_map.get(body.verdict, ReviewState.pending)

    reviewed_ids = []
    target_ids = set(body.slick_ids) if body.slick_ids else None

    for slick in slicks:
        if target_ids is None or slick.slick_id in target_ids:
            slick.review_state = review_state
            reviewed_ids.append(slick.slick_id)

    return {
        "run_id": run_id,
        "verdict": body.verdict,
        "reviewed_slick_ids": reviewed_ids,
        "reason": body.reason,
    }


# ---------------------------------------------------------------------------
# POST /cases/{id}/drift — Queue drift ensemble
# ---------------------------------------------------------------------------

def _run_drift_job(case_id: str, slick_id: str, job_id: str) -> None:
    """Background task: run drift ensemble and store results."""
    drift = configure_ensemble(case_id, slick_id)
    drift = run_ensemble(drift)
    store.add_drift_run(drift)
    store.update_case_status(case_id, CaseStatus.attribution)
    store.complete_job(job_id, message="Drift ensemble complete")


@router.post("/cases/{case_id}/drift")
async def drift(case_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Queue a drift-hindcast ensemble run (stub)."""
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    slicks = store.get_slicks_for_case(case_id)
    slick_id = slicks[0].slick_id if slicks else "stub_slick"

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    store.create_job(job_id, message="Drift ensemble queued")

    background_tasks.add_task(_run_drift_job, case_id, slick_id, job_id)

    return {"job_id": job_id, "case_id": case_id, "status": "queued"}


# ---------------------------------------------------------------------------
# GET /cases/{id}/candidates — Ranked candidates
# ---------------------------------------------------------------------------

@router.get("/cases/{case_id}/candidates")
async def get_candidates(case_id: str) -> dict[str, Any]:
    """
    Return ranked candidate vessels with evidence index scores.

    The score_type is ALWAYS "evidence_index" — never "probability" or "guilty".
    """
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Get contours and tracks (stub: use demo data)
    drift_runs = store.get_drift_runs_for_case(case_id)
    contours = drift_runs[0].contours if drift_runs else {}

    candidates = gate_candidates(contours, [])
    response = score_candidates(case_id, candidates)

    return response.model_dump(mode="json")


# ---------------------------------------------------------------------------
# POST /cases/{id}/export — Freeze report bundle
# ---------------------------------------------------------------------------

@router.post("/cases/{case_id}/export")
async def export_case(case_id: str) -> dict[str, Any]:
    """Freeze and export a report bundle (GeoJSON + CSV + PDF stub)."""
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    slicks = store.get_slicks_for_case(case_id)
    slick_polygons = [s.polygon for s in slicks]

    drift_runs = store.get_drift_runs_for_case(case_id)
    contours = drift_runs[0].contours if drift_runs else {}

    candidates_raw = gate_candidates(contours, [])
    candidates = score_candidates(case_id, candidates_raw)

    bundle = freeze_report_bundle(case, candidates, slick_polygons, contours)

    store.update_case_status(case_id, CaseStatus.exported)

    return bundle


# ---------------------------------------------------------------------------
# GET /jobs/{id} — Job status
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Check the status of a background job."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job.model_dump(mode="json")
