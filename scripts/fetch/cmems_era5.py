"""Fetch a subset of CMEMS currents + ERA5 winds for an AOI.

CMEMS via `copernicusmarine` (pip install copernicusmarine, credentials in
`~/.copernicusmarine/credentials` or CMEMS_USER / CMEMS_PASSWORD env).
ERA5 via the `cdsapi` client (~/.cdsapirc or CDS_UID/CDS_KEY env).

    python scripts/fetch/cmems_era5.py \
        --bbox 68,15,75,22 --start 2026-03-13 --end 2026-03-15 \
        --out data/env

Once downloaded, pass the two NetCDF files to
`sagar.data.loaders.NetCDFOcean(origin, currents_nc, winds_nc, epoch)` and the
drift engine uses them transparently.
"""
from __future__ import annotations

import argparse
import os
import sys


def _bridge_env():
    """The libraries don't actually read CMEMS_USER/CDS_UID/CDS_KEY — that's
    just this repo's naming in .env.example. Bridge them to the env vars
    copernicusmarine/cdsapi really check, so filling in .env is enough and
    nobody has to separately discover COPERNICUSMARINE_SERVICE_USERNAME or
    hand-write ~/.cdsapirc."""
    if os.environ.get("CMEMS_USER") and not os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME"):
        os.environ["COPERNICUSMARINE_SERVICE_USERNAME"] = os.environ["CMEMS_USER"]
        os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"] = os.environ.get("CMEMS_PASSWORD", "")
    if os.environ.get("CDS_UID") and os.environ.get("CDS_KEY") and not os.environ.get("CDSAPI_KEY"):
        os.environ["CDSAPI_URL"] = "https://cds.climate.copernicus.eu/api"
        os.environ["CDSAPI_KEY"] = f"{os.environ['CDS_UID']}:{os.environ['CDS_KEY']}"


def cmems(bbox, start, end, out):
    try:
        import copernicusmarine as cm
    except ImportError:
        sys.exit("pip install copernicusmarine")
    _bridge_env()
    w, s, e, n = bbox
    cm.subset(
        dataset_id="cmems_mod_glo_phy_anfc_0.083deg_PT1H-m",
        variables=["uo", "vo", "thetao"],
        minimum_longitude=w, maximum_longitude=e,
        minimum_latitude=s, maximum_latitude=n,
        start_datetime=start, end_datetime=end,
        # This product's shallowest layer is ~0.494 m. Asking for [0, 0.5] makes
        # CMEMS print "subset ... exceed the dataset coordinates" and then clamp
        # to that single surface layer — which is exactly the surface current we
        # want. The warning is expected and harmless; NetCDFOcean squeezes the
        # length-1 depth axis on read, so nothing downstream sees it.
        minimum_depth=0.0, maximum_depth=1.0,
        output_directory=out, output_filename="cmems_currents.nc")


def era5(bbox, start, end, out):
    try:
        import cdsapi
    except ImportError:
        sys.exit("pip install cdsapi")
    _bridge_env()
    w, s, e, n = bbox
    c = cdsapi.Client()
    c.retrieve("reanalysis-era5-single-levels", {
        "product_type": "reanalysis",
        "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
        "year": [start[:4]], "month": [start[5:7]],
        "day": [f"{d:02d}" for d in range(int(start[8:10]), int(end[8:10]) + 1)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": [n, w, s, e],
        "format": "netcdf",
    }, os.path.join(out, "era5_wind.nc"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="west,south,east,north")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    bbox = tuple(float(x) for x in a.bbox.split(","))
    print("Fetching CMEMS currents ...")
    cmems(bbox, a.start, a.end, a.out)
    print("Fetching ERA5 wind ...")
    era5(bbox, a.start + "T00:00", a.end + "T00:00", a.out)
    print(f"wrote to {a.out}")


if __name__ == "__main__":
    main()
