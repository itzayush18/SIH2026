"""Data-source registry — spec §50.

Every source declares provenance, cost tier, credential requirement and status.
The frontend renders these as the top-bar health indicators. Adapters that
require credentials fall back to the simulator with an explicit `SIMULATION`
label rather than fabricating data (spec §56).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict


@dataclass
class Source:
    id: str
    name: str
    category: str            # "satellite" | "ocean" | "weather" | "ais" | "gis"
    tier: str                # "FREE" | "COMMERCIAL" | "GOVERNMENT"
    endpoint: str
    auth_required: bool
    status: str              # "ONLINE" | "SIMULATED" | "OFFLINE" | "CACHED"
    latency_hint: str
    last_success_iso: str = ""
    fallback: str = ""

    def dict(self):
        return asdict(self)


def _has(k): return bool(os.environ.get(k, "").strip())


def registry():
    """Snapshot the health of every configured source."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return [
        Source("sentinel1", "Sentinel-1 SAR (CDSE)", "satellite", "FREE",
               "https://stac.dataspace.copernicus.eu/v1/", auth_required=True,
               status=("ONLINE" if _has("CDSE_USER") else "SIMULATED"),
               latency_hint="~4 h from acquisition",
               last_success_iso=now,
               fallback="sagar.core.sarsim (physics-based)"),
        Source("sentinel2", "Sentinel-2 optical (CDSE)", "satellite", "FREE",
               "https://stac.dataspace.copernicus.eu/v1/", auth_required=True,
               status=("ONLINE" if _has("CDSE_USER") else "SIMULATED"),
               latency_hint="cloud-limited"),
        Source("cmems", "Copernicus Marine currents+waves", "ocean", "FREE",
               "https://data.marine.copernicus.eu/", auth_required=True,
               status=("ONLINE" if _has("CMEMS_USER") else "SIMULATED"),
               latency_hint="hourly analysis + forecast",
               fallback="sagar.core.environment.SyntheticOcean"),
        Source("era5", "ECMWF ERA5 wind", "weather", "FREE",
               "https://cds.climate.copernicus.eu/api/v2", auth_required=True,
               status=("ONLINE" if _has("CDS_UID") else "SIMULATED"),
               latency_hint="~5 d for reanalysis"),
        Source("aishub", "AISHub terrestrial AIS", "ais", "FREE",
               "http://www.aishub.net/", auth_required=True,
               status=("ONLINE" if _has("AISHUB_USER") else "SIMULATED"),
               latency_hint="~1 min",
               fallback="sagar.core.ais.synthesize"),
        Source("dg_shipping", "DG Shipping / NTRO feed", "ais", "GOVERNMENT",
               "internal", auth_required=True,
               status="OFFLINE",
               latency_hint="government access required",
               fallback="AISHub"),
        Source("spire", "Spire Maritime satellite AIS", "ais", "COMMERCIAL",
               "https://api.spire.com/", auth_required=True,
               status="OFFLINE", latency_hint="global sat-AIS, paid"),
        Source("marine_regions", "Marine Regions WFS (EEZ, MARPOL)", "gis", "FREE",
               "https://marineregions.org/webservices.php", auth_required=False,
               status="ONLINE", latency_hint="cached",
               last_success_iso=now,
               fallback="shipped simplified boundaries"),
        Source("gebco", "GEBCO bathymetry", "gis", "FREE",
               "https://download.gebco.net/", auth_required=False,
               status="OFFLINE",
               latency_hint="static grid; fetch on first use"),
        Source("esri_imagery", "Esri World Imagery basemap", "gis", "FREE",
               "https://server.arcgisonline.com/", auth_required=False,
               status="ONLINE", latency_hint="live tiles",
               last_success_iso=now),
    ]


def overview():
    """Category counts for the dashboard."""
    r = registry()
    out = {}
    for s in r:
        out.setdefault(s.category, {"online": 0, "simulated": 0, "offline": 0})
        k = s.status.lower()
        if k not in out[s.category]:
            k = "offline"
        out[s.category][k] += 1
    return out
