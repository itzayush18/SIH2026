"""End-to-end orchestration: SAR scene -> detection -> characterisation ->
hindcast/forecast -> AIS attribution -> a single JSON-serialisable report."""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

from . import ais, attribute, characterize, detect, drift, inversion, scenario
from .geoutil import Origin, haversine

# Arabian Sea off Mumbai — a heavily trafficked tanker approach.
DEFAULT_ORIGIN = Origin(lat=19.35, lon=71.80)


def _drift_speed(ocean, epoch, lat, lon):
    f = ocean.sample(epoch, lat, lon)
    ax = f.u_cur + 0.03 * f.u_wind
    ay = f.v_cur + 0.03 * f.v_wind
    return math.hypot(ax, ay), f


def run_on(scene, ocean, vessels, seed=3, hours_back=24.0, hours_fwd=18.0,
           n_particles=4000, epoch_iso="2026-03-14T06:00:00",
           p_threshold=0.5, unet_model=None, on_stage=None):
    """Run the physics chain on an ALREADY-BUILT scene + ocean + vessel set —
    i.e. real data, where there is no ground truth. Returns the same result-dict
    shape as `run()` (so `sagar.api.export.build` renders it identically), but the
    validation block carries only self-consistency numbers (inversion fit IoU),
    not truth-referenced errors, and `data_mode` is REAL.

    `vessels` is a dict[mmsi -> Vessel] (real AIS via ais.load_csv, or synthetic
    candidates); pass {} to skip attribution.
    """
    emit = on_stage or (lambda *_: None)
    origin = scene.spec.origin

    emit("scene", {"bounds": list(scene.bounds), "size": scene.spec.size,
                   "pixel_m": scene.spec.pixel_m,
                   "mean_wind_ms": scene.meta.get("mean_wind")})

    if unet_model:
        emit("detect", {"message": "U-Net segmentation (trained on Zenodo)"})
        from . import unet_detect
        detections, labels = unet_detect.detect(scene, unet_model, prob_threshold=p_threshold)
    else:
        emit("detect", {"message": "Speckle-filtering, detrending, thresholding"})
        detections, labels = detect.detect(scene, p_threshold=p_threshold)
    if not detections:
        raise RuntimeError("no slick detected in the real scene "
                           "(try a lower p_threshold, or a scene with a known spill)")
    top = detections[0]
    mask = labels == top.mask_index
    emit("detected", {"n": len(detections), "top": top.to_dict()})

    emit("characterize", {"message": "Estimating thickness, volume, age"})
    dspeed, forcing = _drift_speed(ocean, scene.spec.epoch, *top.centroid_lonlat[::-1])
    char = characterize.characterize(top, forcing, dspeed)
    emit("characterized", {"characterization": char})

    emit("drift", {"message": f"Advecting {n_particles} particles backwards {hours_back:.0f} h"})
    back = drift.hindcast(scene, ocean, mask, hours_back=hours_back,
                          n_particles=n_particles, seed=seed)
    fwd = drift.forecast(scene, ocean, mask, hours_fwd=hours_fwd,
                         n_particles=n_particles, seed=seed + 1)
    pdf = drift.origin_pdf(back, cell_m=750.0, time_bin_s=1800.0)
    peak = drift.pdf_peak(pdf)
    emit("drifted", {"peak": peak})

    emit("invert", {"message": "Source-term inversion: fitting a moving line source"})
    hyp = inversion.invert(scene, ocean, mask, seed=seed)
    spread = inversion.search_dispersion(hyp, origin)
    emit("inverted", {"iou": hyp.iou, "t_start_h": hyp.t_start / 3600.0,
                      "duration_h": hyp.duration / 3600.0,
                      "course_deg": hyp.course_deg, "speed_kn": hyp.speed_kn})

    emit("attribute", {"message": "Scoring AIS traffic against the inferred source"})
    suspects = attribute.rank(vessels, pdf, top, origin, source_hyp=hyp) if vessels else []
    emit("attributed", {"suspects": [dict(mmsi=s.mmsi, name=s.name, score=s.score)
                                     for s in suspects[:5]]})

    return dict(
        scene=scene, ocean=ocean, truth=None, detections=detections,
        labels=labels, mask=mask, metrics=None, characterization=char,
        back=back, fwd=fwd, pdf=pdf, peak=peak, vessels=vessels,
        source=hyp, source_dispersion=spread, suspects=suspects, epoch_iso=epoch_iso,
        validation=dict(
            data_mode="REAL",
            ground_truth=False,
            inversion_iou=hyp.iou,
            top_suspect=suspects[0].mmsi if suspects else None,
        ))


def run(seed=11, hours_back=24.0, hours_fwd=18.0, n_particles=4000,
        origin=DEFAULT_ORIGIN, epoch_iso="2026-03-14T06:00:00",
        on_stage=None):
    """Run the full pipeline. `on_stage(name, dict)` gets called at each stage
    boundary so a streaming endpoint can push progress without knowing anything
    about the internals."""
    emit = on_stage or (lambda *_: None)

    emit("ingest", {"message": "Reading SAR scene and building metocean forcing"})
    scene, ocean, truth = scenario.build(origin, seed=seed)
    emit("scene", {"bounds": list(scene.bounds), "size": scene.spec.size,
                   "pixel_m": scene.spec.pixel_m,
                   "mean_wind_ms": scene.meta.get("mean_wind")})

    emit("detect", {"message": "Speckle-filtering, detrending, thresholding"})
    detections, labels = detect.detect(scene)
    if not detections:
        raise RuntimeError("no slick detected")
    top = detections[0]
    mask = labels == top.mask_index
    metrics = detect.evaluate(mask, scene.truth_mask)
    emit("detected", {"n": len(detections), "top": top.to_dict(),
                      "iou": metrics["iou"], "f1": metrics["f1"]})

    emit("characterize", {"message": "Estimating thickness, volume, age"})
    dspeed, forcing = _drift_speed(ocean, scene.spec.epoch, *top.centroid_lonlat[::-1])
    char = characterize.characterize(top, forcing, dspeed)
    emit("characterized", {"characterization": char})

    emit("drift", {"message": f"Advecting {n_particles} particles backwards {hours_back:.0f} h"})
    back = drift.hindcast(scene, ocean, mask, hours_back=hours_back,
                          n_particles=n_particles, seed=seed)
    fwd = drift.forecast(scene, ocean, mask, hours_fwd=hours_fwd,
                         n_particles=n_particles, seed=seed + 1)
    pdf = drift.origin_pdf(back, cell_m=750.0, time_bin_s=1800.0)
    peak = drift.pdf_peak(pdf)
    emit("drifted", {"peak": peak})

    emit("invert", {"message": "Source-term inversion: fitting a moving line source"})
    hyp = inversion.invert(scene, ocean, mask, seed=seed)
    spread = inversion.search_dispersion(hyp, origin)
    emit("inverted", {"iou": hyp.iou,
                      "t_start_h": hyp.t_start/3600.0, "duration_h": hyp.duration/3600.0,
                      "course_deg": hyp.course_deg, "speed_kn": hyp.speed_kn})

    emit("attribute", {"message": "Reconstructing AIS traffic and scoring vessels"})
    vessels = ais.synthesize(origin, truth.origin_xy, truth.release_t0, seed=seed + 5)
    suspects = attribute.rank(vessels, pdf, top, origin, source_hyp=hyp)
    emit("attributed", {"suspects": [dict(mmsi=s.mmsi, name=s.name, score=s.score)
                                     for s in suspects[:5]]})

    tlat, tlon = origin.to_ll(*truth.origin_xy)
    origin_err_km = haversine(peak["lat"], peak["lon"], tlat, tlon) / 1000.0

    hlat, hlon = origin.to_ll(hyp.x0, hyp.y0)
    inv_err_km = haversine(hlat, hlon, tlat, tlon) / 1000.0

    return dict(
        scene=scene, ocean=ocean, truth=truth, detections=detections,
        labels=labels, mask=mask, metrics=metrics, characterization=char,
        back=back, fwd=fwd, pdf=pdf, peak=peak, vessels=vessels, source=hyp, source_dispersion=spread,
        suspects=suspects, epoch_iso=epoch_iso,
        validation=dict(
            segmentation=metrics,
            pdf_peak_error_km=origin_err_km,
            inversion_error_km=inv_err_km,
            inversion_time_error_h=abs(hyp.t_start - truth.release_t0) / 3600.0,
            inversion_course_error_deg=abs((hyp.course_deg - truth.course_deg + 180) % 360 - 180),
            inversion_iou=hyp.iou,
            true_origin=dict(lat=tlat, lon=tlon, t_rel_s=truth.release_t0),
            attribution_correct=bool(suspects and suspects[0].mmsi == truth.mmsi),
            top_suspect=suspects[0].mmsi if suspects else None,
        ))
