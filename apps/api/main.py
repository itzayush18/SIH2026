"""
OilTrace — FastAPI application entry point.

Configures CORS, mounts routes, and sets up the application lifecycle.
Run with: python -m uvicorn apps.api.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import router
from apps.api.store import store
from packages.schemas.models import SCORE_TYPE


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    # Startup: seed demo case if store is empty
    from packages.schemas.models import Case, CaseStatus
    from datetime import datetime

    if not store.cases:
        demo_case = Case(
            case_id="case_demo_01",
            aoi={
                "type": "Polygon",
                "coordinates": [[
                    [72.80, 18.90],
                    [72.92, 18.90],
                    [72.92, 19.02],
                    [72.80, 19.02],
                    [72.80, 18.90],
                ]],
            },
            start_utc=datetime(2026, 8, 19, 0, 0, 0),
            end_utc=datetime(2026, 8, 21, 0, 0, 0),
            status=CaseStatus.created,
            created_by="demo_seed",
        )
        store.create_case(demo_case)

    yield
    # Shutdown: nothing to clean up for in-memory store


app = FastAPI(
    title="OilTrace API",
    description=(
        "Satellite oil-spill detection, drift hindcasting, and "
        "AIS-based vessel attribution platform. "
        f"Attribution scores use score_type='{SCORE_TYPE}' — "
        "never 'probability' or 'guilty'."
    ),
    version="0.1.0-scaffold",
    lifespan=lifespan,
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routes
app.include_router(router)


@app.get("/")
async def root():
    """Health check / landing."""
    return {
        "service": "oiltrace-api",
        "version": "0.1.0-scaffold",
        "score_type": SCORE_TYPE,
        "docs": "/docs",
    }
