"""Download files attached to a Zenodo record via the public API.

No auth needed — the Sentinel-1 oil-spill dataset records are all open access.
Sizes are real, not the "2 GB total" a certain deep-research blueprint claimed:

    record 8346860  (Part I,   train/val oil)         ~40.7 GB images + 6 MB masks
    record 8253899  (Part II,  train/val no-oil/lookalike)  ~45.9 GB
    record 13761290 (Part III, test)                  ~9.9 GB

    python scripts/fetch/zenodo.py --record 8346860 --out /Volumes/Kioxia/oiltrace-data/zenodo/part1
    python scripts/fetch/zenodo.py --record 8346860 --out ... --only mask   # skip the 40 GB images archive

Uses the record API (https://zenodo.org/api/records/<id>) to resolve the real
download links rather than guessing filenames, and shells out to `curl -C -`
(resumable) instead of urllib, because a dropped connection partway through a
40 GB archive should not mean starting over.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", required=True, help="Zenodo record id, e.g. 8346860")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None,
                     help="substring filter on filename, e.g. 'mask' to skip huge image archives")
    a = ap.parse_args()

    api = f"https://zenodo.org/api/records/{a.record}"
    print(f"GET {api}")
    with urllib.request.urlopen(api, timeout=30) as r:
        meta = json.load(r)

    files = meta.get("files", [])
    if not files:
        sys.exit(f"record {a.record} has no files (or is restricted)")
    if a.only:
        files = [f for f in files if a.only.lower() in f["key"].lower()]

    os.makedirs(a.out, exist_ok=True)
    total_bytes = sum(f["size"] for f in files)
    print(f"{len(files)} file(s), {total_bytes/1e9:.1f} GB total -> {a.out}")

    for i, f in enumerate(files, 1):
        name = f["key"]
        url = f["links"]["self"]
        dest = os.path.join(a.out, name)
        print(f"[{i}/{len(files)}] {name} ({f['size']/1e9:.2f} GB) -> {dest}")
        # -C - resumes a partial file instead of restarting; --retry survives
        # transient wifi drops on a download this large.
        subprocess.run(["curl", "-L", "-C", "-", "--retry", "10",
                        "--retry-delay", "5", "-o", dest, url], check=True)

    print(f"done — {len(files)} file(s) in {a.out}")


if __name__ == "__main__":
    main()
