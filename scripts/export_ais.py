"""Write the synthetic traffic picture as a MarineCadastre-format AIS CSV, and
read it back, to prove the ingest path used for real feeds actually round-trips.

    python scripts/export_ais.py --out data/ais_sample.csv
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sagar.core import ais, scenario
from sagar.core.pipeline import DEFAULT_ORIGIN

EPOCH = "2026-03-14T06:00:00"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/ais_sample.csv")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()

    _, _, truth = scenario.build(DEFAULT_ORIGIN, seed=a.seed)
    vessels = ais.synthesize(DEFAULT_ORIGIN, truth.origin_xy, truth.release_t0,
                             seed=a.seed + 5)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    ais.write_csv(a.out, vessels, epoch_iso=EPOCH)

    back = ais.load_csv(a.out, epoch_iso=EPOCH)
    n_in = sum(len(v.pings) for v in vessels.values())
    n_out = sum(len(v.pings) for v in back.values())
    print(f"wrote {a.out}: {len(vessels)} vessels, {n_in} position reports")
    print(f"round-trip: {len(back)} vessels, {n_out} reports "
          f"-> {'OK' if (len(back), n_out) == (len(vessels), n_in) else 'MISMATCH'}")
    for v in list(back.values())[:3]:
        print(f"  {v.mmsi}  {v.name:18s} {v.type_name:9s} "
              f"{len(v.pings):4d} pings, {len(v.gaps())} gap(s)")


if __name__ == "__main__":
    main()
