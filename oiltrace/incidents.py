"""Incident bundling- one pipeline run × all the surrounding OILTRACE state.

Given a `Scenario` slug, this runs the physics pipeline, adds jurisdiction,
alerts, patrol tasks and an evidence pack, and writes everything into the
`out/<incident_id>/` directory the frontend loads from.
"""
from __future__ import annotations

import json
import os
import time

from sagar.core import pipeline
from sagar.api import export as _export

from . import alerts as _alerts, evidence as _evidence, patrol as _patrol, providers
from .jurisdictions import classify, nearest_coast_km
from .scenarios import BY_SLUG


def _incident_id(slug):
    # Deterministic (PYTHONHASHSEED-independent)- hash() is salted per-process
    import hashlib as _hl
    h = int.from_bytes(_hl.md5(slug.encode()).digest()[:2], "big")
    return f"OIL-{time.strftime('%Y')}-{h % 10000:04d}"


def run(scenario_slug, outdir_root, on_stage=None):
    s = BY_SLUG[scenario_slug]
    # --- Real-data branch (§4.1) -----------------------------------------
    if s.slug == "zenodo-real":
        # Prefer real Zenodo TIFF if present; otherwise SYNTHETIC_OVERLAY on MV Rak geography.
        # This keeps the 7th card clickable in CI / fresh clones without hiding provenance.
        # AIS: try real AccessAIS CSV if present at data/ais/, else synthetic overlay.
        ais_csv = None
        for cand in ("data/ais/MarineCadastre.csv", "data/ais/accessais.csv", "data/ais/real.csv"):
            if os.path.exists(cand):
                ais_csv = cand
                break
        # Allow explicit override via env
        env_tiff = os.environ.get("ZENODO_TIFF", "").strip()
        if env_tiff and os.path.exists(env_tiff):
            r = pipeline.run_real(scene_path=env_tiff, origin=s.origin, ais_csv=ais_csv,
                                  seed=s.seed, on_stage=on_stage)
        else:
            # Coerce pipeline.run_real to scan data/zenodo/
            r = pipeline.run_real(scene_path=None, origin=s.origin, ais_csv=ais_csv,
                                  seed=s.seed, on_stage=on_stage)
        data_mode = r.get("data_mode", "SYNTHETIC_OVERLAY")
        # Normalise legacy values
        import oiltrace.providers as _prov
        data_mode = _prov.canonical_mode(data_mode)
    else:
        r = pipeline.run(seed=s.seed, origin=s.origin, on_stage=on_stage)
        data_mode = "SIMULATION"

    incident_id = _incident_id(scenario_slug)
    scene_outdir = os.path.join(outdir_root, incident_id)
    rep = _export.build(r, scene_outdir)

    # Dark-vessel pass if scene available (§4.2)- honest additive, not replacing AIS
    try:
        from sagar.core.dark_vessel import detect_dark_vessels, enrich_with_dark
        from sagar.core import attribute as _attr
        # Only run when we have a SAR scene (always) and a pdf/source to score against
        dv = detect_dark_vessels(r["scene"], r.get("vessels", {}), r["scene"].spec.origin)
        if dv:
            # Attribute dark candidates on same scale (source_match + spatiotemporal still valid)
            dark_suspects = enrich_with_dark(dv, r, s.origin)
            # Merge and re-rank: keep same scoring function, just add axis-truncated terms
            # We reuse attribute logic by injecting dark vessels as minimal Vessel stubs
            # The existing suspects already include AIS-tracked vessels; dark ones append.
            if dark_suspects:
                # Append dark suspects to report (distinct marker via is_dark flag)
                # Re-sort overall ranking by evidence index (not probability)
                merged = list(r["suspects"]) + dark_suspects
                merged.sort(key=lambda x: -x.score)
                r["suspects"] = merged[:12]
                # Also update rep for export after merge
                rep["suspects"] = [s_.to_dict() for s_ in merged[:12]]
                # Honest dark vessel features: use detection id as MMSI alias
                rep["dark_vessels"] = [dict(mmsi=d.id, id=d.id, lat=d.lat, lon=d.lon, peak_db=d.peak_db, is_dark=True) for d in dv]
                # Also surface count for analytics
                rep["dark_vessel_count"] = len(dv)
    except Exception as e:
        # Dark detection is additive- never fail the incident on its behalf
        rep.setdefault("dark_vessels", [])
        if on_stage:
            try:
                on_stage("dark_vessel", {"note": f"dark detection skipped: {e}"})
            except Exception:
                pass

    top = r["detections"][0]
    lat, lon = top.centroid_lonlat[1], top.centroid_lonlat[0]
    jur = classify(lat, lon)
    coast_km, coast_name = nearest_coast_km(lat, lon)

    # Include dark vessel alert derivation inside alerts.derive (it checks r for dark_vessels)
    # Ensure rep carries dark_vessels for derive
    if "dark_vessels" in rep:
        r["dark_vessels"] = rep["dark_vessels"]
    a = _alerts.derive(r, incident_id, jur, coast_km, coast_name)
    p = _patrol.recommend(rep, jur, coast_km, coast_name)
    # Stamp patrol with ETA for nearest ICG station (§4.6)- done inside patrol module now
    pack = _evidence.build(rep, incident_id, jur, coast_km, coast_name,
                           a, p, scene_outdir, data_mode=data_mode)

    # Provenance: embed per-incident mode chain so evidence is auditable
    prov = _evidence._provenance(data_mode=data_mode)

    rep["oiltrace"] = dict(
        incident_id=incident_id,
        scenario=dict(slug=s.slug, name=s.name, subtitle=s.subtitle,
                      difficulty=s.difficulty, story=s.story, tags=list(s.tags)),
        jurisdiction=dict(name=jur.name, kind=jur.kind, sovereign=jur.sovereign,
                          marpol_regime=jur.marpol_regime, source=jur.source),
        nearest_coast=dict(km=coast_km, name=coast_name),
        alerts=a, patrol=p, evidence_pack=pack,
        provenance=prov,
        data_mode=data_mode,
        providers=[s.dict() for s in providers.registry_for_mode(data_mode)],
    )
    # Clean NaN/Inf for browser JSON compliance (mirrors sagar/api/export._clean)
    def _clean(o):
        import math as _m, numpy as _np
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_clean(v) for v in o]
        if isinstance(o, (float, _np.floating)):
            f = float(o)
            return None if (_m.isnan(f) or _m.isinf(f)) else f
        if isinstance(o, (_np.integer,)):
            return int(o)
        if isinstance(o, (_np.bool_,)):
            return bool(o)
        return o
    rep = _clean(rep)
    with open(os.path.join(scene_outdir, "report.json"), "w") as f:
        json.dump(rep, f, indent=2, default=float, allow_nan=False)
    return rep


def summary(rep):
    """Compact incident record for the left-panel incident list."""
    o = rep["oiltrace"]
    top = rep["detections"][0]
    a = o["alerts"]
    sev = "CRITICAL" if any(x["severity"] == "CRITICAL" for x in a) else (
        "HIGH" if any(x["severity"] == "HIGH" for x in a) else "MEDIUM")
    lead = rep["suspects"][0] if rep["suspects"] else None
    return dict(
        incident_id=o["incident_id"], scenario=o["scenario"],
        severity=sev,
        area_km2=top["area_km2"], p_oil=top["p_oil"],
        centroid=dict(lat=top["centroid_lonlat"][1], lon=top["centroid_lonlat"][0]),
        jurisdiction=o["jurisdiction"]["name"],
        nearest_coast=o["nearest_coast"],
        prime_suspect=(dict(mmsi=lead["mmsi"], name=lead["name"], score=lead["score"])
                       if lead else None),
        n_alerts=len(a), n_patrol=len(o["patrol"]),
        data_mode=o["data_mode"],
    )
