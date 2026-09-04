"""Run detect -> characterise -> hindcast/forecast -> invert -> attribute on
REAL inputs instead of a synthetic scenario.

This is deliberately not a drop-in replacement for `scripts/run_demo.py`: the
demo pipeline (`sagar.core.pipeline.run`) fabricates its AIS traffic from the
scenario's own ground truth (`ais.synthesize(origin, truth.origin_xy, ...)`)
so it can report an error metric against a known answer. There is no ground
truth for a real scene, so this script swaps that stage for real AIS
(`ais.load_csv`) and drops the validation block instead of faking one.

Needs three real inputs already on disk — fetch them first:

    python scripts/fetch/sentinel1.py --bbox 71.4,19.0,72.1,19.7 \\
        --start 2026-03-13T00:00 --end 2026-03-15T00:00 --out data/scenes/s1.tif
    python scripts/fetch/cmems_era5.py --bbox 71.4,19.0,72.1,19.7 \\
        --start 2026-03-13 --end 2026-03-15 --out data/env
    python scripts/fetch/aishub.py --bbox 71.4,19.0,72.1,19.7 --out data/ais/aishub.csv
      # (or a MarineCadastre CSV in the same schema, see sagar/core/ais.py:load_csv)

Then:

    python scripts/run_real.py --scene data/scenes/s1.tif \\
        --currents data/env/cmems_currents.nc --winds data/env/era5_wind.nc \\
        --ais data/ais/aishub.csv --epoch 2026-03-14T06:00:00 --out data/out/real
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sagar.core import ais, attribute, characterize, detect, drift, inversion, pipeline
from sagar.data.loaders import load_geotiff, NetCDFOcean


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="georeferenced Sentinel-1 GRD GeoTIFF")
    ap.add_argument("--currents", required=True, help="CMEMS NetCDF (uo, vo)")
    ap.add_argument("--winds", required=True, help="ERA5 NetCDF (u10, v10)")
    ap.add_argument("--ais", default=None,
                     help="AIS CSV (MarineCadastre schema); omit to run detection + "
                          "drift + inversion only and skip vessel attribution")
    ap.add_argument("--epoch", required=True,
                     help="scene acquisition time, ISO 8601 UTC — anchors ocean/AIS time")
    ap.add_argument("--hours-back", type=float, default=24.0)
    ap.add_argument("--hours-fwd", type=float, default=18.0)
    ap.add_argument("--n-particles", type=int, default=4000)
    ap.add_argument("--p-threshold", type=float, default=0.5,
                     help="lower this (e.g. 0.3) if the classifier — trained on "
                          "simulated scenes — is under-confident on real SAR")
    ap.add_argument("--unet-model", default=None,
                     help="path to a trained U-Net checkpoint (from scripts/train_unet.py) "
                          "to use learned segmentation instead of the logistic detector")
    ap.add_argument("--out", default="data/out/real")
    a = ap.parse_args()

    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)

    print(f"loading scene {a.scene} ...")
    scene = load_geotiff(a.scene, epoch=0.0)
    origin = scene.spec.origin
    print(f"  origin {origin.lat:.4f},{origin.lon:.4f}  {scene.spec.size}px  "
          f"{scene.spec.pixel_m:.1f} m/px")

    print(f"loading ocean forcing (anchored at {a.epoch}) ...")
    ocean = NetCDFOcean(origin, a.currents, a.winds, epoch_np64=a.epoch)

    if a.ais:
        print("loading AIS ...")
        vessels = ais.load_csv(a.ais, epoch_iso=a.epoch)
        print(f"  {len(vessels)} vessel track(s)")
    else:
        vessels = {}
        print("no --ais given — skipping vessel attribution")

    if a.unet_model:
        print(f"detecting with U-Net {a.unet_model} ...")
        from sagar.core import unet_detect
        detections, labels = unet_detect.detect(scene, a.unet_model, prob_threshold=a.p_threshold)
    else:
        print("detecting (logistic) ...")
        detections, labels = detect.detect(scene, p_threshold=a.p_threshold)
    if not detections:
        sys.exit("no slick detected — try --p-threshold 0.3, or confirm the "
                 "scene actually contains a spill")
    top = detections[0]
    mask = labels == top.mask_index
    print(f"  top candidate: {top.area_km2:.1f} km^2  P(oil)={top.p_oil:.3f}  "
          f"{top.length_km:.1f} x {top.width_km:.1f} km")

    print("characterising ...")
    dspeed, forcing = pipeline._drift_speed(ocean, scene.spec.epoch, *top.centroid_lonlat[::-1])
    char = characterize.characterize(top, forcing, dspeed)
    print(f"  {char['bonn_class']}, ~{char['volume_m3']:.0f} m^3 ({char['tonnes']:.0f} t), "
          f"age {char['age_best_h']:.1f} h [{char['confidence']}]")

    print(f"hindcasting {a.n_particles} particles {a.hours_back:.0f} h back ...")
    back = drift.hindcast(scene, ocean, mask, hours_back=a.hours_back,
                          n_particles=a.n_particles, seed=3)
    fwd = drift.forecast(scene, ocean, mask, hours_fwd=a.hours_fwd,
                         n_particles=a.n_particles, seed=5)
    pdf = drift.origin_pdf(back, cell_m=750.0, time_bin_s=1800.0)
    peak = drift.pdf_peak(pdf)
    plat, plon = peak["lat"], peak["lon"]
    print(f"  backward PDF peak: {plat:.4f},{plon:.4f}")

    print("inverting source term ...")
    hyp = inversion.invert(scene, ocean, mask, seed=3)
    hlat, hlon = origin.to_ll(hyp.x0, hyp.y0)
    print(f"  fit IoU {hyp.iou:.3f}  origin {hlat:.4f},{hlon:.4f}  "
          f"course {hyp.course_deg:.0f} deg  speed {hyp.speed_kn:.1f} kn  "
          f"t_start {hyp.t_start/3600:.1f} h  duration {hyp.duration/3600:.1f} h")

    if vessels:
        print("attributing ...")
        suspects = attribute.rank(vessels, pdf, top, origin, source_hyp=hyp)
        for s in suspects[:5]:
            print(f"  {s.score:6.3f}  {s.mmsi}  {s.name}")
    else:
        suspects = []
        print("no AIS -> no attribution (detection + drift + inversion still ran)")

    report = dict(
        data_mode="REAL",
        scene=os.path.basename(a.scene),
        epoch=a.epoch,
        detection=dict(area_km2=top.area_km2, p_oil=top.p_oil,
                       length_km=top.length_km, width_km=top.width_km),
        characterization=char,
        backward_pdf_peak=dict(lat=plat, lon=plon),
        source_hypothesis=dict(lat=hlat, lon=hlon, course_deg=hyp.course_deg,
                               speed_kn=hyp.speed_kn, t_start_h=hyp.t_start / 3600.0,
                               duration_h=hyp.duration / 3600.0, fit_iou=hyp.iou),
        suspects=[dict(mmsi=s.mmsi, name=s.name, score=s.score) for s in suspects[:10]],
    )
    out_path = os.path.join(a.out, "report_real.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {out_path}  ({time.time() - t0:.1f}s)")
    print("no ground truth for real data, so no IoU/error metrics against a "
          "'true' origin — that's expected, not a bug.")


if __name__ == "__main__":
    main()
