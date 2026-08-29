"""Orchestrator — fetches every real source whose credentials are configured.

Silently skips channels without credentials. Prints a clear plan first.

    python scripts/fetch/all.py --bbox 68,15,75,22 --start 2026-03-13 --end 2026-03-15
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def has(*keys): return all(os.environ.get(k) for k in keys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    a = ap.parse_args()

    plan = []
    if has("CDSE_USER", "CDSE_PASSWORD"):
        plan.append(("Sentinel-1 GRD (CDSE)", [sys.executable,
            "scripts/fetch/sentinel1.py", "--bbox", a.bbox,
            "--start", a.start + "T00:00", "--end", a.end + "T00:00",
            "--out", "data/scenes/s1.tif"]))
    if has("CMEMS_USER") or os.path.exists(os.path.expanduser(
            "~/.copernicusmarine/credentials")):
        plan.append(("CMEMS + ERA5", [sys.executable,
            "scripts/fetch/cmems_era5.py", "--bbox", a.bbox,
            "--start", a.start, "--end", a.end, "--out", "data/env"]))
    if has("AISHUB_USER"):
        plan.append(("AISHub live AIS", [sys.executable,
            "scripts/fetch/aishub.py", "--bbox", a.bbox,
            "--out", "data/ais/aishub.csv"]))

    if not plan:
        print("No real-data credentials configured.")
        print("Set the ones you have in .env and rerun. See .env.example.")
        return

    print("Plan:")
    for name, _ in plan: print(f"  · {name}")
    print()
    for name, cmd in plan:
        print(f"--- {name} ---")
        rc = subprocess.call(cmd)
        print(f"({rc})")


if __name__ == "__main__":
    main()
