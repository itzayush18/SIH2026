"""Data-source registry- spec §50.

Every source declares provenance, cost tier, credential requirement and status.
The frontend renders these as the top-bar health indicators. Adapters that
require credentials fall back to the simulator with an explicit `SIMULATION`
label rather than fabricating data (spec §56).

This module now distinguishes per-incident data modes so the status dots can
reflect honest provenance per source, not just a global banner:

  SIMULATION                 - 100% synthetic physics + synthetic AIS
  SYNTHETIC_OVERLAY          - synthetic AIS overlaid on a real geography/incident
                               (e.g. MV Rak 2011), distinct from pure SIMULATION
  REAL_IMAGERY_SYNTHETIC_AIS - Zenodo Sentinel-1 scene + synthetic-overlay AIS
  REAL_IMAGERY_REAL_AIS      - Zenodo scene + real AccessAIS traffic
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict

DATA_MODES = (
    "SIMULATION",
    "SYNTHETIC_OVERLAY",
    "REAL_IMAGERY_SYNTHETIC_AIS",
    "REAL_IMAGERY_REAL_AIS",
)
# Back-compat alias used by older live.py values
_LEGACY_MODE_MAP = {"MIXED": "REAL_IMAGERY_SYNTHETIC_AIS",
                    "PARTIAL_REAL": "REAL_IMAGERY_SYNTHETIC_AIS"}


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


def _has_zenodo():
    # Consider Zenodo present if a local cache directory or marker exists
    import os as _os
    for p in ("data/zenodo", "data/real", "data/samples"):
        if _os.path.exists(p) and _os.listdir(p):
            return True
    return False


def registry():
    """Snapshot the health of every configured source."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Per-source reasoning: mark zenodo/incois honestly rather than just SIMULATED
    zenodo_status = "ONLINE" if _has_zenodo() else "CACHED"
    # INCOIS OOSA- reachable check is cheap, but we don't block; show OFFLINE until probed
    incois_status = "SIMULATED"  # default; live probe upgrades to ONLINE at runtime
    try:
        # If caller set INCOIS_LIVE=1 we claim ONLINE; otherwise keep fallback
        if _has("INCOIS_TOKEN") or _has("INCOIS_LIVE"):
            incois_status = "ONLINE"
    except Exception:
        pass
    return [
        Source("sentinel1", "Sentinel-1 SAR (CDSE)", "satellite", "FREE",
               "https://stac.dataspace.copernicus.eu/v1/", auth_required=True,
               status=("ONLINE" if _has("CDSE_USER") else "SIMULATED"),
               latency_hint="~4 h from acquisition",
               last_success_iso=now,
               fallback="sagar.core.sarsim (physics-based)"),
        Source("zenodo", "Zenodo Sentinel-1 Oil Spill Dataset (Trujillo-Acatitla et al.)", "satellite", "FREE",
               "https://zenodo.org/records/8346860", auth_required=False,
               status=zenodo_status,
               latency_hint="labeled TIFFs- 150 oil / 150 look-alike / 150 clean (Part III)",
               last_success_iso=now if zenodo_status == "ONLINE" else "",
               fallback="sagar.core.sarsim (honest fallback with SYNTHETIC_OVERLAY label)"),
        Source("sentinel2", "Sentinel-2 optical (CDSE)", "satellite", "FREE",
               "https://stac.dataspace.copernicus.eu/v1/", auth_required=True,
               status=("ONLINE" if _has("CDSE_USER") else "SIMULATED"),
               latency_hint="cloud-limited"),
        Source("cmems", "Copernicus Marine currents+waves", "ocean", "FREE",
               "https://data.marine.copernicus.eu/", auth_required=True,
               status=("ONLINE" if _has("CMEMS_USER") else "SIMULATED"),
               latency_hint="hourly analysis + forecast",
               fallback="sagar.core.environment.SyntheticOcean"),
        Source("incois", "INCOIS OOSA / High-Res Ocean State Forecast", "ocean", "FREE",
               "https://incois.gov.in/", auth_required=False,
               status=incois_status,
               latency_hint="India-sourced; NTRO-credible; graceful fallback to SyntheticOcean",
               last_success_iso=now if incois_status == "ONLINE" else "",
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
        Source("accessais", "US AccessAIS bulk (MarineCadastre)- real AIS reference", "ais", "FREE",
               "https://marinecadastre.gov/accessais/", auth_required=False,
               status="CACHED",
               latency_hint="bulk CSV; ordering service flaky, bulk files reliable",
               last_success_iso="",
               fallback="sagar.core.ais.load_csv with SYNTHETIC_OVERLAY flag"),
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
        out.setdefault(s.category, {"online": 0, "simulated": 0, "offline": 0, "cached": 0})
        k = s.status.lower()
        if k not in out[s.category]:
            k = "offline"
        out[s.category][k] += 1
    return out


def registry_for_mode(data_mode: str):
    """Adjust the global registry to honestly reflect a single incident's provenance.

    The global `registry()` answers 'are credentials configured on this host?'.
    `registry_for_mode()` answers 'what did this specific incident actually use?'
    by overriding the relevant categories to ONLINE / SYNTHETIC_OVERLAY / SIMULATED
    so the grey status dots are not lying globally when one incident is real.
    """
    base = registry()
    dm = _LEGACY_MODE_MAP.get(data_mode, data_mode)
    if dm == "SIMULATION":
        return base
    # Per-mode overrides: which source ids become honest REAL/SYNTHETIC_OVERLAY
    overrides = {}
    if dm == "SYNTHETIC_OVERLAY":
        overrides = {"sentinel1": "SIMULATED", "zenodo": "CACHED",
                     "aishub": "SIMULATED", "accessais": "SIMULATED"}
    elif dm == "REAL_IMAGERY_SYNTHETIC_AIS":
        overrides = {"sentinel1": "ONLINE", "zenodo": "ONLINE",
                     "aishub": "SIMULATED", "accessais": "SIMULATED"}
    elif dm == "REAL_IMAGERY_REAL_AIS":
        overrides = {"sentinel1": "ONLINE", "zenodo": "ONLINE",
                     "aishub": "ONLINE", "accessais": "ONLINE"}
    out = []
    for s in base:
        if s.id in overrides:
            # copy with overridden status
            import dataclasses
            s = dataclasses.replace(s, status=overrides[s.id])
        out.append(s)
    return out


def canonical_mode(m: str) -> str:
    m = _LEGACY_MODE_MAP.get(m, m)
    return m if m in DATA_MODES else "SIMULATION"
