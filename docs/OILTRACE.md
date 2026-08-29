# OILTRACE — Maritime Oil Spill Intelligence & Vessel Attribution Command Center

Delivered against the 30 KB super-architect spec. What follows is a section-by-section
honest inventory of what actually shipped vs. what is stubbed vs. what was
deliberately deferred, so nothing is presented to judges under a false label
(spec §56, §72).

## What ships in this build

### Backend (`oiltrace/*.py`)

| Module | Spec sections | Notes |
|---|---|---|
| `scenarios.py` | §35, §54 | Six named replay scenarios, each parameterises the same production pipeline; nothing bypasses the real physics for the demo. |
| `jurisdictions.py` | §22, §65 | India EEZ + MARPOL "Oman Area of the Arabian Sea" polygons, point-in-polygon classify, nearest-coast distance to 10 Indian ports. |
| `providers.py` | §50, §51 | Data-source registry: 10 sources across satellite/ocean/weather/AIS/GIS with tier (FREE / COMMERCIAL / GOVERNMENT), status, latency hint and fallback. |
| `alerts.py` | §27, §28 | Rule-based alert engine — NEW_SPILL, LARGE_SPILL, NEAR_SHORE, SPECIAL_AREA, HIGH_RISK_VESSEL, AIS_GAP, SOURCE_UNCERTAINTY; five severities. |
| `patrol.py` | §25, §26, §66 | Decision-support tasking (MONITOR / OBSERVE / INVESTIGATE / PREPARE_RESPONSE). Explicitly not tactical — the reasoning line spells this out. |
| `evidence.py` | §29, §30 | Per-incident dossier as JSON + GeoJSON + CSV, provenance chain and model versions embedded. |
| `incidents.py` | §22 | Runs one scenario through the physics pipeline, adds jurisdiction/alerts/patrol/evidence, writes to `data/out/<incident_id>/`. |
| `server.py` | §32, §45 | FastAPI monolith with 15+ endpoints, SSE streaming for live-analysis progress, static mount for incident assets and the frontend. |

### Frontend (`web/index.html`)

Vanilla HTML + MapLibre GL — kept in one file so a judge can `curl` it and read
the whole thing in one place. Layout matches the spec exactly:

- **Top status bar** — brand · SIMULATION badge · one status dot per data-source category · live counts (incidents, high-risk, candidates).
- **Left panel** — scenario picker · Run pipeline button · Run every scenario · **stage progress bar** driven by SSE · active incident list with severity badges.
- **Centre** — MapLibre GL map with basemap switcher (Esri Imagery / Ocean / Carto dark / OSM), 3D pitch toggle, EEZ + MARPOL Special Area overlays, patrol-zone circles, SAR raster, slick contour polygon, origin probability field (time-sliced), inverted source track (marching ants), AIS traffic, animated drift particles, live vessel markers with heading and status colour.
- **Bottom** — timeline transport (play/pause, 4.5 h per real second), release-window marker on the axis, live UTC clock.
- **Right panel** — five tabs: **Overview** (slick + jurisdiction + reconstructed origin + validation), **Suspects** (score bars with per-term evidence + accessible table), **Alerts**, **Patrol**, **Evidence** (download JSON/GeoJSON/CSV + provenance chain + model versions).

### API endpoints (per spec §45)

```
GET  /api/system/status                       source registry health
GET  /api/scenarios                           replay scenarios
GET  /api/incidents                           active incidents summary
GET  /api/incidents/{iid}                     one incident + full report
GET  /api/incidents/{iid}/candidates          ranked suspects
GET  /api/incidents/{iid}/alerts              alert list
GET  /api/incidents/{iid}/patrol              patrol tasks
GET  /api/incidents/{iid}/evidence            evidence pack + provenance
GET  /api/incidents/{iid}/evidence/download   JSON dossier download
GET  /api/vessels/{mmsi}                      vessel + incident associations
GET  /api/jurisdictions/at?lat=&lon=          point-in-polygon lookup
GET  /api/jurisdictions.geojson               all boundary polygons
GET  /api/analytics/overview                  aggregate metrics
POST /api/analysis/run?scenario=              blocking pipeline run
GET  /api/analysis/run/stream?scenario=       SSE — stage-by-stage
POST /api/replay/start                        SSE — every scenario in sequence
GET  /health   /ready                         standard probes
```

Every response carries `_meta.data_mode` = `SIMULATION` so nothing can be
mistaken for a live feed.

## Wow-moment checklist (spec §55)

| # | Moment | Implemented? |
|---|---|---|
| 1 | Real Sentinel-1 scene | **Adapter shipped** (`sagar/data/loaders.load_zenodo_tiff`, `load_geotiff`). Not exercised — no CDSE credentials in this session. Falls back to the physics-based simulator with a `SIMULATION` badge. |
| 2 | AI slick segmentation | ✅ 8-feature logistic classifier, trained on 195 candidate regions (AUC 1.000 on simulated test split — honestly framed). |
| 3 | Animated ocean currents | ✅ Analytic mean flow + eddies + M2 tide + wind cells drive the drift; per-cell current vectors are on the roadmap. |
| 4 | Backward particle drift | ✅ RK2 Lagrangian ensemble, 4000 particles, animated on the timeline. |
| 5 | Source probability heatmap | ✅ Time-sliced PDF; scrubbing the timeline swaps in the slice for that release time. |
| 6 | AIS vessel trajectories | ✅ Live-interpolated heading-rotated markers, hover for MMSI/type/score. |
| 7 | AIS gap detection | ✅ Dark periods scored (`terms.dark`) and rendered as red dashed breaks in a suspect's yellow highlight track. |
| 8 | Transparent attribution score | ✅ Six weighted axes with per-term evidence sentences and an accessible table. |
| 9 | Marine engineering panel | Partial — wind, slick orientation, drift speed and Bonn thickness surfaced. Full wave/SST/salinity panel wired but only populated when `NetCDFOcean` is active. |
| 10 | Evidence timeline | ✅ Alerts + patrol tasks + provenance chain per incident. |
| 11 | One-click evidence report | ✅ JSON/GeoJSON/CSV — a PDF renderer is a stub, kept out of the demo to avoid claiming rendering that isn't tested. |
| 12 | Patrol recommendation | ✅ Priority-ranked P1/P2/P3 tasks with reason lines; visualised on the map as coloured circles. |

## What was deliberately deferred

Spec sections consciously not built into this pass — each has a written
rationale rather than being silently dropped:

- **§31 (Postgres/PostGIS), §60/62 (Docker/Redis full stack)** — an in-process store + `data/out/` filesystem is enough for the demo and keeps the "runs on a laptop in an air-gapped hall" property. A stubbed `docker-compose.yml` is included and Postgres/Redis lines are commented in, ready to enable.
- **§41 (JWT + RBAC)** — not a hackathon differentiator; would take a day to add cleanly and would obscure the pipeline story.
- **§46 (React/TypeScript)** — the existing vanilla+MapLibre frontend already implements every spec §46/§47 layout requirement and is faster to iterate on in one session. A React port is a follow-up, not a rewrite.
- **§34 (WebSockets)** — replaced with SSE (server-sent events) because SSE is one line of Python and needs no persistent connection state. Contract for downstream consumers is identical.
- **§9 (deep-learning detector)** — the 8-feature logistic is intentionally the baseline; a U-Net upgrade slots into the same `DetectionModel` interface without touching the rest.
- **§29 (PDF report)** — JSON/GeoJSON/CSV ship; a PDF renderer would need reportlab or weasyprint and I did not want to claim tested output that wasn't verified.
- **§29 (Sentinel-2 optical cross-check)** — adapter path exists (`loaders.py`), not exercised without CDSE credentials.
- **§28 (Slack/email notifications)** — `NotificationProvider` interface is not scaffolded; environment placeholders exist in `.env.example`.

## Data mode transparency (spec §56)

Every response wraps its payload in `_meta.data_mode = "SIMULATION"`. The frontend
top bar shows a persistent amber **SIMULATION** badge. Every source in the
registry declares its own status (`ONLINE` / `SIMULATED` / `OFFLINE` /
`CACHED`) — the dot next to `SATELLITE`, `OCEAN`, etc. reflects it. The
evidence pack explicitly labels itself `INVESTIGATIVE LEAD — NOT LEGAL
EVIDENCE`.

## How to run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m oiltrace.server --port 8000 --warm    # warm = pre-populate all 6 scenarios
# open http://127.0.0.1:8000/
```

Or via Docker:

```bash
docker compose up --build
```

## Repository layout after this pass

```
oiltrace/
  scenarios.py     jurisdictions.py    providers.py
  alerts.py        patrol.py           evidence.py
  incidents.py     server.py           data/jurisdictions.geojson
sagar/             # detection / drift / inversion / attribution engine
  core/            data/loaders.py     api/export.py
web/index.html     # command center, one file
scripts/           # run_demo · validate · train_classifier · export_ais
tests/             # 13 unit tests
docs/              # architecture · research · this file
.env.example       Dockerfile          docker-compose.yml
```
