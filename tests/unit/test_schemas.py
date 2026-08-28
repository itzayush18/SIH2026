"""
OilTrace — Unit tests for Pydantic schemas.

Validates that all core models instantiate correctly with demo data.
"""

import pytest
from datetime import datetime

from packages.schemas.models import (
    Case,
    CaseStatus,
    SourceAsset,
    AssetType,
    DetectionRun,
    Slick,
    DriftRun,
    AISObservation,
    TrackSegment,
    CandidateEvidence,
    AuditEvent,
    CandidateResponse,
    JobStatus,
    JobState,
    ReviewState,
    SCORE_TYPE,
    SCORING_WEIGHTS,
)


class TestCase:
    def test_create_minimal(self):
        case = Case(
            case_id="test_01",
            start_utc=datetime(2026, 8, 19),
            end_utc=datetime(2026, 8, 21),
        )
        assert case.case_id == "test_01"
        assert case.status == CaseStatus.created
        assert case.created_by == "system"

    def test_create_with_aoi(self):
        aoi = {
            "type": "Polygon",
            "coordinates": [[[72.8, 18.9], [72.9, 18.9], [72.9, 19.0], [72.8, 19.0], [72.8, 18.9]]],
        }
        case = Case(
            case_id="test_02",
            aoi=aoi,
            start_utc=datetime(2026, 8, 19),
            end_utc=datetime(2026, 8, 21),
        )
        assert case.aoi["type"] == "Polygon"


class TestSourceAsset:
    def test_immutable_fields(self):
        asset = SourceAsset(
            asset_id="ast_01",
            case_id="test_01",
            uri="s3://bucket/scene.tiff",
            checksum="abc123",
            asset_type=AssetType.sar_grd,
        )
        assert asset.checksum == "abc123"
        assert asset.asset_type == AssetType.sar_grd


class TestSlick:
    def test_default_review_state(self):
        slick = Slick(
            slick_id="slk_01",
            run_id="det_01",
            case_id="test_01",
        )
        assert slick.review_state == ReviewState.pending
        assert slick.area_km2 == 0.0


class TestDriftRun:
    def test_defaults(self):
        drift = DriftRun(
            drift_id="dft_01",
            case_id="test_01",
            slick_id="slk_01",
        )
        assert drift.ensemble_size == 100
        assert drift.seed == 42
        assert drift.horizon_hours == 48.0


class TestAISObservation:
    def test_create(self):
        obs = AISObservation(
            mmsi="538007689",
            timestamp_utc=datetime(2026, 8, 20, 2, 0),
            longitude=72.83,
            latitude=18.93,
        )
        assert obs.sog == 0.0
        assert obs.source == "terrestrial"


class TestCandidateEvidence:
    def test_score_shape(self):
        cand = CandidateEvidence(
            vessel_key="mmsi:538007689",
            score=78.4,
            components={"space": 0.91, "time": 0.82, "forward_fit": 0.73, "behaviour": 0.31},
            ais_quality=0.94,
            evidence_time_utc=datetime(2026, 8, 20, 4, 15),
            flags=["short_gap_interpolated"],
        )
        assert cand.score == 78.4
        assert len(cand.components) == 4
        assert cand.flags == ["short_gap_interpolated"]


class TestCandidateResponse:
    def test_score_type_is_evidence_index(self):
        """HARD PRODUCT RULE: score_type must always be 'evidence_index'."""
        resp = CandidateResponse(case_id="test_01")
        assert resp.score_type == "evidence_index"
        assert resp.score_type == SCORE_TYPE

    def test_with_candidates(self):
        resp = CandidateResponse(
            case_id="test_01",
            candidates=[
                CandidateEvidence(
                    vessel_key="mmsi:123",
                    score=50.0,
                    components={"space": 0.5, "time": 0.5, "forward_fit": 0.5, "behaviour": 0.5},
                    evidence_time_utc=datetime(2026, 8, 20),
                ),
            ],
        )
        assert len(resp.candidates) == 1


class TestAuditEvent:
    def test_append_only_semantics(self):
        event = AuditEvent(
            event_id="aud_01",
            case_id="test_01",
            actor="analyst",
            action="slick_accepted",
            reason="Clear dark patch with sharp boundary",
        )
        assert event.action == "slick_accepted"
        assert event.before_ref is None


class TestConstants:
    def test_score_type_value(self):
        """SCORE_TYPE must never be 'probability' or 'guilty'."""
        assert SCORE_TYPE == "evidence_index"
        assert "probab" not in SCORE_TYPE.lower()
        assert "guilt" not in SCORE_TYPE.lower()

    def test_weights_sum(self):
        """Weights should sum to 1.0."""
        assert abs(sum(SCORING_WEIGHTS.values()) - 1.0) < 1e-9

    def test_weight_keys(self):
        assert set(SCORING_WEIGHTS.keys()) == {"space", "time", "forward_fit", "behaviour"}
