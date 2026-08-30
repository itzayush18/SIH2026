"""Snapshot the running OILTRACE server into a fully static site.

GitHub Pages is static-only, so we bake every API response the frontend uses
into a matching JSON file under `site/`. The frontend already tries `/api/...`
first and falls back to `./api/....json`- that fallback is what runs on Pages.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def snap(client, path, out_path):
    r = client.get(path, timeout=30.0)
    r.raise_for_status()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "wb").write(r.content)


def snap_pdf(client, path, out_path):
    r = client.get(path, timeout=60.0)
    if r.status_code != 200: return
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "wb").write(r.content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default="site")
    a = ap.parse_args()

    with httpx.Client(base_url=a.base) as c:
        r = c.get("/health"); r.raise_for_status()

        # frontend (Vite + React + Tailwind- white / light-grey / Outfit)
        os.makedirs(a.out, exist_ok=True)
        _FRONTEND_INDEX = os.path.join("frontend", "dist", "index.html")
        _FALLBACK_INDEX = os.path.join("frontend", "index.html")
        if os.path.exists(_FRONTEND_INDEX):
            shutil.copy(_FRONTEND_INDEX, os.path.join(a.out, "index.html"))
            # also copy vite assets
            _ASSETS_SRC = os.path.join("frontend", "dist", "assets")
            if os.path.isdir(_ASSETS_SRC):
                shutil.copytree(_ASSETS_SRC, os.path.join(a.out, "assets"), dirs_exist_ok=True)
        elif os.path.exists(_FALLBACK_INDEX):
            shutil.copy(_FALLBACK_INDEX, os.path.join(a.out, "index.html"))
        else:
            raise FileNotFoundError("frontend/dist/index.html not found- run `npm run build` in frontend/ first")

        # top-level snapshots
        snap(c, "/api/system/status",    f"{a.out}/api/system/status.json")
        snap(c, "/api/scenarios",        f"{a.out}/api/scenarios.json")
        snap(c, "/api/incidents",        f"{a.out}/api/incidents.json")
        snap(c, "/api/jurisdictions.geojson", f"{a.out}/api/jurisdictions.geojson")
        snap(c, "/api/coast.geojson",    f"{a.out}/api/coast.geojson")
        snap(c, "/api/analytics/overview", f"{a.out}/api/analytics/overview.json")

        inc = c.get("/api/incidents").json()["incidents"]
        for i in inc:
            iid = i["incident_id"]
            base = f"/api/incidents/{iid}"
            snap(c, base,                 f"{a.out}{base}.json")
            snap(c, base + "/candidates", f"{a.out}{base}/candidates.json")
            snap(c, base + "/alerts",     f"{a.out}{base}/alerts.json")
            snap(c, base + "/patrol",     f"{a.out}{base}/patrol.json")
            snap(c, base + "/evidence",   f"{a.out}{base}/evidence.json")
            snap(c, base + "/timeline",   f"{a.out}{base}/timeline.json")
            snap_pdf(c, base + "/evidence.pdf", f"{a.out}{base}/evidence.pdf")

            # copy incident asset dir (SAR, slick, origin slices, evidence pack)
            src = f"data/out/{iid}"
            dst = f"{a.out}/incidents/{iid}"
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)

        # vectors: snapshot the arabian-tanker scene bbox at t=0
        first = inc[0]["incident_id"]
        rep = c.get(f"/api/incidents/{first}").json()["report"]
        b = rep["scene"]["bounds"]
        q = f"south={b[0][0]}&west={b[0][1]}&north={b[1][0]}&east={b[1][1]}&t_rel_h=0&n=20"
        snap(c, "/api/environment/vectors?" + q,
             f"{a.out}/api/environment/vectors.json")

        # vessel lookups (one per suspect for the first three incidents)
        seen = set()
        for i in inc[:3]:
            for s in c.get(f"/api/incidents/{i['incident_id']}/candidates").json()["candidates"][:3]:
                if s["mmsi"] in seen: continue
                seen.add(s["mmsi"])
                snap(c, f"/api/vessels/{s['mmsi']}",
                     f"{a.out}/api/vessels/{s['mmsi']}.json")

    # A marker file the frontend probes to detect static mode.
    with open(f"{a.out}/api/STATIC.json", "w") as f:
        json.dump({"mode": "STATIC_SNAPSHOT",
                   "note": "Live pipeline runs disabled- this is a snapshot of a "
                           "server run. Clone the repo and `python -m oiltrace.server` "
                           "to try new scenarios interactively."}, f)

    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(a.out) for f in fs)
    print(f"\n  site/ = {total/1e6:.1f} MB in {a.out}/")


if __name__ == "__main__":
    main()
