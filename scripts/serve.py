"""Serve the dashboard and a small API.

    python scripts/serve.py [--port 8000] [--out data/out]

GET  /                     the dashboard
GET  /report.json          the current report (plus PNG overlays)
POST /api/run              re-run once, blocking, returns the full report
GET  /api/run/stream       re-run and stream analysis stages as SSE events
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import queue
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from sagar.api import export
from sagar.core import pipeline

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_app(outdir):
    app = FastAPI(title="SAGAR-DRISHTI")

    @app.post("/api/run")
    def run(seed: int = 11, hours_back: float = 24.0, hours_fwd: float = 18.0):
        r = pipeline.run(seed=seed, hours_back=hours_back, hours_fwd=hours_fwd)
        return JSONResponse(export.build(r, outdir))

    @app.get("/api/run/stream")
    async def run_stream(seed: int = 11, hours_back: float = 24.0, hours_fwd: float = 18.0):
        """Emit an SSE event at every stage boundary, then a final `report` event
        with the URL of the written report. Runs the (blocking) pipeline in a
        worker thread and bridges its callbacks onto the event loop through a
        Queue- asyncio.to_thread would only give one result at the end.
        """
        q: queue.Queue = queue.Queue()
        SENTINEL = object()

        def worker():
            try:
                r = pipeline.run(seed=seed, hours_back=hours_back,
                                 hours_fwd=hours_fwd,
                                 on_stage=lambda name, data: q.put((name, data)))
                export.build(r, outdir)
                q.put(("report", {"url": "report.json"}))
            except Exception as e:
                q.put(("error", {"message": str(e)}))
            finally:
                q.put(SENTINEL)

        threading.Thread(target=worker, daemon=True).start()

        async def gen():
            loop = asyncio.get_running_loop()
            while True:
                item = await loop.run_in_executor(None, q.get)
                if item is SENTINEL:
                    return
                name, data = item
                yield f"event: {name}\ndata: {json.dumps(data, default=float)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    @app.get("/api/health")
    def health():
        return {"ok": True, "report": os.path.exists(os.path.join(outdir, "report.json"))}

    # Frontend is now Vite + React + Tailwind in frontend/ (see oiltrace/server.py for prod WEB)
    _FRONTEND_DIST = os.path.join(ROOT, "frontend", "dist")
    _FALLBACK_WEB = os.path.join(ROOT, "frontend")
    _WEB = _FRONTEND_DIST if os.path.isdir(_FRONTEND_DIST) else _FALLBACK_WEB
    app.mount("/", _Merged(outdir, _WEB), name="ui")
    return app


class _Merged(StaticFiles):
    """Serve from `primary`, fall back to `secondary`."""

    def __init__(self, primary, secondary):
        super().__init__(directory=secondary, html=True)
        self.primary = primary

    def lookup_path(self, path):
        full = os.path.join(self.primary, path)
        if os.path.isfile(full):
            return full, os.stat(full)
        return super().lookup_path(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "out"))
    a = ap.parse_args()
    if not os.path.exists(os.path.join(a.out, "report.json")):
        print("no report yet- running the pipeline once ...")
        export.build(pipeline.run(), a.out)
    import uvicorn
    print(f"\n  SAGAR-DRISHTI  ->  http://127.0.0.1:{a.port}/\n")
    uvicorn.run(build_app(a.out), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
