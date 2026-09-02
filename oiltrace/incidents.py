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


def _real_incident_id(key):
    return f"OIL-{time.strftime('%Y')}-R{abs(hash(key)) % 10000:04d}"


def run_real(scene_path, currents_nc, winds_nc, epoch_iso, outdir_root,
             ais_csv=None, synth_vessels=True, p_threshold=0.5,
             hours_back=24.0, hours_fwd=18.0, n_particles=4000,
             unet_model=None, on_stage=None):
    """Same bundle as `run()`, but on REAL inputs: a Sentinel-1 GeoTIFF, CMEMS +
    ERA5 NetCDF, and either a real AIS CSV or synthetic candidate traffic built
    around the inferred source. Produces the identical report+PNG structure the
    frontend map already renders, tagged data_mode=REAL."""
    from sagar.data.loaders import load_geotiff, NetCDFOcean
    from sagar.core import ais as _ais, attribute as _attribute

    emit = on_stage or (lambda *_: None)
    emit("ingest", {"message": "Loading real Sentinel-1 scene + metocean forcing"})
    scene = load_geotiff(scene_path, epoch=0.0)
    origin = scene.spec.origin
    ocean = NetCDFOcean(origin, currents_nc, winds_nc, epoch_np64=epoch_iso)

    vessels = {}
    if ais_csv:
        vessels = _ais.load_csv(ais_csv, epoch_iso=epoch_iso)

    r = pipeline.run_on(scene, ocean, vessels, epoch_iso=epoch_iso,
                        hours_back=hours_back, hours_fwd=hours_fwd,
                        n_particles=n_particles, p_threshold=p_threshold,
                        unet_model=unet_model, on_stage=on_stage)

    # No real AIS (e.g. Indian waters, no aisstream coverage): build candidate
    # traffic around the INFERRED source so the map has vessels to score. This is
    # synthetic traffic, labelled as such — not a real attribution claim.
    if not vessels and synth_vessels:
        hyp = r["source"]
        vessels = _ais.synthesize(origin, (hyp.x0, hyp.y0), hyp.t_start, seed=7)
        r["vessels"] = vessels
        r["suspects"] = _attribute.rank(vessels, r["pdf"], r["detections"][0],
                                        origin, source_hyp=hyp)
        r["validation"]["top_suspect"] = r["suspects"][0].mmsi if r["suspects"] else None
        r["validation"]["synthetic_ais"] = True

    incident_id = _real_incident_id(f"{scene_path}|{epoch_iso}")
    scene_outdir = os.path.join(outdir_root, incident_id)
    rep = _export.build(r, scene_outdir, epoch_iso=epoch_iso)

    top = r["detections"][0]
    lat, lon = top.centroid_lonlat[1], top.centroid_lonlat[0]
    jur = classify(lat, lon)
    coast_km, coast_name = nearest_coast_km(lat, lon)
    a = _alerts.derive(r, incident_id, jur, coast_km, coast_name)
    p = _patrol.recommend(rep, jur, coast_km, coast_name)
    pack = _evidence.build(rep, incident_id, jur, coast_km, coast_name, a, p, scene_outdir)

    import os as _os
    label = _os.path.basename(scene_path)
    rep["oiltrace"] = dict(
        incident_id=incident_id,
        scenario=dict(slug="real", name="Real Sentinel-1",
                      subtitle=f"{label} · {epoch_iso[:10]}",
                      difficulty="REAL",
                      story="Live pipeline run on real Sentinel-1 (MPC RTC) + "
                            "CMEMS currents + ERA5 wind.",
                      tags=["real", "sentinel-1"]),
        jurisdiction=dict(name=jur.name, kind=jur.kind, sovereign=jur.sovereign,
                          marpol_regime=jur.marpol_regime, source=jur.source),
        nearest_coast=dict(km=coast_km, name=coast_name),
        alerts=a, patrol=p, evidence_pack=pack,
        provenance=_evidence._provenance(),
        data_mode="REAL",
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
