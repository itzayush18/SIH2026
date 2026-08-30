"""Evidence package- spec §29.

Turns one pipeline run into a self-contained, traceable dossier. Every claim
has a provenance line (spec §30) so an analyst- or a court, later- can
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


def _provenance(data_mode="SIMULATION"):
    # Honest chain per data_mode- nunca obscure synthetic vs real (§56)
    if data_mode == "REAL_IMAGERY_REAL_AIS":
        chain = [
            "Sentinel-1 GRD (REAL- Zenodo Sentinel-1 SAR Oil Spill Dataset, Trujillo-Acatitla et al. Parts I–III)",
            "SAR processing v0.4.0- Lee filter, incidence-trend removal (REAL imagery)",
            "Slick detection v1.0- 8-feature logistic (REAL scene, model trained on simulated+real candidate regions)",
            "Metocean forcing (SIMULATED- SyntheticOcean analytic; CMEMS/ERA5 via NetCDFOcean when credentials present- see providers status)",
            "Drift model v0.3- RK2 Lagrangian ensemble",
            "Source-term inversion v0.2 (IoU on REAL slick)",
            "AIS traffic (REAL- MarineCadastre AccessAIS bulk CSV via sagar.core.ais.load_csv)",
            "Six-axis attribution v0.4- evidence index, not probability",
        ]
    elif data_mode == "REAL_IMAGERY_SYNTHETIC_AIS":
        chain = [
            "Sentinel-1 GRD (REAL- Zenodo Sentinel-1 SAR Oil Spill Dataset)",
            "SAR processing v0.4.0- Lee filter, incidence-trend removal (REAL imagery)",
            "Slick detection v1.0- 8-feature logistic (REAL scene)",
            "Metocean forcing (SIMULATED- SyntheticOcean; NetCDFOcean if CMEMS/ERA5 available)",
            "Drift model v0.3- RK2 Lagrangian ensemble",
            "Source-term inversion v0.2 (IoU on REAL slick)",
            "AIS reconstruction (SYNTHETIC_OVERLAY- synthetic traffic overlaid on real scene geography; honest distinct label, not SIMULATION)",
            "Six-axis attribution v0.4- evidence index",
        ]
    elif data_mode == "SYNTHETIC_OVERLAY":
        chain = [
            "Sentinel-1 GRD (SYNTHETIC_OVERLAY- synthetic slick overlaid on real geography: MV Rak 2011 anchor ~20 nm off Mumbai, 19.03N 72.12E; labelled honestly per §3)",
            "SAR processing v0.4.0- Lee filter, incidence-trend removal",
            "Slick detection v1.0- 8-feature logistic",
            "Metocean forcing (SIMULATED- SyntheticOcean analytic)",
            "Drift model v0.3- RK2 Lagrangian ensemble",
            "Source-term inversion v0.2",
            "AIS reconstruction (SYNTHETIC_OVERLAY- synthetic traffic on real-documented incident geography)",
            "Six-axis attribution v0.4",
        ]
    else:
        chain = [
            "Sentinel-1 GRD (SIMULATED- physics-based sarsim with Gamma speckle, incidence trend, look-alikes)",
            "SAR processing v0.4.0- Lee filter, incidence-trend removal",
            "Slick detection v1.0- 8-feature logistic",
            "Metocean forcing (SIMULATED- synthetic ocean + wind)",
            "Drift model v0.3- RK2 Lagrangian ensemble",
            "Source-term inversion v0.2",
            "AIS reconstruction (SIMULATED- synthesised traffic + decoys)",
            "Six-axis attribution v0.4- evidence index, not probability (NFR-10)",
        ]
    return dict(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        data_mode=data_mode,
        model_versions=MODEL_VERSIONS,
        chain=chain,
        particle_seed="deterministic per-incident (provenance attached)",
        forcing_product=("NetCDFOcean (CMEMS 001_024 + ERA5) when available, "
                        "else SyntheticOcean analytic- see providers registry per source"),
    )


def build(report, incident_id, jurisdiction, coast_km, coast_name,
          alerts, patrol, outdir, data_mode=None):
    """Write JSON / GeoJSON / CSV artefacts for one incident."""
    os.makedirs(outdir, exist_ok=True)
    d = report["detections"][0]
    src = report["source"]
    # Resolve honest mode from report or arg or fallback
    if data_mode is None:
        data_mode = report.get("data_mode") or report.get("oiltrace", {}).get("data_mode") or "SIMULATION"
    # Try to include narrative if module present (§4.3)
    try:
        from .narrative import brief_for_suspect  # type: ignore
        _has_narrative = True
    except Exception:
        _has_narrative = False
        brief_for_suspect = None  # type: ignore

    core = dict(
        incident_id=incident_id,
        classification="INVESTIGATIVE LEAD- NOT LEGAL EVIDENCE",
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
                          terms=s["terms"], evidence=s["evidence"],
                          narrative=(brief_for_suspect(s, report) if _has_narrative else None))
                     for i, s in enumerate(report["suspects"][:6])],
        alerts=alerts, patrol=patrol,
        provenance=_provenance(data_mode),
        data_mode=data_mode,
        validation_note=(
            "Segmentation and origin errors are measured against a KNOWN "
            "ground truth built by the same drift physics the pipeline "
            "inverts. Real-world accuracy will differ."
            if data_mode == "SIMULATION" else
            "Real/synthetic-overlay mode: no laboratory ground truth to compare against. "
            "Confidence rests on the reported per-stage uncertainty (inversion IoU, "
            "search dispersion) and on multi-axis evidence- see validation field."),
        validation=report["validation"],
        legal_note=(
            "This document is decision-support intelligence. It does not "
            "establish an offence under MARPOL or any national law. "
            "Enforcement action requires corroboration (oil fingerprinting, "
            "port state inspection, chain of custody)."),
        # Grounded narratives (§4.3)- also expose at top-level for convenience
        narratives=([dict(mmsi=s["mmsi"], narrative=brief_for_suspect(s, report))
                     for s in report["suspects"][:6]] if _has_narrative else []),
    )

    # JSON must not contain NaN/Inf (browser JSON.parse rejects them). Mirror sagar/api/export._clean.
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
    core = _clean(core)
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
