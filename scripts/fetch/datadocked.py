"""Fetch real AIS from Data Docked (https://datadocked.com) and write a
MarineCadastre-style CSV that `sagar.core.ais.load_csv` reads.

Why this matters: Data Docked is satellite+terrestrial AIS with GLOBAL coverage
INCLUDING Indian waters — the exact gap aisstream has. So this is the way to get
real vessels for an Arabian Sea / Bay of Bengal incident.

Credits: this is a paid, credit-metered API (free tier ~20 credits).
  * area snapshot   (get-vessels-by-area)      = 10 credits / call
  * historical track (get-vessel-historical-data) = 5 credits / vessel
So the default is ONE area call (a snapshot: one position per vessel). Use
--history to additionally pull real tracks for the top-N nearest vessels (needed
for strong attribution, but burns 5 credits each — only ~2 years back, so no 2017).

Needs DATADOCKED_KEY in the environment (add to .env, then: set -a; source .env; set +a).

    # snapshot of vessels around the Ennore AOI -> CSV
    python scripts/fetch/datadocked.py --bbox 80.0,12.8,80.6,13.5 \
        --epoch 2026-09-02T00:00:00 --out data/ais/ennore_dd.csv

    # ...plus real tracks for the 6 nearest vessels over a window (costs credits)
    python scripts/fetch/datadocked.py --bbox 80.0,12.8,80.6,13.5 \
        --epoch 2026-09-02T00:00:00 --out data/ais/ennore_dd.csv \
        --history --from 2026-08-31T00:00:00 --to 2026-09-02T00:00:00 --history-top 6
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _http import http_json as _http_json

BASE = "https://datadocked.com/api/vessels_operations"

# Data Docked returns a free-text `typeSpecific`; map the common ones to the
# numeric AIS ship-type codes sagar's vessel-prior expects (0 = unknown).
_TYPE_CODES = {
    "tanker": 80, "oil": 80, "cargo": 70, "bulk": 70, "container": 70,
    "fishing": 30, "tug": 52, "passenger": 60, "ferry": 60, "pleasure": 37,
}


def _type_code(s):
    s = (s or "").lower()
    for k, v in _TYPE_CODES.items():
        if k in s:
            return v
    return 0


def _get(path, params, key, tries=4):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    return _http_json(url, {"x-api-key": key}, tries=tries, label="Data Docked")


def bbox_center_radius_km(w, s, e, n):
    lat = (s + n) / 2.0
    lon = (w + e) / 2.0
    # half the diagonal, in km — covers the whole bbox from the centre
    R = 6371.0
    dlat = math.radians(n - s)
    dlon = math.radians(e - w) * math.cos(math.radians(lat))
    diag_km = R * math.hypot(dlat, dlon)
    return lat, lon, max(1, int(math.ceil(diag_km / 2.0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", help="west,south,east,north (converted to centre+radius)")
    ap.add_argument("--center", help="lat,lon (alternative to --bbox)")
    ap.add_argument("--radius", type=int, default=None,
                     help="circle_radius for the area query (API units); "
                          "default = half the bbox diagonal in km")
    ap.add_argument("--epoch", default=None,
                     help="timestamp to stamp the snapshot with (ISO); default: now UTC")
    ap.add_argument("--out", required=True)
    ap.add_argument("--history", action="store_true",
                     help="also pull real historical tracks for the nearest vessels (5 credits each)")
    ap.add_argument("--from", dest="from_date", help="history window start, ISO")
    ap.add_argument("--to", dest="to_date", help="history window end, ISO")
    ap.add_argument("--history-top", type=int, default=6)
    a = ap.parse_args()

    key = os.environ.get("DATADOCKED_KEY") or os.environ.get("DATADOCKED_API_KEY")
    if not key:
        sys.exit("DATADOCKED_KEY not set — add it to .env then: set -a; source .env; set +a")

    if a.bbox:
        w, s, e, n = (float(x) for x in a.bbox.split(","))
        lat, lon, rad = bbox_center_radius_km(w, s, e, n)
    elif a.center:
        lat, lon = (float(x) for x in a.center.split(","))
        rad = a.radius or 50
    else:
        sys.exit("give --bbox or --center")
    if a.radius:
        rad = a.radius
    epoch = a.epoch or dt.datetime.utcnow().replace(microsecond=0).isoformat()

    print(f"get-vessels-by-area  lat={lat:.4f} lon={lon:.4f} radius={rad}  (10 credits) ...")
    js = _get("get-vessels-by-area",
              {"latitude": lat, "longitude": lon, "circle_radius": rad}, key)
    vessels = js.get("vessels") or js.get("data") or []
    print(f"  {len(vessels)} vessel(s) in area")
    if not vessels:
        sys.exit("no vessels returned — widen --radius, check coverage, or credits")

    rows = []   # (mmsi, iso_time, lat, lon, sog, cog, name, vtype, length)
    for v in vessels:
        mmsi = str(v.get("mmsi", "")).strip()
        if not mmsi:
            continue
        rows.append((mmsi, epoch, v.get("latitude"), v.get("longitude"),
                     v.get("speed", 0) or 0, v.get("course", 0) or 0,
                     v.get("name") or f"MMSI {mmsi}", _type_code(v.get("typeSpecific")), 0))

    if a.history:
        if not (a.from_date and a.to_date):
            sys.exit("--history needs --from and --to")
        # nearest vessels to the AOI centre first
        def d2(v):
            la = v.get("latitude") or lat; lo = v.get("longitude") or lon
            return (la - lat) ** 2 + (lo - lon) ** 2
        for v in sorted(vessels, key=d2)[:a.history_top]:
            mmsi = str(v.get("mmsi", "")).strip()
            if not mmsi:
                continue
            print(f"get-vessel-historical-data  mmsi={mmsi}  (5 credits) ...")
            h = _get("get-vessel-historical-data",
                     {"imo_or_mmsi": mmsi, "from_date": a.from_date, "to_date": a.to_date}, key)
            track = h.get("data") or []
            name = v.get("name") or f"MMSI {mmsi}"
            vt = _type_code(v.get("typeSpecific"))
            for p in track:
                t = p.get("time")
                if t is None:
                    continue
                # normalise epoch-seconds or ISO to ISO
                iso = (dt.datetime.utcfromtimestamp(t).isoformat()
                       if isinstance(t, (int, float)) else str(t)[:19].replace(" ", "T"))
                rows.append((mmsi, iso, p.get("lat"), p.get("lng"),
                             p.get("speed", 0) or 0, p.get("course", 0) or 0, name, vt, 0))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading",
                     "VesselName", "IMO", "CallSign", "VesselType", "Status",
                     "Length", "Width", "Draft", "Cargo"])
        n = 0
        for mmsi, t, la, lo, sog, cog, name, vt, length in rows:
            if la is None or lo is None:
                continue
            wr.writerow([mmsi, t, f"{float(la):.6f}", f"{float(lo):.6f}",
                         f"{float(sog):.1f}", f"{float(cog):.1f}", f"{float(cog):.0f}",
                         name, "", "", vt, 0, length, 0, 0, ""])
            n += 1
    multi = {}
    for r in rows:
        multi[r[0]] = multi.get(r[0], 0) + 1
    with_track = sum(1 for c in multi.values() if c >= 2)
    print(f"wrote {a.out}  ({n} pings, {len(multi)} vessels, {with_track} with tracks)")
    if not a.history:
        print("snapshot only (1 ping/vessel). For attribution that uses vessel "
              "tracks, re-run with --history --from --to (costs credits).")


if __name__ == "__main__":
    main()
