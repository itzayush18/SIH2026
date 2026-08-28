"""
OilTrace — Integration tests for the FastAPI endpoints.

Tests the full request/response cycle using the FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.store import store


@pytest.fixture(autouse=True)
def reset_store():
    """Reset the in-memory store before each test."""
    store.cases.clear()
    store.assets.clear()
    store.detection_runs.clear()
    store.slicks.clear()
    store.drift_runs.clear()
    store.jobs.clear()
    store.audit_events.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthCheck:
    def test_root(self, client):
        res = client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["service"] == "oiltrace-api"
        assert data["score_type"] == "evidence_index"


class TestCreateCase:
    def test_create_case(self, client):
        res = client.post("/cases", json={
            "aoi": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            "start_utc": "2026-08-19T00:00:00Z",
            "end_utc": "2026-08-21T00:00:00Z",
            "created_by": "test",
        })
        assert res.status_code == 200
        data = res.json()
        assert "case_id" in data
        assert data["status"] == "created"


class TestRegisterAsset:
    def test_register_asset(self, client):
        # Create case first
        case_res = client.post("/cases", json={
            "start_utc": "2026-08-19T00:00:00Z",
            "end_utc": "2026-08-21T00:00:00Z",
        })
        case_id = case_res.json()["case_id"]

        res = client.post(f"/cases/{case_id}/assets", json={
            "uri": "s3://test/scene.tiff",
            "asset_type": "sar_grd",
        })
        assert res.status_code == 200
        data = res.json()
        assert "asset_id" in data
        assert len(data["checksum"]) == 64  # SHA-256 hex


class TestDetection:
    def test_detect(self, client):
        # Setup
        case_res = client.post("/cases", json={
            "start_utc": "2026-08-19T00:00:00Z",
            "end_utc": "2026-08-21T00:00:00Z",
        })
        case_id = case_res.json()["case_id"]
        client.post(f"/cases/{case_id}/assets", json={"uri": "test.tiff"})

        res = client.post(f"/cases/{case_id}/detect")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "queued"
        assert "job_id" in data


class TestCandidates:
    def test_get_candidates(self, client):
        # Full pipeline
        case_res = client.post("/cases", json={
            "start_utc": "2026-08-19T00:00:00Z",
            "end_utc": "2026-08-21T00:00:00Z",
        })
        case_id = case_res.json()["case_id"]

        res = client.get(f"/cases/{case_id}/candidates")
        assert res.status_code == 200
        data = res.json()
        assert data["case_id"] == case_id
        assert data["score_type"] == "evidence_index"
        assert isinstance(data["candidates"], list)
        assert len(data["candidates"]) > 0

        # Verify candidate shape
        cand = data["candidates"][0]
        assert "vessel_key" in cand
        assert "score" in cand
        assert "components" in cand
        assert set(cand["components"].keys()) == {"space", "time", "forward_fit", "behaviour"}

    def test_candidate_not_found(self, client):
        res = client.get("/cases/nonexistent/candidates")
        assert res.status_code == 404


class TestExport:
    def test_export(self, client):
        case_res = client.post("/cases", json={
            "start_utc": "2026-08-19T00:00:00Z",
            "end_utc": "2026-08-21T00:00:00Z",
        })
        case_id = case_res.json()["case_id"]

        res = client.post(f"/cases/{case_id}/export")
        assert res.status_code == 200
        data = res.json()
        assert data["case_id"] == case_id
        assert "artefacts" in data
        assert "exported_at" in data


class TestJobStatus:
    def test_job_not_found(self, client):
        res = client.get("/jobs/nonexistent")
        assert res.status_code == 404
