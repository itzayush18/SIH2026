"""Run the full pipeline and write web artefacts to data/out/.

    python scripts/run_demo.py [--seed 11] [--out data/out]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sagar.api import export
from sagar.core import pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="data/out")
    ap.add_argument("--hours-back", type=float, default=24.0)
    ap.add_argument("--hours-fwd", type=float, default=18.0)
    a = ap.parse_args()

    t0 = time.time()
    print("running pipeline ...")
    r = pipeline.run(seed=a.seed, hours_back=a.hours_back, hours_fwd=a.hours_fwd)
    rep = export.build(r, a.out)
    dt = time.time() - t0

    v = r["validation"]
    top = r["detections"][0]
    c = r["characterization"]
    print(f"\n--- SAGAR-DRISHTI  ({dt:.1f}s) ---")
    print(f"slick        {top.id}  {top.area_km2:.1f} km^2  P(oil)={top.p_oil:.3f}  "
          f"{top.length_km:.1f} x {top.width_km:.1f} km")
    print(f"segmentation IoU {v['segmentation']['iou']:.3f}  F1 {v['segmentation']['f1']:.3f}")
    print(f"character    {c['bonn_class']}, ~{c['volume_m3']:.0f} m^3 "
          f"({c['tonnes']:.0f} t), age {c['age_best_h']:.1f} h [{c['confidence']}]")
    print(f"inversion    origin error {v['inversion_error_km']:.2f} km, "
          f"time error {v['inversion_time_error_h']*60:.0f} min, "
          f"course error {v['inversion_course_error_deg']:.1f} deg, "
          f"fit IoU {v['inversion_iou']:.3f}")
    print(f"attribution  {'CORRECT' if v['attribution_correct'] else 'WRONG'} "
          f"-> {v['top_suspect']}")
    for s in r["suspects"][:3]:
        print(f"   {s.score:6.3f}  {s.mmsi}  {s.name}")
    print(f"\nwrote {os.path.join(a.out, 'report.json')} (+ 3 PNG overlays)")
    print("serve the UI with:  python scripts/serve.py")


if __name__ == "__main__":
    main()
