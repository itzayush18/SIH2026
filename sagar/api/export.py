"""Turn a pipeline result into web-ready artefacts: one JSON report plus a
handful of PNG overlays that Leaflet can drape on the map.

Rasters go out as PNGs with explicit lat/lon bounds rather than as GeoJSON
polygons — a 1024x1024 density field is far cheaper to ship as an image, and
the browser gets smooth interpolation for free.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage


def _norm8(a, lo=None, hi=None):
    lo = np.percentile(a, 2) if lo is None else lo
    hi = np.percentile(a, 98) if hi is None else hi
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)


def write_sar_png(scene, path):
    img = (_norm8(scene.sigma0_db) * 255).astype(np.uint8)
    Image.fromarray(img, mode="L").save(path)


def write_mask_png(mask, path, rgb=(255, 64, 64), alpha=120):
    h, w = mask.shape
    out = np.zeros((h, w, 4), np.uint8)
    edge = ndimage.binary_dilation(mask, np.ones((5, 5))) & ~ndimage.binary_erosion(
        mask, np.ones((5, 5)))
    out[mask] = (*rgb, alpha)
    out[edge] = (*rgb, 255)
    Image.fromarray(out, mode="RGBA").save(path)


_HEAT = np.array([
    (0, 0, 0, 0), (33, 25, 120, 90), (60, 90, 200, 140), (40, 180, 190, 180),
    (120, 220, 120, 200), (245, 220, 90, 225), (240, 130, 40, 240), (200, 30, 30, 255),
], float)


def _colormap(v):
    """v in 0..1 -> RGBA, linear interpolation through a perceptual-ish ramp."""
    x = np.clip(v, 0, 1) * (len(_HEAT) - 1)
    i = np.clip(x.astype(int), 0, len(_HEAT) - 2)
    f = (x - i)[..., None]
    return (_HEAT[i] * (1 - f) + _HEAT[i + 1] * f).astype(np.uint8)


def write_density_png(density_2d, path, gamma=0.45):
    d = density_2d / max(density_2d.max(), 1e-12)
    d = np.power(d, gamma)
    img = _colormap(d)
    # numpy row 0 is the top of the image, which is the *north* edge; the
    # histogram's row 0 is the south edge, so flip.
    Image.fromarray(img[::-1], mode="RGBA").save(path)


def pdf_bounds(pdf):
    o = pdf["origin"]
    s, w = o.to_ll(pdf["xedges"][0], pdf["yedges"][0])
    n, e = o.to_ll(pdf["xedges"][-1], pdf["yedges"][-1])
    return [[s, w], [n, e]]


def _cloud_snapshots(res, hours, every_h=1.0, max_pts=320):
    """Particle cloud as thinned point sets at a few times, for animation."""
    out = []
    step_s = every_h * 3600.0
    dt = abs(res.times[1] - res.times[0]) if len(res.times) > 1 else 300.0
    stride = max(1, int(step_s / dt))
    for k in range(0, len(res.times), stride):
        lat, lon = res.latlon_at(k)
        idx = np.linspace(0, lat.size - 1, min(max_pts, lat.size)).astype(int)
        out.append(dict(t_rel_h=float(res.times[k] / 3600.0),
                        points=[[float(lon[i]), float(lat[i])] for i in idx]))
    return out


def _clean(o):
    """NaN/Infinity are valid Python floats but not valid JSON — the browser's
    JSON.parse rejects them outright. Map them to null on the way out."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def build(result, outdir, epoch_iso="2026-03-14T06:00:00"):
    os.makedirs(outdir, exist_ok=True)
    scene = result["scene"]
    top = result["detections"][0]
    pdf = result["pdf"]

    write_sar_png(scene, os.path.join(outdir, "sar.png"))
    write_mask_png(result["mask"], os.path.join(outdir, "slick.png"))
    write_density_png(pdf["density"].sum(axis=0), os.path.join(outdir, "origin.png"))

    # Per-release-time slices of the origin field. Scrubbing the timeline then
    # answers "if the release happened *then*, where was it?" instead of only
    # showing the time-integrated blur.
    slices = []
    group = max(1, int(round(2 * 3600.0 / pdf["time_bin_s"])))   # ~2 h per slice
    nb = pdf["density"].shape[0]
    for g0 in range(0, nb, group):
        chunk = pdf["density"][g0:g0 + group]
        if chunk.sum() <= 0:
            continue
        name = f"origin_t{len(slices):02d}.png"
        write_density_png(chunk.sum(axis=0), os.path.join(outdir, name))
        slices.append(dict(png=name,
                           t_from_h=float(pdf["t_centers"][g0] / 3600.0),
                           t_to_h=float(pdf["t_centers"][min(g0 + group, nb) - 1] / 3600.0),
                           weight=float(chunk.sum())))

    s, w, n, e = scene.bounds
    report = dict(
        generated_for=epoch_iso,
        scene=dict(bounds=[[s, w], [n, e]], size=scene.spec.size,
                   pixel_m=scene.spec.pixel_m, looks=scene.spec.looks,
                   mean_wind_ms=scene.meta.get("mean_wind"),
                   center=dict(lat=scene.spec.origin.lat, lon=scene.spec.origin.lon),
                   sar_png="sar.png", slick_png="slick.png"),
        detections=[d.to_dict() for d in result["detections"]],
        characterization=result["characterization"],
        origin_pdf=dict(png="origin.png", bounds=pdf_bounds(pdf), slices=slices,
                        t_centers_h=[float(t / 3600.0) for t in pdf["t_centers"]],
                        cell_m=pdf["cell_m"]),
        origin_peak=result["peak"],
        source=dict(result["source"].to_dict(scene.spec.origin),
                    search_dispersion=result["source_dispersion"]),
        hindcast=_cloud_snapshots(result["back"], None),
        forecast=_cloud_snapshots(result["fwd"], None),
        vessels=[dict(mmsi=v.mmsi, name=v.name, type=v.type_name,
                      length=v.length, track=v.track_geojson(),
                      t_span=[float(v.sorted_pings()[0].t), float(v.sorted_pings()[-1].t)],
                      gaps=[[float(a), float(b)] for a, b in v.gaps()])
                 for v in result["vessels"].values() if v.pings],
        suspects=[s_.to_dict() for s_ in result["suspects"]],
        validation=result["validation"],
    )
    report = _clean(report)
    with open(os.path.join(outdir, "report.json"), "w") as f:
        json.dump(report, f, indent=2, allow_nan=False, default=float)
    return report
