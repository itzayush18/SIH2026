"""HTTP smoke tests hitting the running OILTRACE server on localhost:8000.

Skipped automatically if nothing answers on that port — no false failures when
someone runs `pytest tests/` without booting the server first.
"""
from __future__ import annotations

import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ.get("OILTRACE_BASE", "http://127.0.0.1:8000")


@pytest.fixture(scope="module")
def base():
    try:
        r = httpx.get(BASE + "/health", timeout=2.0)
        assert r.status_code == 200
    except Exception:
        pytest.skip(f"no OILTRACE server responding at {BASE}")
    return BASE


def get(base, path, **kw):
    return httpx.get(base + path, timeout=15.0, **kw)


def test_system_status(base):
    r = get(base, "/api/system/status").json()
    assert r["_meta"]["data_mode"] == "SIMULATION"
    assert any(s["id"] == "sentinel1" for s in r["sources"])


def test_scenarios(base):
    assert len(get(base, "/api/scenarios").json()["scenarios"]) >= 6


def test_incidents(base):
    r = get(base, "/api/incidents").json()
    assert r["incidents"], "warm the server first: python -m oiltrace.server --warm"


def iid(base):
    return get(base, "/api/incidents").json()["incidents"][0]["incident_id"]


def test_incident_children(base):
    x = iid(base)
    for ep in ("candidates", "alerts", "patrol", "evidence", "timeline"):
        assert get(base, f"/api/incidents/{x}/{ep}").status_code == 200, ep


def test_evidence_pdf(base):
    x = iid(base)
    r = get(base, f"/api/incidents/{x}/evidence.pdf")
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"


def test_vectors(base):
    r = get(base, "/api/environment/vectors?south=17&west=71&north=21&east=74&n=6").json()
    assert r["type"] == "FeatureCollection"
    assert len(r["features"]) >= 40


def test_coast_and_jurisdictions(base):
    assert get(base, "/api/coast.geojson").status_code == 200
    r = get(base, "/api/jurisdictions/at?lat=19.35&lon=71.80").json()
    assert r["kind"] in ("SPECIAL_AREA", "EEZ")


def test_vessel_lookup(base):
    x = iid(base)
    v = get(base, f"/api/incidents/{x}").json()["report"]["vessels"][0]
    r = get(base, f"/api/vessels/{v['mmsi']}").json()
    assert r["vessel"]["mmsi"] == v["mmsi"]


def test_analytics(base):
    r = get(base, "/api/analytics/overview").json()
    assert r["incidents"] >= 1
    assert 0.0 <= r["attribution_correct_rate"] <= 1.0
