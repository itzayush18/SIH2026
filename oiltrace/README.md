# OilTrace

**Satellite oil-spill detection, drift hindcasting, and AIS-based vessel attribution platform.**

SIH 2026 · PS 26143

---

## Quick Start

### Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **Poetry** — `pip install poetry` or [install.python-poetry.org](https://install.python-poetry.org)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **pnpm** — Install via `npm i -g pnpm`

> **Hardware note**: OilTrace runs on modest hardware. No Docker, no GPU, no Postgres required for the scaffold. Everything runs as plain local processes.

---

### Windows

```powershell
# 1. Clone and enter the project
cd oiltrace

# 2. Run setup (installs Python deps via Poetry + JS deps via pnpm)
.\setup.bat

# 3. Start both servers
.\start.bat
```

This opens two terminal windows:
- **API** → http://localhost:8000 (FastAPI + Swagger docs at `/docs`)
- **UI** → http://localhost:5173 (React + MapLibre)

#### Run tests (Windows)
```powershell
poetry run pytest tests\unit\ -v
```

---

### macOS / Linux

```bash
# 1. Clone and enter the project
cd oiltrace

# 2. Run setup
make setup

# 3. Start both servers
make dev
```

Press `Ctrl+C` to stop both servers.

#### Run tests (macOS/Linux)
```bash
make test
```

---

## Project Structure

```
oiltrace/
├── apps/
│   ├── web/            # React + MapLibre UI (Vite)
│   └── api/            # FastAPI routes + case state machine
├── services/
│   ├── ingestion/      # Source adapters, checksums, metadata QC
│   ├── vision/         # Preprocessing, inference stub, vectorisation
│   ├── drift/          # OpenDrift config stub, ensembles, contours
│   ├── ais/            # Parsing, QC, segmentation, interpolation
│   ├── attribution/    # Gating, scoring, explanations
│   └── reporting/      # PDF/GeoJSON/CSV export stub
├── packages/
│   ├── schemas/        # Pydantic models (shared types)
│   ├── geo/            # CRS/distance/raster utils
│   └── observability/  # Structured logs, run manifests
├── models/             # Model card placeholders
├── configs/            # Demo + env config
├── data/demo/          # Demo case fixture
├── tests/              # Unit, integration, scenario, UI tests
├── docs/               # Architecture docs
├── setup.bat           # Windows setup
├── start.bat           # Windows start
├── start.sh            # macOS/Linux start
├── Makefile            # macOS/Linux: make setup / make dev
└── requirements.txt    # Python dependencies
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/cases` | Create a new investigation case |
| `POST` | `/cases/{id}/assets` | Register a source asset |
| `POST` | `/cases/{id}/detect` | Queue oil-spill detection |
| `POST` | `/detections/{run}/review` | Accept/reject/uncertain slicks |
| `POST` | `/cases/{id}/drift` | Queue drift-hindcast ensemble |
| `GET` | `/cases/{id}/candidates` | Get ranked candidate vessels |
| `POST` | `/cases/{id}/export` | Export report bundle |
| `GET` | `/jobs/{id}` | Check job status |

Interactive API docs: http://localhost:8000/docs

## Attribution Scoring

```
R(v) = 100 × q_case × q_ais(v) × (0.35·s_space + 0.25·s_time + 0.25·s_fit + 0.15·s_beh)
```

> ⚠️ **Product Rule**: The output is an **evidence index** — not a probability, not a guilt determination. All API responses use `score_type: "evidence_index"`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.10+) |
| Data | DuckDB + Parquet |
| Geospatial | Shapely, pyproj |
| Drift | OpenDrift/OpenOil (stub) |
| UI | React 18 + MapLibre GL JS |
| Build | Vite |
| Package Manager | pnpm |
| Tests | pytest + httpx |

## Scaffold Status

This is the **initial scaffold pass**. The following are stubbed:
- ML detection model (returns hardcoded polygon)
- Drift hindcasting (returns static contours)
- AIS data (returns mock observations)
- PDF export (returns metadata only)
- Auth/roles, calibration, real Sentinel-1/AIS ingestion