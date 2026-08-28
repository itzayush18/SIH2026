"""
OilTrace — Core Pydantic v2 domain models.

All entities used across services, API, and exports live here.
This is the single source of truth for data shapes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# HARD PRODUCT RULE — Scoring output semantics
# ---------------------------------------------------------------------------
# The attribution score is an *evidence index* — a weighted composite of
# spatial, temporal, forward-fit, and behavioural indicators.
# It is **NOT** a probability, a liability determination, or an accusation.
# All UI, API, and export surfaces MUST use this label.
SCORE_TYPE: str = "evidence_index"

# Frozen scoring weights — do NOT change without product + legal sign-off.
SCORING_WEIGHTS: dict[str, float] = {
    "space": 0.35,
    "time": 0.25,
    "forward_fit": 0.25,
    "behaviour": 0.15,
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CaseStatus(str, Enum):
    """Lifecycle states for a Case."""
    created = "created"
    assets_registered = "assets_registered"
    detecting = "detecting"
    detection_review = "detection_review"
    drifting = "drifting"
    attribution = "attribution"
    review_required = "review_required"
    exported = "exported"
    closed = "closed"


class ReviewState(str, Enum):
    """Slick / detection review outcome."""
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    uncertain = "uncertain"


class JobState(str, Enum):
    """Background job lifecycle."""
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class AssetType(str, Enum):
    """Supported source-asset types."""
    sar_grd = "sar_grd"
    sar_slc = "sar_slc"
    optical = "optical"
    ais_csv = "ais_csv"
    ais_nmea = "ais_nmea"
    other = "other"


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

class Case(BaseModel):
    """An investigation case scoping one potential spill event."""
    case_id: str = Field(..., description="Unique case identifier")
    aoi: dict[str, Any] = Field(
        default_factory=dict,
        description="Area of Interest as GeoJSON geometry",
    )
    start_utc: datetime = Field(..., description="Observation window start")
    end_utc: datetime = Field(..., description="Observation window end")
    status: CaseStatus = Field(default=CaseStatus.created)
    created_by: str = Field(default="system")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SourceAsset(BaseModel):
    """An immutable source data asset registered to a case."""
    asset_id: str = Field(..., description="Unique asset identifier")
    case_id: str
    uri: str = Field(..., description="Path or URL to the asset")
    checksum: str = Field(default="", description="SHA-256 hex digest")
    asset_type: AssetType = Field(default=AssetType.other)
    crs: str = Field(default="EPSG:4326", description="Coordinate reference system")
    acquisition_time: Optional[datetime] = None
    licence: str = Field(default="unknown", description="Data licence")


class DetectionRun(BaseModel):
    """A single detection-model execution on a source asset."""
    run_id: str
    case_id: str
    asset_id: str
    status: JobState = Field(default=JobState.queued)
    model_version: str = Field(default="stub_v0")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    slick_count: int = Field(default=0)


class Slick(BaseModel):
    """A detected oil-slick polygon with review state."""
    slick_id: str
    run_id: str
    case_id: str
    polygon: dict[str, Any] = Field(
        default_factory=dict,
        description="GeoJSON Polygon geometry",
    )
    area_km2: float = Field(default=0.0)
    perimeter_km: float = Field(default=0.0)
    compactness: float = Field(default=0.0, description="Polsby-Popper score")
    review_state: ReviewState = Field(default=ReviewState.pending)


class DriftRun(BaseModel):
    """Configuration and output of a drift-hindcast ensemble run."""
    drift_id: str
    case_id: str
    slick_id: str
    forcing_ids: list[str] = Field(default_factory=list)
    ensemble_size: int = Field(default=100)
    seed: int = Field(default=42)
    horizon_hours: float = Field(default=48.0)
    contours: dict[str, Any] = Field(
        default_factory=dict,
        description="Origin-probability contour GeoJSON",
    )
    status: JobState = Field(default=JobState.queued)


class AISObservation(BaseModel):
    """A single AIS position report."""
    mmsi: str
    timestamp_utc: datetime
    longitude: float
    latitude: float
    sog: float = Field(default=0.0, description="Speed over ground (knots)")
    cog: float = Field(default=0.0, description="Course over ground (degrees)")
    nav_status: str = Field(default="under_way")
    source: str = Field(default="terrestrial")


class TrackSegment(BaseModel):
    """A continuous vessel track segment derived from AIS observations."""
    segment_id: str
    mmsi: str
    case_id: str
    observations: list[AISObservation] = Field(default_factory=list)
    gap_seconds_max: float = Field(default=0.0)
    interpolated: bool = Field(default=False)


class CandidateEvidence(BaseModel):
    """Attribution evidence for a single candidate vessel."""
    vessel_key: str = Field(..., description="e.g. 'mmsi:123456789'")
    score: float = Field(
        ...,
        description="Composite evidence index (0-100). NOT a probability.",
    )
    components: dict[str, float] = Field(
        ...,
        description="Component scores: space, time, forward_fit, behaviour",
    )
    ais_quality: float = Field(default=1.0)
    evidence_time_utc: datetime
    flags: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    """Append-only audit log entry. Never mutated after creation."""
    event_id: str
    case_id: str
    actor: str
    action: str
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    before_ref: Optional[str] = None
    after_ref: Optional[str] = None
    reason: str = Field(default="")


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class CandidateResponse(BaseModel):
    """Shape returned by GET /cases/{id}/candidates."""
    case_id: str
    status: str = Field(default="review_required")
    score_type: str = Field(
        default=SCORE_TYPE,
        description="Always 'evidence_index'. NEVER 'probability' or 'guilty'.",
    )
    candidates: list[CandidateEvidence] = Field(default_factory=list)
    abstention_reasons: list[str] = Field(default_factory=list)


class JobStatus(BaseModel):
    """Status of a background job."""
    job_id: str
    state: JobState
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Attribution scoring function
# ---------------------------------------------------------------------------

def compute_evidence_index(
    q_case: float,
    q_ais: float,
    s_space: float,
    s_time: float,
    s_fit: float,
    s_beh: float,
) -> float:
    """
    Compute the attribution evidence index for a candidate vessel.

    Formula:
        R(v) = 100 * q_case * q_ais(v) * (
            0.35 * s_space + 0.25 * s_time + 0.25 * s_fit + 0.15 * s_beh
        )

    The weights are frozen constants defined in SCORING_WEIGHTS.

    Returns a score in [0, 100].  This is an EVIDENCE INDEX, not a
    probability and not a guilt determination.

    Args:
        q_case:  Overall case quality factor (0-1).
        q_ais:   AIS data quality for this vessel (0-1).
        s_space: Spatial proximity score (0-1).
        s_time:  Temporal proximity score (0-1).
        s_fit:   Forward-drift fit score (0-1).
        s_beh:   Behavioural anomaly score (0-1).

    Returns:
        Evidence index (0-100).
    """
    w = SCORING_WEIGHTS
    weighted_sum = (
        w["space"] * s_space
        + w["time"] * s_time
        + w["forward_fit"] * s_fit
        + w["behaviour"] * s_beh
    )
    raw = 100.0 * q_case * q_ais * weighted_sum
    return round(max(0.0, min(100.0, raw)), 2)
