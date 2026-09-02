"""Query CDSE for a Sentinel-1 GRD scene over an AOI and download it.

Needs CDSE_USER and CDSE_PASSWORD in the environment. Free — register at
https://dataspace.copernicus.eu.

    python scripts/fetch/sentinel1.py \
        --bbox 71.4,19.0,72.1,19.7 \
        --start 2026-03-01T00:00:00Z --end 2026-03-20T00:00:00Z \
        --out data/scenes/s1_arabian

IMPORTANT — read before assuming the output drops straight into the pipeline:

CDSE ships GRD two ways, and NEITHER is a calibrated single-band dB GeoTIFF:

  * the per-polarisation COG assets ("vv"/"vh") are hosted on s3://eodata/...
    and are in raw digital numbers (DN), not sigma-nought;
  * the "Product" asset is the full ~1 GB .SAFE zip (also raw DN inside).

`sagar.data.loaders.load_geotiff` reads a band and treats it AS sigma0 dB. Raw
DN is not dB, so the detector's dB-tuned thresholds and the classifier (trained
on simulated dB scenes) will misbehave on uncalibrated input. Getting from GRD
DN to sigma0 dB needs radiometric calibration (the calibration LUT in the
product, or a tool like SNAP/`pyroSAR`/`sarsen`). That step is not in this repo.

So this script's honest job is: search the correct catalogue, show what's
available, and fetch the raw product. Calibration to dB is a separate step.

For an analysis-ready, ALREADY-CALIBRATED dB COG over plain HTTPS with no SNAP,
Microsoft Planetary Computer's `sentinel-1-rtc` / `sentinel-1-grd` is the
pragmatic route — ask and a fetcher for it can be added.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


# The old catalogue.dataspace.copernicus.eu/stac endpoint was retired — it now
# only carries CLMS/CCM collections and 400s on "SENTINEL-1". This is the live one.
STAC = "https://stac.dataspace.copernicus.eu/v1"
TOKEN_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
             "protocol/openid-connect/token")
EODATA_GW = "https://eodata.dataspace.copernicus.eu/"


def token():
    user, pw = os.environ.get("CDSE_USER"), os.environ.get("CDSE_PASSWORD")
    if not (user and pw):
        sys.exit("CDSE_USER / CDSE_PASSWORD not set — run: set -a; source .env; set +a")
    body = urllib.parse.urlencode({
        "client_id": "cdse-public",
        "grant_type": "password",
        "username": user, "password": pw}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def search(bbox, start, end, collection="sentinel-1-grd", limit=10):
    """STAC search. bbox = (west, south, east, north)."""
    q = {"collections": [collection], "bbox": list(bbox),
         "datetime": f"{start}/{end}", "limit": limit}
    req = urllib.request.Request(f"{STAC}/search",
        data=json.dumps(q).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def download(url, out, tok):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=600) as r, open(out, "wb") as f:
        got = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            got += len(b)
            print(f"\r  {got/1e6:.0f} MB", end="", flush=True)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="west,south,east,north")
    ap.add_argument("--start", required=True, help="ISO, e.g. 2026-03-01T00:00:00Z")
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True, help="output path prefix (no extension)")
    ap.add_argument("--which", choices=["product", "list"], default="list",
                     help="'list' (default) just prints matches; 'product' downloads "
                          "the full ~1 GB .SAFE zip")
    a = ap.parse_args()
    bbox = tuple(float(x) for x in a.bbox.split(","))

    print(f"Searching sentinel-1-grd over {bbox} ...")
    res = search(bbox, a.start, a.end)
    feats = res.get("features", [])
    if not feats:
        sys.exit("no Sentinel-1 GRD scene in that bbox/window — widen --start/--end")

    print(f"{len(feats)} scene(s):")
    for i, f in enumerate(feats):
        p = f["properties"]
        print(f"  [{i}] {f['id']}")
        print(f"       {p.get('datetime')}  orbit={p.get('sat:orbit_state','?')}")

    feat = feats[0]
    assets = feat.get("assets", {})
    vv = assets.get("vv", {}).get("href", "")
    vv_https = vv.replace("s3://eodata/", EODATA_GW) if vv.startswith("s3://") else vv

    print("\nTop scene assets:")
    print(f"  VV COG (raw DN, s3):   {vv}")
    if vv_https:
        print(f"  VV COG via HTTPS gw:   {vv_https}")
    print(f"  Product (.SAFE zip):   {assets.get('Product',{}).get('href','—')}")

    if a.which == "list":
        print("\nList-only (default). This is NOT yet a calibrated dB GeoTIFF — see the")
        print("module docstring. Re-run with --which product to pull the full .SAFE,")
        print("or ask for the Microsoft Planetary Computer fetcher for analysis-ready dB.")
        return

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    out = a.out + ".zip"
    print(f"\nFetching token ...")
    tok = token()
    href = assets.get("Product", {}).get("href")
    if not href:
        sys.exit("no Product asset on this scene")
    print(f"Downloading .SAFE product -> {out}  (this is ~1 GB)")
    download(href, out, tok)
    print(f"wrote {os.path.getsize(out)/1e6:.0f} MB")
    print("\nNext: unzip, then calibrate the VV measurement TIFF to sigma0 dB "
          "before load_geotiff — this repo does not do that step yet.")


if __name__ == "__main__":
    main()
