"""Incident bundling — one pipeline run × all the surrounding OILTRACE state.

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
    return f"OIL-{time.strftime('%Y')}-{abs(hash(slug)) % 10000:04d}"


def run(scenario_slug, outdir_root, on_stage=None):
    s = BY_SLUG[scenario_slug]
    r = pipeline.run(seed=s.seed, origin=s.origin, on_stage=on_stage)
    incident_id = _incident_id(scenario_slug)
    scene_outdir = os.path.join(outdir_root, incident_id)
    rep = _export.build(r, scene_outdir)

    top = r["detections"][0]
    lat, lon = top.centroid_lonlat[1], top.centroid_lonlat[0]
    jur = classify(lat, lon)
    coast_km, coast_name = nearest_coast_km(lat, lon)

    a = _alerts.derive(r, incident_id, jur, coast_km, coast_name)
    p = _patrol.recommend(rep, jur, coast_km, coast_name)
    pack = _evidence.build(rep, incident_id, jur, coast_km, coast_name,
                           a, p, scene_outdir)

    rep["oiltrace"] = dict(
        incident_id=incident_id,
        scenario=dict(slug=s.slug, name=s.name, subtitle=s.subtitle,
                      difficulty=s.difficulty, story=s.story, tags=list(s.tags)),
        jurisdiction=dict(name=jur.name, kind=jur.kind, sovereign=jur.sovereign,
                          marpol_regime=jur.marpol_regime, source=jur.source),
        nearest_coast=dict(km=coast_km, name=coast_name),
        alerts=a, patrol=p, evidence_pack=pack,
        provenance=_evidence._provenance(),
        data_mode="SIMULATION",
    )
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
