"""Fetch real AIS from VesselAPI (https://vesselapi.com) and write a
MarineCadastre-style CSV that `sagar.core.ais.load_csv` reads.

VesselAPI: global REST AIS (incl. Indian waters), Bearer-auth, generous free
tier (150 requests/month). Snapshot-style — one current position per vessel in
the area (good for real ships on the map + proximity attribution; it has no
historical position-track endpoint, so for vessel tracks use datadocked --history).

    base: https://api.vesselapi.com/v1
    auth: Authorization: Bearer <VESSELAPI_KEY>
    bbox: GET /v1/location/vessels/bounding-box
          ?filter.lonLeft&filter.lonRight&filter.latBottom&filter.latTop  (<=4 deg span)
    radius: GET /v1/location/vessels/radius
          ?filter.longitude&filter.latitude&filter.radius  (<=100 km)

Needs VESSELAPI_KEY in the environment (add to .env, then: set -a; source .env; set +a).

    python scripts/fetch/vesselapi.py --bbox 80.0,12.8,80.6,13.5 \
        --epoch 2026-09-02T00:00:00 --out data/ais/vapi.csv

The per-vessel position field names aren't fully documented, so parsing is
tolerant (tries latitude/lat, longitude/lon/lng, speed/sog, course/cog). Run
once with --raw to print the first raw vessel object if anything looks off.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _http import http_json as _http_json

BASE = "https://api.vesselapi.com/v1"

_TYPE_CODES = {"tanker": 80, "oil": 80, "cargo": 70, "bulk": 70, "container": 70,
               "fishing": 30, "tug": 52, "passenger": 60, "ferry": 60, "pleasure": 37}


def _pick(d, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _type_code(s):
    s = str(s or "").lower()
    for k, v in _TYPE_CODES.items():
        if k in s:
            return v
    return 0


def _get(path, params, key, tries=4):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    return _http_json(url, {"Authorization": f"Bearer {key}"}, tries=tries, label="VesselAPI")


def snapshot(w, s, e, n, key):
    """Reusable: return normalized ship dicts for a bbox. Used by the server's
    /api/ais/snapshot endpoint as well as the CLI."""
    js = _get("location/vessels/bounding-box",
              {"filter.lonLeft": w, "filter.lonRight": e,
               "filter.latBottom": s, "filter.latTop": n}, key)
    vessels = js.get("vessels") or js.get("data") or (js if isinstance(js, list) else [])
    out = []
    for v in vessels:
        if not isinstance(v, dict):
            continue
        mmsi = str(_pick(v, "mmsi", "MMSI", default="")).strip()
        lat = _pick(v, "latitude", "lat", "Latitude")
        lon = _pick(v, "longitude", "lon", "lng", "Longitude")
        if not mmsi or lat is None or lon is None:
            continue
        out.append(dict(mmsi=mmsi, lat=float(lat), lon=float(lon),
                        sog=float(_pick(v, "speed", "sog", "Speed", default=0) or 0),
                        cog=float(_pick(v, "course", "cog", "Course", default=0) or 0),
                        name=str(_pick(v, "name", "Name", default=f"MMSI {mmsi}"))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", help="west,south,east,north (<=4 deg span)")
    ap.add_argument("--center", help="lat,lon (uses radius endpoint)")
    ap.add_argument("--radius", type=int, default=80, help="km for --center (<=100)")
    ap.add_argument("--epoch", default=None, help="ISO timestamp to stamp the snapshot; default now")
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw", action="store_true", help="print the first raw vessel object and exit")
    a = ap.parse_args()

    key = os.environ.get("VESSELAPI_KEY") or os.environ.get("VESSEL_API_KEY")
    if not key:
        sys.exit("VESSELAPI_KEY not set — add it to .env then: set -a; source .env; set +a")

    if a.bbox:
        w, s, e, n = (float(x) for x in a.bbox.split(","))
        print(f"bounding-box lonLeft={w} lonRight={e} latBottom={s} latTop={n} ...")
        js = _get("location/vessels/bounding-box",
                  {"filter.lonLeft": w, "filter.lonRight": e,
                   "filter.latBottom": s, "filter.latTop": n}, key)
    elif a.center:
        lat, lon = (float(x) for x in a.center.split(","))
        print(f"radius lat={lat} lon={lon} r={a.radius}km ...")
        js = _get("location/vessels/radius",
                  {"filter.latitude": lat, "filter.longitude": lon,
                   "filter.radius": a.radius}, key)
    else:
        sys.exit("give --bbox or --center")

    vessels = js.get("vessels") or js.get("data") or (js if isinstance(js, list) else [])
    if a.raw:
        print(json.dumps(vessels[0] if vessels else js, indent=2)[:1500]); return
    print(f"  {len(vessels)} vessel(s)")
    if not vessels:
        sys.exit("no vessels returned — check the key, the bbox, or your quota")

    epoch = a.epoch or dt.datetime.utcnow().replace(microsecond=0).isoformat()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    n = 0
    with open(a.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading",
                     "VesselName", "IMO", "CallSign", "VesselType", "Status",
                     "Length", "Width", "Draft", "Cargo"])
        for v in vessels:
            if not isinstance(v, dict):
                continue
            mmsi = str(_pick(v, "mmsi", "MMSI", default="")).strip()
            lat = _pick(v, "latitude", "lat", "Latitude")
            lon = _pick(v, "longitude", "lon", "lng", "Longitude")
            if not mmsi or lat is None or lon is None:
                continue
            sog = _pick(v, "speed", "sog", "Speed", default=0) or 0
            cog = _pick(v, "course", "cog", "Course", default=0) or 0
            name = _pick(v, "name", "Name", default=f"MMSI {mmsi}")
            vt = _type_code(_pick(v, "typeSpecific", "type", "shipType"))
            length = _pick(v, "length", "Length", default=0) or 0
            wr.writerow([mmsi, epoch, f"{float(lat):.6f}", f"{float(lon):.6f}",
                         f"{float(sog):.1f}", f"{float(cog):.1f}", f"{float(cog):.0f}",
                         name, "", "", vt, 0, length, 0, 0, ""])
            n += 1
    print(f"wrote {a.out}  ({n} vessels, 1 ping each)")
    if n == 0:
        print("0 usable rows — run with --raw to see the actual field names and tell me.")


if __name__ == "__main__":
    main()
