"""Evidence package — spec §29.

Turns one pipeline run into a self-contained, traceable dossier. Every claim
has a provenance line (spec §30) so an analyst — or a court, later — can
follow a number back to the model version, dataset and timestamp that produced
it. Nothing here is a scientific determination; the file even says so.
"""
from __future__ import annotations

import csv
import io
import json
import os
import time


MODEL_VERSIONS = dict(
    sar_processing="0.4.0",
    detector="oil_classifier v1.0 (logistic, 8 features, N_train=195)",
    drift="RK2 Lagrangian ensemble v0.3",
    inversion="source-term inversion v0.2 (coarse+refine random search, IoU objective)",
    attribution="six-axis logistic v0.4",
    reference="SIH26143 · NTRO · SAGAR-DRISHTI / OILTRACE",
)


def _provenance():
    return dict(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        model_versions=MODEL_VERSIONS,
        chain=[
            "Sentinel-1 GRD (SIMULATED for this run)",
            "SAR processing v0.4.0 — Lee filter, incidence-trend removal",
            "Slick detection v1.0 — 8-feature logistic",
            "Metocean forcing (SIMULATED — synthetic ocean + wind)",
            "Drift model v0.3 — RK2 Lagrangian ensemble",
            "Source-term inversion v0.2",
            "AIS reconstruction (SIMULATED — synthesised traffic + decoys)",
            "Six-axis attribution v0.4",
        ],
    )


def build(report, incident_id, jurisdiction, coast_km, coast_name,
          alerts, patrol, outdir):
    """Write JSON / GeoJSON / CSV artefacts for one incident."""
    os.makedirs(outdir, exist_ok=True)
    d = report["detections"][0]
    src = report["source"]

    core = dict(
        incident_id=incident_id,
        classification="INVESTIGATIVE LEAD — NOT LEGAL EVIDENCE",
        detection=dict(
            acquisition_utc=report["generated_for"],
            centroid=dict(lat=d["centroid_lonlat"][1], lon=d["centroid_lonlat"][0]),
            area_km2=d["area_km2"], length_km=d["length_km"], width_km=d["width_km"],
            orientation_deg=d["orientation_deg"], p_oil=d["p_oil"],
        ),
        characterization=report["characterization"],
        source_reconstruction=dict(
            release_start_h_before_acq=src["t_start"] / 3600.0,
            duration_h=src["duration"] / 3600.0,
            course_deg=src["course_deg"], speed_kn=src["speed_kn"],
            start_lat=src["start_lat"], start_lon=src["start_lon"],
            inversion_fit_iou=src["iou"],
            search_dispersion=src["search_dispersion"],
        ),
        jurisdiction=dict(
            name=jurisdiction.name, kind=jurisdiction.kind,
            sovereign=jurisdiction.sovereign,
            marpol_regime=jurisdiction.marpol_regime,
            source=jurisdiction.source,
            nearest_coast_km=coast_km, nearest_coast=coast_name,
        ),
        attribution=[dict(rank=i+1, mmsi=s["mmsi"], name=s["name"],
                          type=s["type_name"], score=s["score"],
                          terms=s["terms"], evidence=s["evidence"])
                     for i, s in enumerate(report["suspects"][:6])],
        alerts=alerts, patrol=patrol,
        provenance=_provenance(),
        validation_note=(
            "REAL data: no ground truth exists, so no segmentation/origin error "
            "is reported — only the source-inversion fit IoU and classifier score."
            if report["validation"].get("data_mode") == "REAL" else
            "Segmentation and origin errors are measured against a KNOWN "
            "ground truth built by the same drift physics the pipeline "
            "inverts. Real-world accuracy will differ."),
        validation=report["validation"],
        legal_note=(
            "This document is decision-support intelligence. It does not "
            "establish an offence under MARPOL or any national law. "
            "Enforcement action requires corroboration (oil fingerprinting, "
            "port state inspection, chain of custody)."),
    )

    with open(os.path.join(outdir, f"{incident_id}.evidence.json"), "w") as f:
        json.dump(core, f, indent=2, default=float, allow_nan=False)

    with open(os.path.join(outdir, f"{incident_id}.slick.geojson"), "w") as f:
        json.dump({"type": "FeatureCollection", "features": [
            {"type": "Feature",
             "properties": {"incident_id": incident_id, "p_oil": d["p_oil"],
                            "area_km2": d["area_km2"],
                            "acquisition_utc": report["generated_for"]},
             "geometry": {"type": "Polygon", "coordinates": [
                 d["contour_lonlat"] + [d["contour_lonlat"][0]]
                 if d["contour_lonlat"] else []]}},
            {"type": "Feature",
             "properties": {"incident_id": incident_id,
                            "kind": "inverted_source_track"},
             "geometry": {"type": "LineString",
                          "coordinates": [[p["lon"], p["lat"]] for p in src["track"]]}}
        ]}, f, indent=2)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "mmsi", "name", "type", "length_m", "score",
                *[k for k, _ in [("source_match", 0), ("spatiotemporal", 0),
                                 ("behaviour", 0), ("dark", 0),
                                 ("alignment", 0), ("prior", 0)]]])
    for i, s in enumerate(report["suspects"][:12]):
        w.writerow([i+1, s["mmsi"], s["name"], s["type_name"], f"{s['length']:.0f}",
                    f"{s['score']:.3f}",
                    *[f"{s['terms'].get(k, 0):.3f}" for k in
                      ("source_match", "spatiotemporal", "behaviour",
                       "dark", "alignment", "prior")]])
    with open(os.path.join(outdir, f"{incident_id}.suspects.csv"), "w") as f:
        f.write(buf.getvalue())

    return dict(incident_id=incident_id, outdir=outdir,
                json=f"{incident_id}.evidence.json",
                geojson=f"{incident_id}.slick.geojson",
                csv=f"{incident_id}.suspects.csv")
