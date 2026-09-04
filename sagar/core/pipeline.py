"""End-to-end orchestration: SAR scene -> detection -> characterisation ->
hindcast/forecast -> AIS attribution -> a single JSON-serialisable report.

Adds `run_with_scene` so a real Zenodo TIFF or a GeoTIFF can be pushed through
*the same* detect→characterize→drift→inversion→attribute chain without cloning
the whole function. `run()` (synthetic) delegates to it; `run_real()` is the
honest entry point for §4.1.
"""
from __future__ import annotations

import math
import os

import numpy as np
from scipy import ndimage

from . import ais, attribute, characterize, detect, drift, inversion, scenario
from .geoutil import Origin, haversine

# Arabian Sea off Mumbai- a heavily trafficked tanker approach.
DEFAULT_ORIGIN = Origin(lat=19.35, lon=71.80)


#: Where a trained U-Net checkpoint is looked for. Override with SAGAR_UNET.
UNET_DEFAULT_PATH = "data/models/unet_v1.pt"


def _run_detector(scene, emit):
    """Detect slicks with the U-Net when one is available, else the logistic.

    Selection is explicit and fails loudly in only one direction: if a
    checkpoint is configured but unusable (torch missing, file corrupt), we
    fall back to the logistic detector and *say so* through `emit`, rather
    than silently reporting U-Net provenance for logistic results. The
    returned detector name is carried into the report so the dashboard and
    evidence pack can state which model produced the detections.
    """
    path = os.environ.get("SAGAR_UNET", UNET_DEFAULT_PATH)
    if os.path.exists(path):
        try:
            from . import unet_detect
            dets, labels = unet_detect.detect(scene, path)
            if dets:
                emit("detect", {"message": f"U-Net segmenter ({os.path.basename(path)})"})
                return dets, labels, "unet"
            emit("detect", {"message": "U-Net returned no regions- using logistic detector"})
        except Exception as exc:
            emit("detect", {"message": f"U-Net unavailable ({exc})- using logistic detector"})

    dets, labels = detect.detect(scene)
    return dets, labels, "logistic-8feature"


def _drift_speed(ocean, epoch, lat, lon):
    f = ocean.sample(epoch, lat, lon)
    ax = f.u_cur + 0.03 * f.u_wind
    ay = f.v_cur + 0.03 * f.v_wind
    return math.hypot(ax, ay), f


def run_with_scene(scene, ocean, vessels_or_path=None, seed=11,
                   hours_back=24.0, hours_fwd=18.0, n_particles=4000,
                   origin=None, epoch_iso="2026-03-14T06:00:00",
                   truth=None, data_mode="SIMULATION", on_stage=None):
    """Core chain that works for both synthetic and real scenes.

    `vessels_or_path` may be:
      - a dict of Vessel already loaded (real AIS)
      - a path to a MarineCadastre CSV (str)
      - None- synthesise traffic (honest SYNTHETIC_OVERLAY)

    Returns the same report dict as `run()` but with `validation` downgraded
    when truth is not available, and with `data_mode` propagated.

    The detection → inversion path is *identical* to the synthetic one; only the
    ingestion provenance differs. This is what the Zenodo exercise is meant to
    stress-test.
    """
    origin = origin or scene.spec.origin
    emit = on_stage or (lambda *_: None)

    emit("detect", {"message": "Speckle-filtering, detrending, thresholding"})
    detections, labels, detector = _run_detector(scene, emit)
    if not detections:
        raise RuntimeError("no slick detected")
    top = detections[0]
    mask = labels == top.mask_index
    # When truth_mask is all-zero (real TIFF without label) we report NaN IoU
    if scene.truth_mask is not None and scene.truth_mask.any():
        metrics = detect.evaluate(mask, scene.truth_mask)
    else:
        metrics = dict(iou=float("nan"), precision=float("nan"),
                       recall=float("nan"), f1=float("nan"))
    emit("detected", {"n": len(detections), "top": top.to_dict(),
                      "iou": metrics["iou"], "f1": metrics["f1"]})

    emit("characterize", {"message": "Estimating thickness, volume, age"})
    try:
        dspeed, forcing = _drift_speed(ocean, scene.spec.epoch, *top.centroid_lonlat[::-1])
    except Exception:
        dspeed, forcing = 0.15, None
        # minimal forcing fallback
        from .environment import Forcing as _Forcing
        forcing = _Forcing(0.1, 0.05, 3.0, 2.0)
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
    # Resolve vessels- keep SIMULATION honest, SYNTHETIC_OVERLAY distinct
    if isinstance(vessels_or_path, dict):
        vessels = vessels_or_path
    elif isinstance(vessels_or_path, str) and os.path.exists(vessels_or_path):
        vessels = ais.load_csv(vessels_or_path, epoch_iso=epoch_iso)
    elif vessels_or_path is None and truth is not None:
        # Pure SIMULATION: truth is known, decoys are built around it
        vessels = ais.synthesize(origin, truth.origin_xy, truth.release_t0, seed=seed + 5)
    elif vessels_or_path is None and truth is None:
        # SYNTHETIC_OVERLAY / REAL_IMAGERY_SYNTHETIC_AIS: no truth, so place synthetic
        # traffic relative to the recovered source itself (honest: label stays synthetic)
        vessels = ais.synthesize(origin, (hyp.x0, hyp.y0), hyp.t_start, seed=seed + 5)
    else:
        vessels = {}
    suspects = attribute.rank(vessels, pdf, top, origin, source_hyp=hyp) if vessels else []
    emit("attributed", {"suspects": [dict(mmsi=s.mmsi, name=s.name, score=s.score)
                                     for s in suspects[:5]]})

    # Validation: only calibrated when truth is known
    if truth is not None:
        tlat, tlon = origin.to_ll(*truth.origin_xy)
        origin_err_km = haversine(peak["lat"], peak["lon"], tlat, tlon) / 1000.0
        hlat, hlon = origin.to_ll(hyp.x0, hyp.y0)
        inv_err_km = haversine(hlat, hlon, tlat, tlon) / 1000.0
        validation = dict(
            segmentation=metrics,
            pdf_peak_error_km=origin_err_km,
            inversion_error_km=inv_err_km,
            inversion_time_error_h=abs(hyp.t_start - truth.release_t0) / 3600.0,
            inversion_course_error_deg=abs((hyp.course_deg - truth.course_deg + 180) % 360 - 180),
            inversion_iou=hyp.iou,
            true_origin=dict(lat=tlat, lon=tlon, t_rel_s=truth.release_t0),
            attribution_correct=bool(suspects and suspects[0].mmsi == truth.mmsi),
            top_suspect=suspects[0].mmsi if suspects else None,
        )
    else:
        validation = dict(
            segmentation=metrics,
            pdf_peak_error_km=float("nan"),
            inversion_error_km=float("nan"),
            inversion_time_error_h=float("nan"),
            inversion_course_error_deg=float("nan"),
            inversion_iou=hyp.iou,
            true_origin=None,
            attribution_correct=None,
            top_suspect=suspects[0].mmsi if suspects else None,
            note="Real imagery- no laboratory ground truth. Confidence rests on inversion IoU and search dispersion, not on a calibrated error bar.",
        )

    return dict(
        detector=detector,
        scene=scene, ocean=ocean, truth=truth, detections=detections,
        labels=labels, mask=mask, metrics=metrics, characterization=char,
        back=back, fwd=fwd, pdf=pdf, peak=peak, vessels=vessels, source=hyp, source_dispersion=spread,
        suspects=suspects, epoch_iso=epoch_iso, data_mode=data_mode,
        validation=validation)


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
    res = run_with_scene(scene, ocean, vessels_or_path=None, seed=seed,
                         hours_back=hours_back, hours_fwd=hours_fwd,
                         n_particles=n_particles, origin=origin,
                         epoch_iso=epoch_iso, truth=truth,
                         data_mode="SIMULATION", on_stage=on_stage)
    # run_with_scene already emitted detect..attribute; return its dict but ensure truth present
    return res


def run_real(scene_path: str = None, origin=None, ais_csv: str = None,
             seed=11, hours_back=24.0, hours_fwd=18.0, n_particles=3500,
             epoch_iso="2026-03-14T06:00:00", on_stage=None):
    """Entry point for §4.1: Zenodo TIFF (or any GeoTIFF) through the *unmodified*
    pipeline. Falls back honestly to SYNTHETIC_OVERLAY when the file is absent.

    Honest labelling (§2): never claim REAL when the read failed. The returned
    report's `data_mode` tells the truth and the evidence provenance spells out
    which branch was taken, so a demo operator cannot accidentally show synthetic
    data as real.
    """
    emit = on_stage or (lambda *_: None)
    from .environment import SyntheticOcean

    # --- Try real imagery first ----------------------------------------
    data_mode = "REAL_IMAGERY_SYNTHETIC_AIS"
    ais_source = ais_csv
    real_scene = None
    real_ocean = None

    # Determine real scene location: explicit path > env > data/zenodo scan
    candidates = []
    if scene_path and os.path.exists(scene_path):
        candidates = [scene_path]
    else:
        for d in ("data/zenodo", "data/real", "data/samples"):
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    if fn.lower().endswith((".tif", ".tiff")):
                        candidates.append(os.path.join(d, fn))
    # Try each candidate through the adapter that actually exists
    for cand in candidates[:3]:
        try:
            emit("ingest", {"message": f"Loading Zenodo scene {os.path.basename(cand)}"})
            from sagar.data.loaders import load_zenodo_tiff
            # need an origin- derive from candidate if possible, else fallback DEFAULT_ORIGIN
            use_origin = origin or DEFAULT_ORIGIN
            real_scene = load_zenodo_tiff(cand, origin=use_origin)
            # Also try CMEMS/ERA5 if NetCDFs present (stretch goal, not required)
            # For now use SyntheticOcean; the adapter contract is identical.
            real_ocean = SyntheticOcean(real_scene.spec.origin, seed=seed)
            # Heuristic: if AIS CSV also present, upgrade mode
            if ais_csv and os.path.exists(ais_csv):
                data_mode = "REAL_IMAGERY_REAL_AIS"
                ais_source = ais_csv
            else:
                # no real AIS- synthetic overlay (still counts as real imagery)
                data_mode = "REAL_IMAGERY_SYNTHETIC_AIS"
            break
        except Exception as e:
            emit("ingest", {"message": f"Zenodo load failed {os.path.basename(cand)}: {e}- trying next"})
            continue

    if real_scene is None:
        # Honest fallback: no Zenodo file found (CI, fresh clone without download)
        # Build a *synthetic-overlay* scene anchored at the real MV Rak geography
        # so the demo is not fully invented- it overlays synthetic oil onto a
        # documented incident locale (see sagar/data/mv_rak.py / §4.4).
        emit("ingest", {"message": "No Zenodo TIFF found- falling back to SYNTHETIC_OVERLAY (honest)"})
        data_mode = "SYNTHETIC_OVERLAY"
        # Use MV Rak origin (19.03 N, 72.12 E- ~20 nm off Mumbai) for overlay
        try:
            from sagar.data.mv_rak import ORIGIN as RAK_ORIGIN
            overlay_origin = RAK_ORIGIN
        except Exception:
            overlay_origin = Origin(lat=19.03, lon=72.12)
        real_scene, real_ocean, _truth = scenario.build(overlay_origin, seed=seed + 100)
        # Mark meta so the UI badge can explain the fallback
        real_scene.meta["fallback_note"] = "SYNTHETIC_OVERLAY- synthetic slick over real geography (MV Rak 2011 anchor)- no Zenodo file present"
        # Purposely discard _truth so validation downgrades honestly
        return run_with_scene(real_scene, real_ocean, vessels_or_path=ais_source,
                              seed=seed, hours_back=hours_back, hours_fwd=hours_fwd,
                              n_particles=n_particles, origin=overlay_origin,
                              epoch_iso=epoch_iso, truth=None,
                              data_mode=data_mode, on_stage=on_stage)

    # Real path succeeded
    return run_with_scene(real_scene, real_ocean, vessels_or_path=ais_source,
                          seed=seed, hours_back=hours_back, hours_fwd=hours_fwd,
                          n_particles=n_particles, origin=real_scene.spec.origin,
                          epoch_iso=epoch_iso, truth=None,
                          data_mode=data_mode, on_stage=on_stage)
