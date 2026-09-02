"""Fetch a calibrated Sentinel-1 VV scene from Microsoft Planetary Computer,
clip+downsample it to an AOI, and write a dB GeoTIFF that `load_geotiff` reads.

Why MPC + RTC and not CDSE GRD:
  * MPC serves Sentinel-1 as cloud-optimized GeoTIFFs over plain HTTPS — no
    ~1 GB .SAFE download, no S3 keys, no token (signing is anonymous + free).
    We read only the AOI window at an overview level → megabytes, not gigabytes.
  * We use the `sentinel-1-rtc` collection (Radiometrically Terrain Corrected),
    which is map-projected (UTM, 10 m) and CALIBRATED to gamma-nought. Plain GRD
    (on both MPC and CDSE) is raw DN in radar geometry (crs=None) — you can't
    clip it by lon/lat and it isn't calibrated.

Calibration is genuine here: RTC pixels are linear gamma0, converted with
sigma0_dB = 10*log10(gamma0). That's real terrain-corrected backscatter in dB,
the units the detector expects — not a pseudo-calibration.

    pip install pystac-client planetary-computer rasterio
    python scripts/fetch/sentinel1_mpc.py \
        --bbox 71.4,19.0,72.1,19.7 \
        --start 2024-01-01 --end 2024-06-30 \
        --out data/scenes/s1_mpc.tif --size 1024

Output: single-band Float32 GeoTIFF in dB, UTM CRS, which
`sagar.data.loaders.load_geotiff` reads directly (origin + pixel size come from
the geotransform; max value < 60 dB so it is treated as dB, not re-converted).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="west,south,east,north")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=1024,
                     help="target width/height in px (downsampled via COG overviews)")
    ap.add_argument("--pol", default="vv", choices=["vv", "vh"])
    a = ap.parse_args()

    try:
        import planetary_computer, pystac_client, rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds
        from rasterio.enums import Resampling
        from rasterio.transform import Affine
    except ImportError as e:
        sys.exit(f"missing dep: {e}. Run: pip install pystac-client planetary-computer rasterio")

    w, s, e, n = (float(x) for x in a.bbox.split(","))

    print(f"Searching MPC sentinel-1-rtc over [{w},{s},{e},{n}] {a.start}..{a.end} ...")
    cat = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace)
    items = list(cat.search(collections=["sentinel-1-rtc"],
                            bbox=[w, s, e, n],
                            datetime=f"{a.start}/{a.end}").items())
    if not items:
        sys.exit("no Sentinel-1 RTC over that AOI/window — widen the dates or bbox")

    items.sort(key=lambda it: it.properties.get("datetime", ""), reverse=True)
    item = next((it for it in items if a.pol in it.assets), items[0])
    print(f"{len(items)} scene(s); using {item.id}")
    print(f"  acquired {item.properties.get('datetime')}  "
          f"orbit={item.properties.get('sat:orbit_state','?')}")

    href = item.assets[a.pol].href
    with rasterio.open(href) as src:
        if src.crs is None:
            sys.exit("scene has no CRS (raw GRD?) — expected RTC; report this")
        left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, w, s, e, n)
        win = from_bounds(left, bottom, right, top, src.transform)
        print(f"  reading {a.pol.upper()} window, downsampled to ~{a.size}px ...")
        g0 = src.read(1, window=win, out_shape=(a.size, a.size),
                      resampling=Resampling.average).astype(np.float64)
        win_transform = src.window_transform(win)
        sx = g0.shape[1] / max(win.width, 1)
        sy = g0.shape[0] / max(win.height, 1)
        out_transform = win_transform * Affine.scale(1 / sx, 1 / sy)
        out_crs = src.crs

    valid = g0 > 0
    if not valid.any():
        sys.exit("window came back empty (all zero) — AOI may be off the scene footprint")

    # genuine calibration: linear gamma0 -> dB
    db = np.full(g0.shape, np.nan, np.float32)
    db[valid] = (10.0 * np.log10(g0[valid])).astype(np.float32)
    # Fill nodata (scene-edge/off-footprint pixels) with the scene MEDIAN, not the
    # minimum. Filling with a very dark value makes the detector read the nodata
    # border as one giant dark "slick" — a false positive along the scene edge.
    fill = float(np.nanmedian(db[valid]))
    db = np.nan_to_num(db, nan=fill)
    db = np.clip(db, -35.0, 5.0)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with rasterio.open(
        a.out, "w", driver="GTiff",
        height=db.shape[0], width=db.shape[1], count=1, dtype="float32",
        crs=out_crs, transform=out_transform, nodata=None) as dst:
        dst.write(db, 1)

    print(f"\nwrote {a.out}  ({db.shape[1]}x{db.shape[0]} px, calibrated dB, "
          f"range {db.min():.1f}..{db.max():.1f})")
    print("Feed it to the pipeline via:  scripts/run_real.py --scene " + a.out)


if __name__ == "__main__":
    main()
