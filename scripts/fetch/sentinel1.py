"""Query CDSE STAC for a Sentinel-1 GRD scene and download the VV/VH band.

Needs CDSE_USER and CDSE_PASSWORD in the environment. Free — register at
https://dataspace.copernicus.eu.

    python scripts/fetch/sentinel1.py \
        --bbox 71.4,19.0,72.1,19.7 \
        --start 2026-03-13T00:00 --end 2026-03-15T00:00 \
        --out data/scenes/s1_arabian.tif

Once downloaded, wire it into the pipeline by pointing
`sagar.data.loaders.load_geotiff(<path>, ...)` at the file and passing the
resulting Scene to `sagar.core.detect.detect(scene)`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


STAC = "https://catalogue.dataspace.copernicus.eu/stac"
TOKEN_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
             "protocol/openid-connect/token")


def token():
    user, pw = os.environ.get("CDSE_USER"), os.environ.get("CDSE_PASSWORD")
    if not (user and pw):
        sys.exit("CDSE_USER / CDSE_PASSWORD not set — see .env.example")
    body = urllib.parse.urlencode({
        "client_id": "cdse-public",
        "grant_type": "password",
        "username": user, "password": pw}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def search(bbox, start, end, product="IW_GRDH_1S"):
    """Query STAC. bbox = (west, south, east, north)."""
    q = {"collections": ["SENTINEL-1"], "bbox": list(bbox),
         "datetime": f"{start}/{end}", "limit": 10,
         "query": {"productType": {"eq": product}}}
    req = urllib.request.Request(f"{STAC}/search",
        data=json.dumps(q).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def download(url, out, tok):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=180) as r, open(out, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="west,south,east,north")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bbox = tuple(float(x) for x in a.bbox.split(","))

    print("Querying CDSE STAC ...")
    res = search(bbox, a.start, a.end)
    if not res.get("features"):
        sys.exit("no matching Sentinel-1 GRD found in that bbox/window")
    feat = res["features"][0]
    print(f"  scene: {feat['id']}")
    # Preferred: the GRD product asset. Fall back to the first asset.
    assets = feat.get("assets", {})
    href = None
    for k in ("PRODUCT", "SAFE", "s1-grd", "measurement", "product"):
        if k in assets:
            href = assets[k].get("href"); break
    if not href:
        href = next(iter(assets.values()))["href"]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    print("Fetching token ...")
    tok = token()
    print(f"Downloading {href} -> {a.out}")
    download(href, a.out, tok)
    print(f"wrote {os.path.getsize(a.out)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
