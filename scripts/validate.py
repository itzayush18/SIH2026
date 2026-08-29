"""Batch validation over independent scenarios.

Each seed regenerates everything — metocean fields, slick geometry, discharge
timing, look-alike population and traffic picture — so the numbers below are a
fair repeated measurement rather than one lucky scene.

    python scripts/validate.py --seeds 10
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sagar.core import pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--start", type=int, default=11)
    ap.add_argument("--json", default="data/validation.json")
    a = ap.parse_args()

    rows = []
    for i in range(a.seeds):
        seed = a.start + i * 7
        t0 = time.time()
        try:
            r = pipeline.run(seed=seed)
        except Exception as exc:                      # a miss is a result too
            print(f"seed {seed}: FAILED ({exc})")
            rows.append(dict(seed=seed, failed=str(exc)))
            continue
        v = r["validation"]
        rows.append(dict(seed=seed, runtime_s=time.time() - t0, **{
            k: v[k] for k in ("pdf_peak_error_km", "inversion_error_km",
                              "inversion_time_error_h", "inversion_course_error_deg",
                              "inversion_iou", "attribution_correct")},
            iou=v["segmentation"]["iou"], f1=v["segmentation"]["f1"],
            margin=(r["suspects"][0].score - r["suspects"][1].score)
            if len(r["suspects"]) > 1 else float("nan")))
        x = rows[-1]
        print(f"seed {seed:3d}  IoU {x['iou']:.3f}  origin {x['inversion_error_km']:6.2f} km  "
              f"dt {x['inversion_time_error_h']*60:5.0f} min  "
              f"attrib {'OK ' if x['attribution_correct'] else 'MISS'}  "
              f"margin {x['margin']:.2f}  ({x['runtime_s']:.0f}s)", flush=True)

    ok = [r for r in rows if "failed" not in r]
    if not ok:
        sys.exit("all runs failed")

    def agg(k):
        vals = [r[k] for r in ok if isinstance(r[k], (int, float))]
        return dict(mean=st.mean(vals), median=st.median(vals),
                    min=min(vals), max=max(vals))

    summary = dict(n=len(ok),
                   segmentation_iou=agg("iou"), segmentation_f1=agg("f1"),
                   inversion_error_km=agg("inversion_error_km"),
                   inversion_time_error_h=agg("inversion_time_error_h"),
                   inversion_course_error_deg=agg("inversion_course_error_deg"),
                   inversion_iou=agg("inversion_iou"),
                   pdf_peak_error_km=agg("pdf_peak_error_km"),
                   score_margin=agg("margin"),
                   attribution_accuracy=sum(r["attribution_correct"] for r in ok) / len(ok),
                   runtime_s=agg("runtime_s"), runs=rows)

    print("\n=== summary over", len(ok), "scenarios ===")
    print(f"segmentation IoU      {summary['segmentation_iou']['mean']:.3f} "
          f"(median {summary['segmentation_iou']['median']:.3f})")
    print(f"segmentation F1       {summary['segmentation_f1']['mean']:.3f}")
    print(f"origin position error {summary['inversion_error_km']['mean']:.2f} km "
          f"(median {summary['inversion_error_km']['median']:.2f}, "
          f"worst {summary['inversion_error_km']['max']:.2f})")
    print(f"release time error    {summary['inversion_time_error_h']['mean']*60:.0f} min "
          f"(median {summary['inversion_time_error_h']['median']*60:.0f})")
    print(f"source course error   {summary['inversion_course_error_deg']['mean']:.1f} deg")
    print(f"backward-PDF peak err {summary['pdf_peak_error_km']['mean']:.2f} km  "
          f"<- why inversion exists")
    print(f"attribution accuracy  {summary['attribution_accuracy']*100:.0f}%")
    print(f"top-1 score margin    {summary['score_margin']['mean']:.2f}")
    print(f"runtime per scenario  {summary['runtime_s']['mean']:.0f}s")

    os.makedirs(os.path.dirname(a.json) or ".", exist_ok=True)
    with open(a.json, "w") as f:
        json.dump(summary, f, indent=2, default=float)
    print("wrote", a.json)


if __name__ == "__main__":
    main()
