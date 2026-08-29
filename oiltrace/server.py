"""OILTRACE backend — spec §32, §45.

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "out")
WEB = os.path.join(ROOT, "web")


class Store:
    """In-process incident registry. Redis would be the drop-in for a cluster."""
    def __init__(self):
        self.incidents = {}   # incident_id -> report

    def put(self, rep):
        self.incidents[rep["oiltrace"]["incident_id"]] = rep

    def get(self, iid):
        return self.incidents.get(iid)

    def list(self):
        return [_inc.summary(r) for r in self.incidents.values()]


STORE = Store()


def _sim_banner(payload):
    """Wrap every response in a mode header — spec §56."""
    if isinstance(payload, dict):
        payload["_meta"] = dict(data_mode="SIMULATION",
                                generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                           time.gmtime()))
    return payload


def build_app():
    app = FastAPI(title="OILTRACE", version="0.4.0",
                  description="Oil Spill Intelligence & Vessel Attribution Command Center — "
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
        return _sim_banner(dict(incident=_inc.summary(r), report=r))

    @app.get("/api/incidents/{iid}/candidates")
    def get_candidates(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(candidates=r["suspects"]))

    @app.get("/api/incidents/{iid}/evidence")
    def get_evidence(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(evidence=r["oiltrace"]["evidence_pack"],
                                provenance=r["oiltrace"]["provenance"]))

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
        return _sim_banner(dict(alerts=r["oiltrace"]["alerts"]))

    @app.get("/api/incidents/{iid}/patrol")
    def get_patrol(iid: str):
        r = STORE.get(iid)
        if not r: raise HTTPException(404, "unknown incident")
        return _sim_banner(dict(patrol=r["oiltrace"]["patrol"]))

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
        return _sim_banner(dict(dispatched=_notify.dispatch_critical(r)))

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
                           label=f"SAR acquisition — {r['detections'][0]['area_km2']:.0f} km² dark feature"))
        events.append(dict(t_rel_h=0.0, kind="classified",
                           label=f"Classifier: P(oil)={r['detections'][0]['p_oil']:.3f}"))
        events.append(dict(t_rel_h=0.1, kind="attributed",
                           label=(r["suspects"][0]["name"] + f" — score {r['suspects'][0]['score']:.2f}"
                                  if r["suspects"] else "no candidates")))
        events.sort(key=lambda e: e["t_rel_h"])
        return _sim_banner(dict(events=events))

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
                    help="Skip pre-warming — server starts with no incidents")
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
