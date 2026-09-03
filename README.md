# OILTRACE

**Maritime Oil Spill Intelligence & Vessel Attribution Command Center.**

Smart India Hackathon 2026 · **SIH26143** · NTRO · Disaster Management.

Full command center on top of the SAGAR-DRISHTI physics engine — pipeline as
before, plus jurisdiction lookup (India EEZ + MARPOL Special Areas), an alert
engine, patrol recommendations, per-incident evidence packs (JSON/GeoJSON/CSV
with provenance chain), a source-registry with per-provider health, and a
MapLibre-GL command center with a scenario picker, live SSE progress bar,
5-tab intelligence side-panel and 6 replay scenarios.

```
python -m oiltrace.server --port 8000         → http://127.0.0.1:8000/
```

Full inventory of what's real vs stubbed vs deferred against the 72-section
spec: [docs/OILTRACE.md](docs/OILTRACE.md).

---

# SAGAR-DRISHTI

**Oil spill detection from SAR, drift hindcasting, and vessel attribution from AIS.**

Smart India Hackathon 2026 · Problem Statement **SIH26143** · National Technical
Research Organisation (NTRO) · Theme: Disaster Management

An automated pipeline that takes a SAR scene and an AIS feed and answers three
questions: *is that dark patch oil?*, *where and when did it come from?*, and
*which ship put it there?* — with the reasoning behind each answer written out
so an analyst can audit it.

---

## Quickstart

```bash
# 1. Create the virtual environment and install dependencies
python3 -m venv .venv && .venv/Scripts/pip install -r requirements.txt

# 2. Run the full demo pipeline (synthetic scene, ~30 s)
.venv/Scripts/python scripts/run_demo.py

# 3. Launch the command center dashboard
.venv/Scripts/python -m oiltrace.server --port 8000
#    → http://127.0.0.1:8000/
```

### Frontend (development mode — live-reload)

```bash
cd frontend
pnpm install
pnpm dev          # → http://127.0.0.1:5173  (proxies /api to :8000)
```

> **Note:** The backend must be running on port 8000 when using `pnpm dev`.
> For a fully self-contained single-port deployment, build the frontend first:
> ```bash
> cd frontend && pnpm build
> python -m oiltrace.server --port 8000   # serves dist/ automatically
> ```

Other entry points:

```bash
.venv/Scripts/python tests/test_pipeline.py               # 10 unit tests, ~20 s
.venv/Scripts/python scripts/validate.py --seeds 10       # batch validation, ~6 min
.venv/bin/python scripts/train_on_zenodo.py              # retrain classifier on real data
.venv/Scripts/python scripts/train_classifier.py --scenes 45   # retrain on synthetic data
.venv/Scripts/python scripts/export_ais.py                # MarineCadastre-format AIS CSV
```

No GPU required. Core pipeline: five pure-Python wheels (numpy, scipy, pillow, fastapi, uvicorn).

---

## What it does

**1 · Detect.** Refined-Lee speckle filtering and incidence-trend removal, then
multi-scale adaptive thresholding (deliberately over-detecting), then an
8-feature logistic discriminator that separates mineral oil from the look-alikes
that defeat a bare threshold — low-wind cells and biogenic films. The features
are the classical physical ones: contrast, edge sharpness, shape complexity,
internal homogeneity, local wind.

**2 · Characterise.** Bonn Agreement appearance class and thickness from damping
contrast; volume and tonnage; and **three independent age estimators** —
advective (a slick is a trail: length ÷ drift speed), Fay gravity-viscous
spreading, and weathering-driven contrast decay. They are fused in log space and
their *disagreement* is reported as the uncertainty, rather than hidden.

**3 · Hindcast and forecast.** An RK2 Lagrangian ensemble — currents + windage +
Stokes drift + turbulent random walk — run backwards to a space-time origin
probability field and forwards to a drift projection. Windage is perturbed per
particle (3.0% ± 0.6%), because it is the dominant uncertainty for surface oil.

**4 · Invert the source.** *This is the part that makes the attribution work.*
A backward particle cloud cannot localise this kind of spill: an operational
discharge from a vessel underway is a **line source**, its along-track extent
was there at t=0, and running it backwards never collapses it. Measured here:
backward spread contracts by under 2% over 26 hours, and the backward-PDF peak
lands **13.9 km** from the true origin on average.

So instead of inverting the cloud, we invert the source — hypothesise
`(t_start, duration, course, speed, x₀, y₀)`, forward-advect that moving line
through the same metocean fields, and score the footprint against the observed
slick by IoU. That halves the position error and, more importantly, produces a
**candidate source track** to match against AIS in space *and* time.

**5 · Attribute.** Reconstruct traffic from AIS, filter out vessels that can't
be scored, and rank the rest on six evidence axes:

| Axis | Weight | What it measures |
|---|---|---|
| Source-track match | 3.2 | AIS track vs the inverted source line, sampled at the release times |
| Origin envelope | 2.4 | AIS track integrated against the backward origin PDF |
| Behaviour | 1.6 | speed drop vs the vessel's own median, course alteration, loitering |
| AIS dark period | 1.2 | transponder gap overlapping the release window |
| Axis alignment | 1.0 | vessel course vs the slick's major axis |
| Vessel prior | 0.7 | type, length, draft |

Additive log-odds through a sigmoid, and every term ships with a sentence of
justification. The prior carries the smallest weight by design: it must never be
able to convict on its own.

**6 · Present.** A Vite + React + Tailwind operations dashboard (`frontend/` — Outfit, white/light-grey grid): SAR σ⁰, detected slick, origin
probability field, AIS traffic, the inverted source track, a scrubbable
hindcast↔forecast timeline, and ranked suspect cards with their evidence. MapLibre GL, fully responsive.

---

## API Reference

The backend is a FastAPI server. All endpoints return JSON with a `_meta.data_mode` field
indicating whether the data is `SIMULATION`, `REAL_IMAGERY`, or `REAL_IMAGERY_SYNTHETIC_AIS`.

### System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/system/status` | Data source registry health, provider list, incident count |
| `GET` | `/api/scenarios` | List all available scenarios with metadata |
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (returns incident count) |

### Incidents

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/incidents` | List all processed incidents (summaries) |
| `GET` | `/api/incidents/{iid}` | Full incident report + suspects + provenance |
| `GET` | `/api/incidents/{iid}/candidates` | Ranked vessel suspects with evidence terms |
| `GET` | `/api/incidents/{iid}/evidence` | Evidence pack manifest + provenance chain |
| `GET` | `/api/incidents/{iid}/evidence/download` | Download full evidence JSON |
| `GET` | `/api/incidents/{iid}/evidence.pdf` | Generate & download evidence PDF report |
| `GET` | `/api/incidents/{iid}/alerts` | Active alerts for this incident |
| `GET` | `/api/incidents/{iid}/patrol` | Coast guard patrol recommendations |
| `GET` | `/api/incidents/{iid}/dark-vessels` | Dark (AIS-off) vessel detections |
| `GET` | `/api/incidents/{iid}/timeline` | Chronological event log |
| `POST` | `/api/incidents/{iid}/notify` | Dispatch alerts to configured channels |

### Analysis

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analysis/run?scenario={slug}` | Run pipeline for one scenario (returns on completion) |
| `GET` | `/api/analysis/run/stream?scenario={slug}` | SSE stream: real-time stage progress + final incident |
| `POST` | `/api/replay/start` | SSE stream: run all 6 scenarios sequentially |

### Environment & Jurisdiction

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/environment/vectors?south=&west=&north=&east=&t_rel_h=` | Ocean current + wind vectors (GeoJSON arrows) |
| `GET` | `/api/jurisdictions/at?lat=&lon=` | Jurisdiction, sovereign, MARPOL regime at a point |
| `GET` | `/api/jurisdictions.geojson` | All jurisdiction polygons as GeoJSON |
| `GET` | `/api/coast.geojson` | Coastline GeoJSON for map rendering |

### Vessels & Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/vessels/{mmsi}` | Vessel profile + incident associations |
| `GET` | `/api/analytics/overview` | Aggregate stats across all incidents |
| `GET` | `/api/validation/mv-rak` | MV Rak 2011 validation vignette |
| `GET` | `/api/live/incois` | INCOIS live data probe |

---

## Frontend — How it connects to the API

The React frontend (`frontend/src/`) communicates with the backend entirely through
the API layer above. Here is the complete data flow:

```
Browser                          FastAPI (:8000)              Python pipeline
  │                                   │                              │
  │── GET /api/scenarios ────────────►│                              │
  │◄─ [{slug, name, story, …}] ───────│                              │
  │                                   │                              │
  │── GET /api/analysis/run/stream ──►│                              │
  │     ?scenario=arabian-tanker      │── _inc.run(slug) ───────────►│
  │                                   │                       detect │
  │◄── event: detect ─────────────────│◄──────────────────────────── │
  │◄── event: drift ──────────────────│◄──────────────────────────── │
  │◄── event: invert ─────────────────│◄──────────────────────────── │
  │◄── event: attribute ──────────────│◄──────────────────────────── │
  │◄── event: incident {iid} ─────────│                              │
  │                                   │                              │
  │── GET /api/incidents/{iid} ──────►│                              │
  │◄─ {scene, detections, source,     │                              │
  │    suspects, alerts, patrol, …}   │                              │
  │                                   │                              │
  │  MapView renders:                 │                              │
  │   • SAR σ⁰ raster overlay         │                              │
  │   • Slick contour polygon         │                              │
  │   • Origin PDF heatmap            │                              │
  │   • Hindcast/forecast particles   │                              │
  │   • Inverted source track         │                              │
  │   • AIS vessel tracks             │                              │
  │                                   │                              │
  │  RightPanel shows:                │                              │
  │   • Overview tab: scene, slick    │                              │
  │   • Suspects tab: ranked cards    │                              │
  │   • Alerts tab: severity/actions  │                              │
  │   • Patrol tab: CG recommendations│                              │
  │   • Timeline tab: event log       │                              │
  │   • Evidence tab: download pack   │                              │
```

### Key frontend files

| File | Purpose |
|---|---|
| [`src/lib/api.ts`](frontend/src/lib/api.ts) | `fetchJSON()` wrapper; falls back to static JSON files for offline demos |
| [`src/lib/types.ts`](frontend/src/lib/types.ts) | TypeScript interfaces for `Report`, `IncidentSummary`, `Scenario`, etc. |
| [`src/App.tsx`](frontend/src/App.tsx) | Root component; SSE connection, incident state, tab routing |
| [`src/components/LeftPanel.tsx`](frontend/src/components/LeftPanel.tsx) | Scenario picker, Run button, incident list, SSE progress bar |
| [`src/components/MapView.tsx`](frontend/src/components/MapView.tsx) | MapLibre GL map — SAR raster, slick, drift, tracks, source line |
| [`src/components/RightPanel.tsx`](frontend/src/components/RightPanel.tsx) | 6-tab intelligence panel (overview / suspects / alerts / patrol / timeline / evidence) |
| [`src/components/Timeline.tsx`](frontend/src/components/Timeline.tsx) | Scrubbable hindcast↔forecast slider |
| [`src/components/TopBar.tsx`](frontend/src/components/TopBar.tsx) | Status bar: data mode badge, incident count, high-risk count |

---

## ML Classifier — Training on Real Data

The 8-feature logistic oil/look-alike discriminator (`sagar/data/oil_classifier.json`)
can be trained on two data sources:

### Option A — Zenodo Sentinel-1 Dataset (real calibrated SAR scenes, **recommended**)

**Dataset:** [Sentinel-1 SAR Oil Spill Dataset, Part I](https://zenodo.org/records/8346860)
(1,200 scenes · 2048×2048×2 float32 GeoTIFF · Sigma0 VV+VH in dB · with ground-truth masks)

Download **both** archives — the masks are only 6.2 MB and easy to overlook:

```
01_Train_Val_Oil_Spill_images.7z   40.7 GB  →  Oil/00000.tif …
01_Train_Val_Oil_Spill_mask.7z      6.2 MB  →  Mask_oil/00000.tif …
```

Extract them as siblings; basenames pair 1:1. These scenes are already
SNAP-processed (Orbit → Thermal Noise Removal → Calibration → Speckle filter →
Terrain Correction → dB), so the pixel values are genuine decibels.

```bash
# Full training on all 1,200 scenes (~3.5 h on CPU, feature extraction dominates)
.venv/bin/python scripts/train_on_zenodo.py \
    --images /path/to/Oil --masks /path/to/Mask_oil \
    --cache features.npz

# Quick pass (120 scenes, ~20 min)
.venv/bin/python scripts/train_on_zenodo.py --limit 120

# Re-fit in seconds once features are cached
.venv/bin/python scripts/train_on_zenodo.py --cache features.npz --epochs 20000
```

**Results (full run, 1,200 scenes → ~110,000 labelled regions):**

| Metric | Value |
|---|---|
| Test Accuracy | 91.6% |
| Test AUC | 0.951 |
| Recall | 0.856 |
| F1 | 0.512 |

**How it works:** rather than cropping one blob per image, the script runs the
*actual inference segmenter* (`detect.dark_spot_candidates`) over each scene and
labels every candidate by its overlap with the ground-truth mask — ≥50% inside
is oil, ≤5% is a look-alike, and the ambiguous band between is dropped rather
than guessed at. The negatives are therefore exactly the look-alikes the
deployed detector really trips on. `--cache` saves the extracted feature matrix
so hyperparameter retries cost seconds instead of hours. The resulting
`oil_classifier.json` is a drop-in replacement — no other code changes needed.

### Option B — Synthetic data (no download required)

```bash
.venv/Scripts/python scripts/train_classifier.py --scenes 45
```

Generates synthetic SAR scenes with correct Bragg physics, fits the same model.
Achieves AUC ~1.0 on simulated data (note: this will not generalise to real scenes).

### How training flows into inference

```
Training (one-off)                    Inference (every run)
═══════════════════════════           ═══════════════════════════════════════
Kaggle JPEGs / synthetic scenes       Any SAR scene (simulated or real GeoTIFF)
         │                                          │
         ▼                                          ▼
detect.preprocess()  ──── same ───── detect.preprocess()
detect._region_features()  ── same── detect._region_features()
logistic regression fit               detect.score()  ← reads oil_classifier.json
         │                                          │
         ▼                                          ▼
sagar/data/oil_classifier.json ──────────────────── P(oil) per candidate region
```

---

## Datasets Used

| Data | Source | Usage |
|---|---|---|
| **SAR oil spill chips (training)** | [Kaggle Sentinel-1 CSIRO dataset](https://www.kaggle.com/datasets/harikrishnacs/sentinel-1-sar-oil-spill-detection-dataset) | Train the 8-feature logistic discriminator |
| **SAR segmentation labels** | [Zenodo Sentinel-1 Part I](https://zenodo.org/records/8346860), [Part II](https://zenodo.org/records/8253899), [Part III](https://zenodo.org/records/13761290) | 2048×2048 σ⁰ dB TIFFs with pixel masks; real-data adapter in `loaders.py` |
| **Raw SAR imagery** | Copernicus Data Space (Sentinel-1 GRD, IW GRDH) | Real-scene inference via `loaders.load_geotiff` |
| **Ocean currents** | [CMEMS GLOBAL_ANALYSISFORECAST_PHY_001_024](https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/services) | Surface currents (u, v) for Lagrangian drift |
| **Wind** | ERA5 single-levels (u10, v10) | 10 m wind for leeway drift and local wind proxy feature |
| **AIS** | [MarineCadastre](https://marinecadastre.gov/accessais/) / NTRO / DG Shipping | Vessel tracks for attribution; `ais.load_csv` adapter |
| **Synthetic corpus** | Built-in `sagar/core/sarsim.py` | Physics-correct SAR scene generation for pipeline testing |

---

## Results

Ten independent scenarios (`scripts/validate.py --seeds 10`) — every seed
regenerates the metocean fields, slick geometry, discharge timing, look-alike
population and traffic picture, so these are repeated measurements, not one
lucky scene.

| Metric | Mean | Median | Worst |
|---|---|---|---|
| Segmentation IoU | 0.699 | 0.735 | 0.439 |
| Segmentation F1 | 0.813 | - | - |
| **Attribution accuracy** | **10 / 10** | - | - |
| Top-1 score margin over runner-up | 0.52 | - | 0.29 |
| Origin position error (inversion) | 9.4 km | 9.6 km | 17.0 km |
| Origin position error (backward PDF alone) | 13.9 km | - | - |
| Release time error | 198 min | 185 min | - |
| Source course error | 21° | - | - |
| Runtime per scenario | 32 s | - | - |

**Classifier (real Kaggle data):** Test AUC 0.863 · Accuracy 81.8% · F1 0.744
on 1,385 held-out real Sentinel-1 chips (oil vs look-alike).

---

## Honest limitations

The simulated scenarios are trained and validated on **simulated** scenes. The simulator
implements the right physics — Bragg damping with a CMOD-like wind background,
Gamma speckle at Sentinel-1's ENL, incidence trend across the swath, low-wind
cells and biogenic films — and the ground truth is derived by *the same drift
physics the pipeline then inverts*, so origin recovery is a fair test with a
known answer. But:

- **The classifier AUC of 0.951 is from the Zenodo train/val split.** It will
  still degrade on the held-out Part III test set — real look-alikes are more
  varied than any training corpus, and the split shares scenes and sensors.
- **The reported search dispersion is not a calibrated error bar.** The
  optimiser converges tightly (~1 km) onto answers that can be 17 km wrong,
  because the forward map is only weakly identifiable along the drift direction.
  Read a *wide* dispersion as "distrust this inversion"; do not read a narrow one as
  confirmation.
- Single-polarisation intensity only. VH and polarimetric features
  (entropy/alpha, co-pol phase difference) are the standard next lever.
- No land or ice masking; analytic metocean fields rather than CMEMS/ERA5.
- Rankings are **investigative leads**, not findings of guilt. Enforcement under
  MARPOL Annex I requires corroboration — typically oil fingerprinting against a
  sample taken at port state inspection.

---

## Moving to operational data

Everything algorithmic depends on exactly two interfaces, which is why this is a
configuration change rather than a rewrite:

```python
scene.sigma0_db                 # ndarray, dB
scene.latlon_of_pixel(r, c)     # → (lat, lon)
ocean.sample_xy(t, x, y)        # → (u_cur, v_cur, u_wind, v_wind)
```

| Source | Adapter |
|---|---|
| Zenodo Sentinel-1 scenes + masks | `scripts/train_on_zenodo.py` (training only) |
| Zenodo Sentinel-1 oil-spill dataset (labelled TIFFs) | `loaders.load_zenodo_tiff` |
| Sentinel-1 GRD GeoTIFF (georeferenced) | `loaders.load_geotiff` |
| CMEMS currents + ERA5 winds | `loaders.NetCDFOcean` |
| MarineCadastre / real AIS CSV | `ais.load_csv` |

Dataset links, model references and the reasoning behind each design choice are
in **[docs/research.md](docs/research.md)**; the module map and the decisions
worth defending are in **[docs/architecture.md](docs/architecture.md)**.

---

## Repository layout

```
sagar/core/     geoutil · environment · sarsim · scenario · detect
                characterize · drift · inversion · ais · attribute · pipeline
                dark_vessel · narrative · incois · mv_rak
sagar/data/     loaders.py (real-data adapters) · oil_classifier.json
sagar/api/      export.py (report.json + PNG overlays)
oiltrace/       server.py (FastAPI) · incidents · scenarios · alerts
                patrol · evidence · jurisdictions · providers · pdf · notify
frontend/       Vite + React + TypeScript + Tailwind (Outfit, white/light-grey, grid)
                src/lib/api.ts        API client (fetchJSON + static fallback)
                src/lib/types.ts      TypeScript interfaces for Report, Incident, etc.
                src/App.tsx           Root: SSE wiring, incident state, tab routing
                src/components/       MapView · LeftPanel · RightPanel · Timeline · TopBar
scripts/        run_demo · serve · validate · train_on_zenodo · train_classifier · export_ais
tests/          test_pipeline.py  test_new_features.py
docs/           architecture.md · research.md · OILTRACE.md
data/           out/ (incident evidence packs) · dataset/ (Kaggle training data, gitignored)
```

---

## How to Run

### ▶ Quickest — single command, everything served on one port

```bash
# Install dependencies (first time only)
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# Build the frontend (first time only, or after UI changes)
cd frontend && pnpm install && pnpm build && cd ..

# Launch — warms all 6 scenarios, then serves at http://127.0.0.1:8000/
.venv\Scripts\python -m oiltrace.server --port 8000
```

Open **http://127.0.0.1:8000** in your browser. The dashboard will load with all
incidents already processed and the real-data classifier active.

---

### ▶ Dev mode — live-reload frontend

Run two terminals simultaneously:

**Terminal 1:**
```bash
.venv\Scripts\python -m oiltrace.server --port 8000 --no-warm
```

**Terminal 2:**
```bash
cd frontend
pnpm dev      # → http://127.0.0.1:5173  (API calls proxy to :8000)
```

---

### ▶ Other commands

| Task | Command |
|---|---|
| Run full pipeline demo (CLI, ~30 s) | `.venv\Scripts\python scripts/run_demo.py` |
| Run 10-scenario batch validation | `.venv\Scripts\python scripts/validate.py --seeds 10` |
| **Retrain classifier on real data** | `.venv/bin/python scripts/train_on_zenodo.py` |
| Retrain classifier on synthetic data | `.venv\Scripts\python scripts/train_classifier.py --scenes 45` |
| Run unit tests | `.venv\Scripts\python tests/test_pipeline.py` |
| Export synthetic AIS CSV | `.venv\Scripts\python scripts/export_ais.py` |
| Rebuild frontend | `cd frontend && pnpm build` |
