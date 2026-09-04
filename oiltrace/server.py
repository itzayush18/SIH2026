"""OILTRACE backend- spec §32, §45.

Modular monolith on FastAPI. One process, clean service boundaries, endpoints
that match the spec verbatim so a downstream React/TS frontend could pull them
without any adapter. WebSockets replaced with SSE for the same reason we don't
require Redis: the demo has to run on a laptop in an air-gapped hall.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from oiltrace import incidents as _inc, providers as _prov
from oiltrace.scenarios import SCENARIOS
from oiltrace.jurisdictions import classify
from oiltrace import coast as _coast
from oiltrace import notify as _notify, pdf as _pdf, vectors as _vec
from oiltrace import impact as _impact, investigator as _inv
from oiltrace import rescore as _rescore, whatif as _whatif

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "out")
# Vite + React + Tailwind frontend (white / light-grey / Outfit)
# Production build: frontend/dist  |  Dev: `npm run dev` in frontend/ proxied to :8000
_FRONTEND_DIST = os.path.join(ROOT, "frontend", "dist")
_FRONTEND_SRC = os.path.join(ROOT, "frontend")
if os.path.isdir(_FRONTEND_DIST):
    WEB = _FRONTEND_DIST
elif os.path.isdir(_FRONTEND_SRC):
    # fallback for local dev without a build (serve source index.html via vite proxy- FastAPI just needs a folder)
    WEB = _FRONTEND_SRC
else:
    WEB = _FRONTEND_DIST  # will error visibly if neither exists- run `npm run build` in frontend/


class Store:
    """In-process incident registry. Redis would be the drop-in for a cluster."""
    def __init__(self):
        self.incidents = {}   # incident_id -> report
        # Analyst decisions, append-only: (incident_id, mmsi) -> list of entries.
        # Append-only because the audit trail is the product- an analyst who
        # changes their mind adds a decision, they do not erase the earlier one.
        self.decisions = {}

    def put(self, rep):
        self.incidents[rep["oiltrace"]["incident_id"]] = rep

    def get(self, iid):
        return self.incidents.get(iid)

    def list(self):
        return [_inc.summary(r) for r in self.incidents.values()]

    def decide(self, iid, mmsi, action, analyst, note=""):
        entry = dict(incident_id=iid, mmsi=mmsi, action=action,
                     analyst=analyst or "unattributed", note=note,
                     at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        self.decisions.setdefault((iid, mmsi), []).append(entry)
        return entry

    def decisions_for(self, iid):
        out = []
        for (i, _m), entries in self.decisions.items():
            if i == iid:
                out.extend(entries)
        return sorted(out, key=lambda e: e["at"])

    def latest_decision(self, iid, mmsi):
        entries = self.decisions.get((iid, mmsi))
        return entries[-1] if entries else None


STORE = Store()


def _sim_banner(payload, mode=None):
    """Wrap every response in a mode header- spec §56 and honest per-incident labelling.

    Every API response keeps a `_meta.data_mode` field. Never let a screen or export
    imply a probability/certainty where none is calibrated (NFR-10). The value is
    now per-incident where applicable:
      SIMULATION | SYNTHETIC_OVERLAY | REAL_IMAGERY_SYNTHETIC_AIS | REAL_IMAGERY_REAL_AIS

    If the payload already carries an oiltrace/report incident mode we honour it
    rather than collapsing everything to SIMULATION.
    """
    if isinstance(payload, dict):
        inferred = mode
        # Try to infer from payload structure
        if inferred is None:
            # Check common nests
            if "data_mode" in payload:
                inferred = payload["data_mode"]
            elif "oiltrace" in payload and isinstance(payload["oiltrace"], dict):
                inferred = payload["oiltrace"].get("data_mode")
            elif "report" in payload and isinstance(payload["report"], dict):
                ro = payload["report"].get("oiltrace", {}) if isinstance(payload["report"].get("oiltrace"), dict) else {}
                inferred = ro.get("data_mode") or payload["report"].get("data_mode")
            elif "incident" in payload and isinstance(payload["incident"], dict):
                inferred = payload["incident"].get("data_mode")
            elif "incidents" in payload and isinstance(payload["incidents"], list):
                modes = {i.get("data_mode") for i in payload["incidents"] if isinstance(i, dict) and i.get("data_mode")}
                if len(modes) == 1:
                    inferred = next(iter(modes))
                elif len(modes) > 1:
                    inferred = "MIXED"
        if inferred is None:
            inferred = "SIMULATION"
        # Canonicalise via providers (handles legacy MIXED etc.)
        try:
            from oiltrace.providers import canonical_mode as _canon
            inferred = _canon(inferred)
        except Exception:
            pass
        payload["_meta"] = dict(data_mode=inferred,
                                generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                           time.gmtime()))
    return payload


def build_app():
    app = FastAPI(title="OILTRACE", version="0.4.0",
                  description="Oil Spill Intelligence & Vessel Attribution Command Center- "
                              "SIH26143 · NTRO. This deployment is a SIMULATION.")

    # ---- system status ----------------------------------------------------
    @app.get("/api/system/status")
    def system_status():
        return _sim_banner(dict(sources=[s.dict() for s in _prov.registry()],
                                overview=_prov.overview(),
                                incidents=len(STORE.incidents)))

    @app.get("/api/scenarios")
    def list_scenarios():
        return _sim_banner(dict(scenarios=[
            dict(slug=s.slug, name=s.name, subtitle=s.subtitle,
                 difficulty=s.difficulty, story=s.story, tags=list(s.tags),
                 center=dict(lat=s.origin.lat, lon=s.origin.lon))
            for s in SCENARIOS]))

    # ---- incidents --------------------------------------------------------
    @app.get("/api/incidents")
    def list_incidents():
        return _sim_banner(dict(incidents=STORE.list()))

    @app.get("/api/incidents/{iid}")
    def get_incident(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(incident=_inc.summary(r), report=r),
                           mode=r.get("oiltrace", {}).get("data_mode") or r.get("data_mode"))

    @app.get("/api/incidents/{iid}/candidates")
    def get_candidates(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        # Attach any analyst decision so the console can show the machine's
        # verdict and the human's ruling side by side.
        cands = []
        for c in r["suspects"]:
            c = dict(c)
            d = STORE.latest_decision(iid, c.get("mmsi"))
            c["analyst_decision"] = d
            cands.append(c)
        return _sim_banner(dict(candidates=cands),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- analyst-in-the-loop ---------------------------------------------
    # The deck promises the analyst retains final authority (§ "Human Verified").
    # These endpoints are what make that true rather than decorative: the model
    # proposes a verdict, a named analyst accepts, rejects or escalates it, and
    # every ruling lands in an append-only ledger that ships with the evidence.

    @app.post("/api/incidents/{iid}/candidates/{mmsi}/decision")
    def decide_candidate(iid: str, mmsi: str, action: str,
                         analyst: str = "", note: str = ""):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        action = (action or "").strip().upper()
        if action not in ("ACCEPT", "REJECT", "ESCALATE"):
            raise HTTPException(422, "action must be ACCEPT, REJECT or ESCALATE")
        if not any(str(c.get("mmsi")) == str(mmsi) for c in r["suspects"]):
            raise HTTPException(404, "unknown candidate for this incident")
        entry = STORE.decide(iid, mmsi, action, analyst, note)
        return _sim_banner(dict(decision=entry),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    @app.get("/api/incidents/{iid}/decisions")
    def list_decisions(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(decisions=STORE.decisions_for(iid)),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    @app.get("/api/incidents/{iid}/evidence")
    def get_evidence(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(evidence=r["oiltrace"]["evidence_pack"],
                                provenance=r["oiltrace"]["provenance"]),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    @app.get("/api/incidents/{iid}/evidence/download")
    def download_evidence(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        path = os.path.join(OUT, iid, r["oiltrace"]["evidence_pack"]["json"])
        return FileResponse(path, media_type="application/json",
                            filename=f"{iid}.evidence.json")

    @app.get("/api/incidents/{iid}/alerts")
    def get_alerts(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(alerts=r["oiltrace"]["alerts"]),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    @app.get("/api/incidents/{iid}/patrol")
    def get_patrol(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(patrol=r["oiltrace"]["patrol"]),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- vessels ----------------------------------------------------------
    @app.get("/api/vessels/{mmsi}")
    def vessel(mmsi: str):
        for r in STORE.incidents.values():
            for v in r["vessels"]:
                if v["mmsi"] == mmsi:
                    return _sim_banner(dict(vessel=v,
                        associations=[dict(incident_id=r["oiltrace"]["incident_id"])]))
        raise HTTPException(404, "unknown MMSI")

    # ---- jurisdictions ----------------------------------------------------
    @app.get("/api/jurisdictions/at")
    def jur_at(lat: float, lon: float):
        j = classify(lat, lon)
        return _sim_banner(dict(name=j.name, kind=j.kind, sovereign=j.sovereign,
                                marpol_regime=j.marpol_regime, source=j.source))

    @app.get("/api/jurisdictions.geojson")
    def jur_all():
        with open(os.path.join(os.path.dirname(__file__), "data",
                               "jurisdictions.geojson")) as f:
            return JSONResponse(json.load(f))

    # ---- analytics --------------------------------------------------------
    @app.get("/api/analytics/overview")
    def analytics():
        recs = list(STORE.incidents.values())
        if not recs:
            return _sim_banner(dict(empty=True))
        n = len(recs)
        p_oil = sum(r["detections"][0]["p_oil"] for r in recs) / n
        area = sum(r["detections"][0]["area_km2"] for r in recs) / n
        by_sev = {}
        for r in recs:
            s = _inc.summary(r)["severity"]
            by_sev[s] = by_sev.get(s, 0) + 1
        by_jur = {}
        for r in recs:
            j = r["oiltrace"]["jurisdiction"]["name"]
            by_jur[j] = by_jur.get(j, 0) + 1
        cands = sum(1 for r in recs
                    for s in r["suspects"] if s["score"] > .45)
        return _sim_banner(dict(
            incidents=n, mean_p_oil=p_oil, mean_area_km2=area,
            candidate_vessels=cands,
            by_severity=by_sev, by_jurisdiction=by_jur,
            avg_inversion_error_km=sum(r["validation"]["inversion_error_km"] for r in recs) / n,
            attribution_correct_rate=sum(1 for r in recs
                                         if r["validation"]["attribution_correct"]) / n,
        ))

    # ---- analysis (run one) ----------------------------------------------
    @app.post("/api/analysis/run")
    def run_one(scenario: str = "arabian-tanker"):
        rep = _inc.run(scenario, OUT)
        STORE.put(rep)
        return _sim_banner(dict(incident=_inc.summary(rep)))

    @app.get("/api/analysis/run/stream")
    async def run_stream(scenario: str = "arabian-tanker"):
        q: queue.Queue = queue.Queue(); SENTINEL = object()

        def worker():
            try:
                rep = _inc.run(scenario, OUT,
                               on_stage=lambda n, d: q.put((n, d)))
                STORE.put(rep)
                q.put(("incident", _inc.summary(rep)))
            except Exception as e:
                q.put(("error", {"message": str(e)}))
            finally:
                q.put(SENTINEL)
        threading.Thread(target=worker, daemon=True).start()

        async def gen():
            loop = asyncio.get_running_loop()
            while True:
                item = await loop.run_in_executor(None, q.get)
                if item is SENTINEL: return
                name, data = item
                yield f"event: {name}\ndata: {json.dumps(data, default=float)}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    # ---- replay (a whole scenario set, one after another) ----------------
    @app.post("/api/replay/start")
    async def replay_start():
        q: queue.Queue = queue.Queue(); SENTINEL = object()

        def worker():
            try:
                for i, s in enumerate(SCENARIOS):
                    q.put(("scenario_start", {"slug": s.slug, "name": s.name,
                                              "index": i, "total": len(SCENARIOS)}))
                    rep = _inc.run(s.slug, OUT,
                                   on_stage=lambda n, d: q.put((n, d)))
                    STORE.put(rep)
                    q.put(("scenario_done", _inc.summary(rep)))
                q.put(("replay_done", {"n": len(SCENARIOS)}))
            except Exception as e:
                q.put(("error", {"message": str(e)}))
            finally:
                q.put(SENTINEL)
        threading.Thread(target=worker, daemon=True).start()

        async def gen():
            loop = asyncio.get_running_loop()
            while True:
                item = await loop.run_in_executor(None, q.get)
                if item is SENTINEL: return
                name, data = item
                yield f"event: {name}\ndata: {json.dumps(data, default=float)}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})


    @app.get("/api/coast.geojson")
    def coast():
        return JSONResponse(_coast.geojson())

    # ---- environment vectors (currents + wind) ----------------------------
    @app.get("/api/environment/vectors")
    def env_vectors(south: float, west: float, north: float, east: float,
                    t_rel_h: float = 0.0, n: int = 24):
        gj = _vec.sample([[south, west], [north, east]], t_rel_h=t_rel_h, n=n)
        return JSONResponse(gj)

    # ---- evidence PDF ------------------------------------------------------
    @app.get("/api/incidents/{iid}/evidence.pdf")
    def evidence_pdf(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        outdir = os.path.join(OUT, iid)
        path = _pdf.render(r, outdir)
        return FileResponse(path, media_type="application/pdf",
                            filename=f"{iid}.evidence.pdf")

    # ---- alerts fanout to configured channels -----------------------------
    @app.post("/api/incidents/{iid}/notify")
    def notify(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(dispatched=_notify.dispatch_critical(r)),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- MV Rak validation vignette (§4.4) ---------------------------------
    @app.get("/api/validation/mv-rak")
    def mv_rak():
        try:
            from sagar.data.mv_rak import vignette_result as _vr
            return _sim_banner(dict(vignette=_vr()), mode="SYNTHETIC_OVERLAY")
        except Exception as e:
            raise HTTPException(500, f"mv-rak vignette failed: {e}")

    # ---- dark vessels for an incident (§4.2) --------------------------------
    @app.get("/api/incidents/{iid}/dark-vessels")
    def dark_vessels(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(dark_vessels=r.get("dark_vessels", [])),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- INCOIS live probe (§4.5) -------------------------------------------
    @app.get("/api/live/incois")
    def incois_probe():
        try:
            from oiltrace.incois import probe as _probe
            return _sim_banner(dict(incois=_probe()))
        except Exception as e:
            return _sim_banner(dict(incois=dict(status="OFFLINE", error=str(e))))

    # ---- incident timeline (chronological event log) ----------------------
    @app.get("/api/incidents/{iid}/timeline")
    def timeline(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        import time as _t
        events = []
        src = r["source"]
        events.append(dict(t_rel_h=src["t_start"]/3600.0, kind="release_start",
                           label=f"Reconstructed release starts (source-term inversion)"))
        events.append(dict(t_rel_h=(src["t_start"]+src["duration"])/3600.0,
                           kind="release_end",
                           label=f"Release ends after {src['duration']/3600:.1f} h"))
        for v in r["vessels"]:
            for g in v.get("gaps", []):
                events.append(dict(t_rel_h=g[0]/3600.0, kind="ais_gap_open",
                                   label=f"{v['name']} AIS goes dark",
                                   subject=v["mmsi"]))
                events.append(dict(t_rel_h=g[1]/3600.0, kind="ais_gap_close",
                                   label=f"{v['name']} AIS resumes",
                                   subject=v["mmsi"]))
        events.append(dict(t_rel_h=0.0, kind="acquisition",
                           label=f"SAR acquisition- {r['detections'][0]['area_km2']:.0f} km² dark feature"))
        events.append(dict(t_rel_h=0.0, kind="classified",
                           label=f"Classifier: P(oil)={r['detections'][0]['p_oil']:.3f}"))
        events.append(dict(t_rel_h=0.1, kind="attributed",
                           label=(r["suspects"][0]["name"] + f"- score {r['suspects'][0]['score']:.2f}"
                                  if r["suspects"] else "no candidates")))
        events.sort(key=lambda e: e["t_rel_h"])
        return _sim_banner(dict(events=events),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- real AIS: bbox snapshot + live stream (ported from oiltrace-realdata-dg)
    _snap_cache = {}   # key -> (epoch_seconds, ships)
    _SNAP_TTL = 300

    def _ships_from_csv(w, s, e, n):
        """Fallback: load ships from the newest data/ais/*.csv, filtered to bbox.
        Lets the map show real vessels you already pulled even when the live API
        is rate-limited/blocked."""
        import glob, csv as _csv
        files = sorted(glob.glob(os.path.join(ROOT, "data", "ais", "*.csv")),
                       key=os.path.getmtime, reverse=True)
        for path in files:
            try:
                ships = {}
                with open(path, newline="") as f:
                    for row in _csv.DictReader(f):
                        try:
                            la, lo = float(row["LAT"]), float(row["LON"])
                        except (KeyError, ValueError):
                            continue
                        if not (w <= lo <= e and s <= la <= n):
                            continue
                        m = str(row.get("MMSI", "")).strip()
                        if not m:
                            continue
                        ships[m] = dict(mmsi=m, lat=la, lon=lo,
                                        sog=float(row.get("SOG") or 0),
                                        cog=float(row.get("COG") or 0),
                                        name=row.get("VesselName") or f"MMSI {m}")
                if ships:
                    return list(ships.values()), os.path.basename(path)
            except Exception:
                continue
        return None, None

    @app.get("/api/ais/snapshot")
    def ais_snapshot(bbox: str, refresh: int = 0):
        try:
            w, s, e, n = (float(x) for x in bbox.split(","))
        except Exception:
            return JSONResponse({"error": "bad bbox"}, status_code=400)
        ck = ",".join(f"{v:.2f}" for v in (w, s, e, n))
        hit = _snap_cache.get(ck)
        if hit and not refresh and (time.time() - hit[0]) < _SNAP_TTL:
            return JSONResponse({"ships": hit[1], "count": len(hit[1]), "cached": True})

        key = os.environ.get("VESSELAPI_KEY") or os.environ.get("VESSEL_API_KEY")
        if not key:
            return JSONResponse({"error": "VESSELAPI_KEY not set on server"}, status_code=400)
        try:
            sys.path.insert(0, os.path.join(ROOT, "scripts", "fetch"))
            import vesselapi
            ships = vesselapi.snapshot(w, s, e, n, key)
            _snap_cache[ck] = (time.time(), ships)
            return JSONResponse({"ships": ships, "count": len(ships), "cached": False})
        except (SystemExit, Exception) as ex:
            # API blocked/rate-limited: serve the last good pull, else the newest CSV.
            if hit:
                return JSONResponse({"ships": hit[1], "count": len(hit[1]),
                                     "cached": True, "stale": True})
            ships, src = _ships_from_csv(w, s, e, n)
            if ships:
                return JSONResponse({"ships": ships, "count": len(ships),
                                     "source": "csv:" + src, "stale": True})
            return JSONResponse({"error": str(ex)}, status_code=502)

    # ---- live AIS bridge: aisstream.io WebSocket -> browser SSE ------------
    # Real ships on the map for well-covered (foreign) waters. The server holds
    # AISSTREAM_KEY; the browser just opens an EventSource on this endpoint.
    @app.get("/api/ais/live")
    async def ais_live(bbox: str = "72.6,18.8,73.2,19.3"):
        key = os.environ.get("AISSTREAM_KEY") or os.environ.get("AISSTREAM_API_KEY")

        async def gen():
            if not key:
                yield f"event: error\ndata: {json.dumps({'message':'AISSTREAM_KEY not set on server'})}\n\n"
                return
            try:
                import websockets
            except ImportError:
                yield f"event: error\ndata: {json.dumps({'message':'pip install websockets'})}\n\n"
                return
            try:
                w, s, e, n = (float(x) for x in bbox.split(","))
            except Exception:
                yield f"event: error\ndata: {json.dumps({'message':'bad bbox'})}\n\n"
                return
            sub = {"APIKey": key, "BoundingBoxes": [[[s, w], [n, e]]],
                   "FilterMessageTypes": ["PositionReport", "ShipStaticData"]}
            names = {}
            try:
                async with websockets.connect("wss://stream.aisstream.io/v0/stream",
                                              ping_interval=20, max_size=None) as ws:
                    await ws.send(json.dumps(sub))
                    yield f"event: ready\ndata: {json.dumps({'bbox':[w,s,e,n]})}\n\n"
                    while True:
                        raw = await ws.recv()
                        try:
                            msg = json.loads(raw if isinstance(raw, str) else raw.decode())
                        except Exception:
                            continue
                        meta = msg.get("MetaData", {})
                        mmsi = str(meta.get("MMSI", "")).strip()
                        if not mmsi:
                            continue
                        mt = msg.get("MessageType")
                        body = msg.get("Message", {}).get(mt, {})
                        if mt == "ShipStaticData":
                            names[mmsi] = (body.get("Name") or meta.get("ShipName") or "").strip()
                            continue
                        if mt != "PositionReport":
                            continue
                        lat = body.get("Latitude", meta.get("latitude"))
                        lon = body.get("Longitude", meta.get("longitude"))
                        if lat is None or lon is None:
                            continue
                        payload = dict(mmsi=mmsi, lat=lat, lon=lon,
                                       sog=body.get("Sog", 0.0), cog=body.get("Cog", 0.0),
                                       name=names.get(mmsi) or meta.get("ShipName", "").strip())
                        yield f"event: ship\ndata: {json.dumps(payload, default=float)}\n\n"
            except Exception as ex:
                yield f"event: error\ndata: {json.dumps({'message': str(ex)[:160]})}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    # ---- investigator / what-if / rescore / impact / fleet alerts --------
    # ---- investigator (rule-based Q&A) -----------------------------------
    @app.get("/api/investigator")
    def investigator(iid: str, q: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(_inv.answer(r, q),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- what-if drift ---------------------------------------------------
    @app.post("/api/incidents/{iid}/whatif")
    def whatif(iid: str, wind: float = 1.0, current: float = 1.0):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        # We cannot re-run drift without the pixel mask; use the *inverted*
        # source track as the mask proxy — a slightly reduced-fidelity but very
        # fast counterfactual. Better than nothing, honestly labelled.
        import numpy as np
        # Build a small mask around the reported centroid.
        d = r["detections"][0]
        # scene dimensions from the report
        sc = r["scene"]
        n = sc["size"]
        pixel_m = sc["pixel_m"]
        origin_lat = sc["center"]["lat"]; origin_lon = sc["center"]["lon"]
        # Build mask around the contour polygon back to pixel space (approx).
        from sagar.core.geoutil import Origin as _O
        origin = _O(origin_lat, origin_lon)
        mask = np.zeros((n, n), dtype=bool)
        for lon, lat in d.get("contour_lonlat", []):
            x, y = origin.to_xy(lat, lon)
            c = int(x / pixel_m + n / 2.0)
            row = int(n / 2.0 - y / pixel_m)
            if 0 <= row < n and 0 <= c < n:
                mask[max(0,row-2):row+3, max(0,c-2):c+3] = True
        meta = dict(origin_lat=origin_lat, origin_lon=origin_lon,
                    size=n, pixel_m=pixel_m)
        return _sim_banner(_whatif.run(meta, mask, wind_scale=wind, current_scale=current),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- model-lab rescore ----------------------------------------------
    @app.post("/api/incidents/{iid}/rescore")
    def rescore(iid: str,
                source_match: float = 3.2, spatiotemporal: float = 2.4,
                alignment: float = 1.0, behaviour: float = 1.6,
                dark: float = 1.2, prior: float = 0.7, bias: float = -3.4):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        w = dict(source_match=source_match, spatiotemporal=spatiotemporal,
                 alignment=alignment, behaviour=behaviour, dark=dark, prior=prior)
        return _sim_banner(dict(candidates=_rescore.rescore(r["suspects"], w, bias)),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- landfall / impact timeline -------------------------------------
    @app.get("/api/incidents/{iid}/impact")
    def impact(iid: str, near_km: float = 30.0):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(series=_impact.series(r["forecast"], near_km=near_km),
                                near_km=near_km),
                           mode=r.get("oiltrace", {}).get("data_mode"))

    # ---- fleet-wide alerts feed -----------------------------------------
    @app.get("/api/alerts")
    def all_alerts():
        rows = []
        for iid, r in STORE.incidents.items():
            for a in r["oiltrace"].get("alerts", []):
                rows.append(dict(incident_id=iid, **a))
        # newest CRITICAL first, then HIGH, then rest
        rank = {"CRITICAL":0, "HIGH":1, "MEDIUM":2, "LOW":3, "INFO":4}
        rows.sort(key=lambda x: rank.get(x["severity"], 9))
        return _sim_banner(dict(alerts=rows, total=len(rows)))

    # ---- health / readiness ----------------------------------------------
    @app.get("/health")
    def health(): return {"ok": True}

    @app.get("/ready")
    def ready(): return {"ready": True, "incidents": len(STORE.incidents)}

    # ---- static: incident asset directories + frontend -------------------
    if os.path.isdir(OUT):
        app.mount("/incidents", StaticFiles(directory=OUT), name="incidents")
    app.mount("/", StaticFiles(directory=WEB, html=True), name="ui")
    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-warm", action="store_true",
                    help="Skip pre-warming- server starts with no incidents")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)

    if not a.no_warm:
        print(f"Warming up {len(SCENARIOS)} scenarios in parallel ...")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def _do(sc):
            t0 = time.time()
            r = _inc.run(sc.slug, OUT)
            STORE.put(r)
            return sc.slug, r["oiltrace"]["incident_id"], time.time() - t0
        # numpy releases the GIL for large ops, so threads help even in CPython.
        with ThreadPoolExecutor(max_workers=min(4, len(SCENARIOS))) as ex:
            futs = [ex.submit(_do, s) for s in SCENARIOS]
            for f in as_completed(futs):
                try:
                    slug, iid, dt = f.result()
                    print(f"  {slug:20s} -> {iid}  {dt:.0f}s")
                except Exception as e:
                    print(f"  FAILED: {e}")

    import uvicorn
    print(f"\n  OILTRACE Command Center  ->  http://127.0.0.1:{a.port}/\n")
    uvicorn.run(build_app(), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
