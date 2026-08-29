"""Real-scene runner.

Takes a Sentinel-1 GeoTIFF (and optionally CMEMS + ERA5 NetCDFs) and runs the
production pipeline on it, producing the same OILTRACE incident record the
simulator produces. If real files are missing, the caller should fall back to
`incidents.run(scenario)` — this module never fabricates.
"""
from __future__ import annotations

import os
import time

from sagar.api import export as _export
from sagar.core import ais, attribute, characterize, detect, drift, inversion
from sagar.core.environment import SyntheticOcean

from . import alerts as _alerts, evidence as _evidence, patrol as _patrol
from .jurisdictions import classify, nearest_coast_km


def run_from_geotiff(geotiff_path, outdir_root, currents_nc=None, winds_nc=None,
                     ais_csv=None, epoch_iso=None, on_stage=None):
    from sagar.data.loaders import load_geotiff, NetCDFOcean
    import numpy as np
    emit = on_stage or (lambda *_: None)

    emit("ingest", {"message": f"Reading {os.path.basename(geotiff_path)}"})
    scene = load_geotiff(geotiff_path)
    origin = scene.spec.origin

    if currents_nc and winds_nc:
        emit("environment", {"message": "Loading CMEMS + ERA5 fields"})
        ocean = NetCDFOcean(origin, currents_nc, winds_nc,
                            epoch_np64=np.datetime64(epoch_iso or "now"))
        mode = "REAL_METOCEAN"
    else:
        ocean = SyntheticOcean(origin)
        mode = "SIMULATED_METOCEAN"

    emit("detect", {"message": "Speckle → detrend → threshold"})
    dets, labels = detect.detect(scene)
    if not dets:
        raise RuntimeError("no slick detected in that scene")
    top = dets[0]
    mask = labels == top.mask_index

    dspeed = (ocean.sample(scene.spec.epoch, *top.centroid_lonlat[::-1])
              if hasattr(ocean, "sample") else None)
    forcing = dspeed
    char = characterize.characterize(
        top, forcing, dspeed and (forcing.u_cur**2 + forcing.v_cur**2)**.5 or 0.15)

    emit("drift", {"message": "Backward + forward drift ensembles"})
    back = drift.hindcast(scene, ocean, mask, hours_back=24.0)
    fwd = drift.forecast(scene, ocean, mask, hours_fwd=18.0)
    pdf = drift.origin_pdf(back, cell_m=750.0, time_bin_s=1800.0)
    peak = drift.pdf_peak(pdf)

    emit("invert", {"message": "Source-term inversion"})
    hyp = inversion.invert(scene, ocean, mask)
    disp = inversion.search_dispersion(hyp, origin)

    if ais_csv:
        emit("ais", {"message": f"Loading {os.path.basename(ais_csv)}"})
        vessels = ais.load_csv(ais_csv, epoch_iso=epoch_iso)
    else:
        # No real AIS -> attribution can't run honestly. Empty suspect list.
        vessels = {}
    suspects = attribute.rank(vessels, pdf, top, origin, source_hyp=hyp) if vessels else []

    result = dict(scene=scene, ocean=ocean, detections=dets, labels=labels,
                  mask=mask, characterization=char, back=back, fwd=fwd,
                  pdf=pdf, peak=peak, vessels=vessels, source=hyp,
                  source_dispersion=disp, suspects=suspects,
                  metrics=dict(), truth=None,
                  epoch_iso=epoch_iso or time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                  validation=dict(segmentation=dict(iou=float("nan"),
                                                    precision=float("nan"),
                                                    recall=float("nan"),
                                                    f1=float("nan")),
                                  pdf_peak_error_km=float("nan"),
                                  inversion_error_km=float("nan"),
                                  inversion_time_error_h=float("nan"),
                                  inversion_course_error_deg=float("nan"),
                                  inversion_iou=hyp.iou,
                                  attribution_correct=None,
                                  true_origin=None,
                                  top_suspect=(suspects[0].mmsi if suspects else None)))
    incident_id = f"OIL-LIVE-{int(time.time())%10000:04d}"
    scene_outdir = os.path.join(outdir_root, incident_id)
    rep = _export.build(result, scene_outdir)

    lat, lon = top.centroid_lonlat[1], top.centroid_lonlat[0]
    jur = classify(lat, lon)
    coast_km, coast_name = nearest_coast_km(lat, lon)

    a = _alerts.derive(result, incident_id, jur, coast_km, coast_name)
    p = _patrol.recommend(rep, jur, coast_km, coast_name)
    pack = _evidence.build(rep, incident_id, jur, coast_km, coast_name, a, p, scene_outdir)

    rep["oiltrace"] = dict(incident_id=incident_id,
        scenario=dict(slug="live", name=os.path.basename(geotiff_path),
                      subtitle=f"Live Sentinel-1 scene · {mode}",
                      difficulty="live", story="Real ingested scene.",
                      tags=["live", mode.lower()]),
        jurisdiction=dict(name=jur.name, kind=jur.kind, sovereign=jur.sovereign,
                          marpol_regime=jur.marpol_regime, source=jur.source),
        nearest_coast=dict(km=coast_km, name=coast_name),
        alerts=a, patrol=p, evidence_pack=pack,
        provenance=_evidence._provenance(),
        data_mode="MIXED" if (currents_nc or ais_csv) else "PARTIAL_REAL")
    import json
    with open(os.path.join(scene_outdir, "report.json"), "w") as f:
        json.dump(rep, f, indent=2, default=float, allow_nan=False)
    return rep
