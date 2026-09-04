"""Collect LIVE AIS from aisstream.io for an AOI and write a MarineCadastre-style
CSV that `sagar.core.ais.load_csv` reads.

aisstream.io is a real-time WebSocket feed — it has NO history. You get the
vessels transmitting *right now* inside your bounding box, for as long as you
listen. Two consequences:

  * Run it for a few minutes so moving vessels build up a track (>=2 pings each),
    otherwise attribution behaviour features (speed drop, course change) are weak.
  * The AIS you collect is stamped with the current time. For attribution to line
    up, the SAR scene must be from the SAME period. Attributing live AIS against
    a 2024 archive Sentinel-1 scene will NOT time-align — use a very recent
    scene (last day or two) if you want a genuine live end-to-end demo.

COVERAGE WARNING (measured 2026-09): aisstream is crowdsourced from volunteer
land-based receivers. Coverage is dense near US/European coasts but ~ZERO over
the Indian coast / Arabian Sea. A world-box test pulled 2400+ msgs in 25 s;
the entire India coast (8-24N, 68-90E) returned 0 ships in 25 s. So for an
Arabian Sea AOI, live aisstream will give you nothing — use synthetic AIS
(sagar.core.ais.synthesize) or a historical MarineCadastre CSV instead. Live
aisstream only makes sense over a well-covered coast.

Needs AISSTREAM_KEY in the environment (free key at https://aisstream.io).

    export AISSTREAM_KEY=...            # or put it in .env and: set -a; source .env; set +a
    python scripts/fetch/aisstream.py \
        --bbox 71.4,19.0,72.1,19.7 --minutes 5 --out data/ais/live.csv

bbox is west,south,east,north (same order as every other fetch script here).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import json
import os
import sys


def _decode(raw):
    """aisstream frames may be plain-text JSON or gzip/zlib-compressed bytes
    (the SubscriptionConfirmation advertises CompressionEnabled). Try text
    first, then decompress. Returns a dict, or None if it can't be parsed."""
    import gzip, zlib
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return None
    # bytes: maybe already JSON, else gzip, else raw-deflate
    for attempt in (
        lambda b: b,
        lambda b: gzip.decompress(b),
        lambda b: zlib.decompress(b),
        lambda b: zlib.decompress(b, -zlib.MAX_WBITS),
    ):
        try:
            return json.loads(attempt(raw))
        except Exception:
            continue
    return None


async def collect(key, bbox, minutes, out):
    import websockets
    w, s, e, n = bbox
    n_binary = 0
    # aisstream wants [[ [lat_min, lon_min], [lat_max, lon_max] ]] — note lat,lon order.
    sub = {
        "APIKey": key,
        "BoundingBoxes": [[[s, w], [n, e]]],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }
    pos = {}     # mmsi -> list of (ts, lat, lon, sog, cog)
    static = {}  # mmsi -> dict(name, vtype, length, draft)
    deadline = None

    print(f"connecting to aisstream.io, listening {minutes} min over "
          f"[{w},{s},{e},{n}] ...")
    n_msgs = 0
    try:
        ws = await websockets.connect("wss://stream.aisstream.io/v0/stream",
                                      ping_interval=20, max_size=None)
    except Exception as e:
        print(f"could not connect: {e}")
        return pos, static
    try:
        await ws.send(json.dumps(sub))
        loop = asyncio.get_event_loop()
        deadline = loop.time() + minutes * 60
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=deadline - loop.time())
            except asyncio.TimeoutError:
                break
            except websockets.ConnectionClosed:
                # Bad key or server drop — aisstream closes without a frame.
                print("\n  connection closed by server (bad key, or dropped mid-stream)")
                break
            msg = _decode(raw)
            if msg is None:
                n_binary += 1
                continue
            n_msgs += 1
            # aisstream reports problems as a plain {"error": "..."} / {"message": ...}
            # object with no MetaData — surface it instead of silently dropping it.
            if isinstance(msg, dict) and ("error" in msg or "Error" in msg or
                                          msg.get("MessageType") == "Error"):
                print(f"\n  aisstream said: {json.dumps(msg)[:300]}")
                break
            meta = msg.get("MetaData", {})
            mmsi = str(meta.get("MMSI", "")).strip()
            if not mmsi:
                if n_msgs <= 2:   # show the first stray message for debugging
                    print(f"\n  first message (no MMSI): {json.dumps(msg)[:300]}")
                continue
            mtype = msg.get("MessageType")
            body = msg.get("Message", {}).get(mtype, {})
            if mtype == "PositionReport":
                ts = meta.get("time_utc", "")[:19].replace(" ", "T") or \
                     dt.datetime.utcnow().isoformat(timespec="seconds")
                lat = body.get("Latitude", meta.get("latitude"))
                lon = body.get("Longitude", meta.get("longitude"))
                if lat is None or lon is None:
                    continue
                pos.setdefault(mmsi, []).append(
                    (ts, lat, lon, body.get("Sog", 0.0), body.get("Cog", 0.0)))
            elif mtype == "ShipStaticData":
                d = body.get("Dimension", {}) or {}
                static[mmsi] = dict(
                    name=(body.get("Name") or meta.get("ShipName") or f"MMSI {mmsi}").strip(),
                    vtype=int(body.get("Type", 0) or 0),
                    length=float((d.get("A", 0) or 0) + (d.get("B", 0) or 0)),
                    draft=float(body.get("MaximumStaticDraught", 0) or 0))
            if n_msgs % 200 == 0:
                print(f"\r  {n_msgs} msgs, {len(pos)} vessels ...", end="", flush=True)
    finally:
        await ws.close()
    print(f"\n  collected {n_msgs} JSON messages ({n_binary} undecodable binary), "
          f"{len(pos)} vessels with positions")
    return pos, static


def write_csv(pos, static, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    rows = 0
    with open(out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading",
                     "VesselName", "IMO", "CallSign", "VesselType", "Status",
                     "Length", "Width", "Draft", "Cargo"])
        for mmsi, pings in pos.items():
            st = static.get(mmsi, {})
            length = st.get("length", 0.0)
            for ts, lat, lon, sog, cog in pings:
                wr.writerow([mmsi, ts, f"{lat:.6f}", f"{lon:.6f}",
                             f"{sog:.1f}", f"{cog:.1f}", f"{cog:.0f}",
                             st.get("name", f"MMSI {mmsi}"), "", "",
                             st.get("vtype", 0), 0, f"{length:.0f}",
                             f"{length/7:.0f}", f"{st.get('draft',0.0):.1f}", ""])
                rows += 1
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="west,south,east,north")
    ap.add_argument("--minutes", type=float, default=5.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    key = os.environ.get("AISSTREAM_KEY") or os.environ.get("AISSTREAM_API_KEY")
    if not key:
        sys.exit("AISSTREAM_KEY not set — add it to .env then: set -a; source .env; set +a")
    bbox = tuple(float(x) for x in a.bbox.split(","))

    pos, static = asyncio.run(collect(key, bbox, a.minutes, a.out))
    if not pos:
        sys.exit("no AIS received — check the key, the bbox (is it over water with "
                 "traffic?), and that --minutes was long enough")
    rows = write_csv(pos, static, a.out)
    multi = sum(1 for p in pos.values() if len(p) >= 2)
    print(f"wrote {a.out}  ({rows} pings, {len(pos)} vessels, "
          f"{multi} with >=2 pings usable for behaviour)")


if __name__ == "__main__":
    main()
