"""Pull recent AIS from AISHub and normalise to the MarineCadastre CSV schema
`sagar.core.ais.load_csv` expects.

Needs AISHUB_USER in the environment (free registration at aishub.net).

    python scripts/fetch/aishub.py --bbox 68,15,75,22 --out data/ais/aishub.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="west,south,east,north")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    user = os.environ.get("AISHUB_USER")
    if not user:
        sys.exit("AISHUB_USER not set")
    w, s, e, n = (float(x) for x in a.bbox.split(","))
    q = urllib.parse.urlencode(dict(username=user, format=1, output="json",
        compress=0, latmin=s, latmax=n, lonmin=w, lonmax=e))
    url = f"http://data.aishub.net/ws.php?{q}"
    print(f"GET {url}")
    with urllib.request.urlopen(url, timeout=45) as r:
        data = json.load(r)
    if data and isinstance(data, list) and data[0].get("ERROR"):
        sys.exit(f"AISHub: {data[0]['ERROR_MESSAGE']}")

    rows = data[1] if len(data) > 1 else []
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w2 = csv.writer(f)
        w2.writerow(["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG",
                     "Heading", "VesselName", "IMO", "CallSign", "VesselType",
                     "Status", "Length", "Width", "Draft", "Cargo"])
        for r_ in rows:
            ts = dt.datetime.fromtimestamp(int(r_.get("TIME", 0)),
                                           tz=dt.timezone.utc).isoformat()
            w2.writerow([r_.get("MMSI", ""), ts,
                         f"{float(r_.get('LATITUDE', 0)):.6f}",
                         f"{float(r_.get('LONGITUDE', 0)):.6f}",
                         r_.get("SOG", 0), r_.get("COG", 0),
                         r_.get("HEADING", 0), r_.get("NAME", ""),
                         r_.get("IMO", ""), r_.get("CALLSIGN", ""),
                         r_.get("TYPE", 0), r_.get("NAVSTAT", 0),
                         r_.get("A", 0) + r_.get("B", 0),
                         r_.get("C", 0) + r_.get("D", 0),
                         r_.get("DRAUGHT", 0), ""])
    print(f"wrote {len(rows)} pings to {a.out}")


if __name__ == "__main__":
    main()
