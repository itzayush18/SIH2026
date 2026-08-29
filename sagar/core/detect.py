"""Dark-spot detection and oil/look-alike discrimination on SAR sigma0.

Three stages, mirroring the operational literature (Solberg et al.; Topouzelis):

  1. **Preprocess** — refined-Lee speckle filter, then remove the range-dependent
     incidence-angle trend so a single threshold is valid across the swath.
  2. **Segment** — adaptive local thresholding at several window scales, union of
     scales, morphological cleanup, connected components. Deliberately
     over-detects: recall here is cheap, precision is stage 3's job.
  3. **Classify** — per-region feature vector -> logistic model -> P(oil).
     The features are the classical discriminators: contrast, edge sharpness,
     shape complexity, homogeneity and local wind. A look-alike (low-wind cell,
     biogenic film) is dark but *soft-edged, low-contrast and blobby*; mineral
     oil is dark, *sharp-edged and geometrically complex*.

The model coefficients live in `sagar/data/oil_classifier.json`, fit by
`scripts/train_classifier.py`. If the file is missing we fall back to
physically-signed priors so the pipeline still runs end to end.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from typing import List

import numpy as np
from scipy import ndimage

FEATURES = [
    "contrast_db",      # background dB - region mean dB  (oil: large)
    "edge_grad",        # mean |grad| on the region border (oil: sharp)
    "log_area_km2",
    "complexity",       # P / (2*sqrt(pi*A)); 1 = circle
    "elongation",       # major/minor axis of the inertia ellipse
    "std_db",           # internal homogeneity
    "local_wind_proxy", # background level -> wind; oil needs 3-12 m/s to show
    "edge_contrast_ratio",
]

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "oil_classifier.json")

# Sign-correct fallback so a fresh clone works before training.
_FALLBACK = dict(
    bias=-1.35,
    weights=dict(contrast_db=0.62, edge_grad=0.55, log_area_km2=0.30,
                 complexity=0.85, elongation=0.40, std_db=-0.45,
                 local_wind_proxy=0.25, edge_contrast_ratio=0.50),
    mu={k: 0.0 for k in FEATURES},
    sigma={k: 1.0 for k in FEATURES},
)


@dataclass
class Detection:
    id: str
    mask_index: int
    features: dict
    p_oil: float
    area_km2: float
    perimeter_km: float
    centroid_rc: tuple
    centroid_lonlat: tuple
    orientation_deg: float
    length_km: float
    width_km: float
    contour_lonlat: list

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------- preprocess
def lee_filter(img, size=7, looks=4.4):
    """Multiplicative-noise Lee filter. Preserves the slick edges the
    classifier depends on, unlike a plain box blur."""
    mean = ndimage.uniform_filter(img, size)
    sq = ndimage.uniform_filter(img * img, size)
    var = np.clip(sq - mean * mean, 0, None)
    noise_var = mean * mean / looks
    k = var / (var + noise_var + 1e-9)
    return mean + k * (img - mean)


def detrend_incidence(db):
    """Fit and remove the along-range (column) brightness ramp."""
    cols = np.arange(db.shape[1], dtype=float)
    prof = np.median(db, axis=0)
    coef = np.polyfit(cols, prof, 2)
    return db - np.polyval(coef, cols)[None, :] + float(np.median(prof))


def preprocess(sigma0_db, looks=4.4):
    lin = np.power(10.0, sigma0_db / 10.0)
    filt = lee_filter(lin, size=7, looks=looks)
    db = 10.0 * np.log10(np.clip(filt, 1e-7, None))
    return detrend_incidence(db)


# ------------------------------------------------------------------ segment
def dark_spot_candidates(db, scales=(81, 201, 501), k=1.6, k_global=1.9, min_pixels=150):
    """Union of multi-scale adaptive thresholds plus a global one, then cleanup.

    The scale set has to bracket the slick: a window smaller than the feature
    sits *inside* it, the local mean tracks the slick itself and the contrast
    vanishes. The global term catches basin-scale slicks larger than every
    window; the small windows catch thin filaments the global term misses.
    """
    cand = np.zeros(db.shape, dtype=bool)
    med = float(np.median(db))
    mad = float(np.median(np.abs(db - med))) * 1.4826
    cand |= db < (med - k_global * mad)
    for w in scales:
        m = ndimage.uniform_filter(db, w)
        s = np.sqrt(np.clip(ndimage.uniform_filter(db * db, w) - m * m, 0, None))
        cand |= db < (m - k * s)
    cand = ndimage.binary_opening(cand, np.ones((3, 3)))
    cand = ndimage.binary_closing(cand, np.ones((7, 7)))
    cand = ndimage.binary_fill_holes(cand)
    lab, nlab = ndimage.label(cand)
    if nlab:
        sizes = ndimage.sum(cand, lab, range(1, nlab + 1))
        for i, sz in enumerate(sizes, start=1):
            if sz < min_pixels:
                cand[lab == i] = False
    return cand


# ------------------------------------------------------------------ features
def _region_features(db, mask, pixel_m):
    px_km2 = (pixel_m / 1000.0) ** 2
    area_px = int(mask.sum())
    area_km2 = area_px * px_km2

    dil = ndimage.binary_dilation(mask, np.ones((3, 3)))
    border = dil & ~mask
    halo = ndimage.binary_dilation(mask, np.ones((25, 25))) & ~dil
    if halo.sum() < 30:
        halo = ~mask

    inside = db[mask]
    outside = db[halo]
    contrast = float(np.median(outside) - np.median(inside))

    gy, gx = np.gradient(db)
    grad = np.hypot(gx, gy)
    edge_grad = float(grad[border].mean()) if border.any() else 0.0
    interior_grad = float(grad[mask].mean()) + 1e-6

    perim_px = int(border.sum())
    perimeter_km = perim_px * pixel_m / 1000.0
    complexity = perimeter_km * 1000.0 / (2.0 * math.sqrt(math.pi * max(area_km2, 1e-9) * 1e6))

    rr, cc = np.nonzero(mask)
    rr = rr - rr.mean(); cc = cc - cc.mean()
    cov = np.cov(np.vstack([cc, rr])) if area_px > 3 else np.eye(2)
    ev, evec = np.linalg.eigh(cov)
    ev = np.clip(ev, 1e-6, None)
    elongation = float(math.sqrt(ev[1] / ev[0]))
    orient = float((math.degrees(math.atan2(evec[1, 1], evec[0, 1])) + 360) % 180)
    length_km = 4.0 * math.sqrt(ev[1]) * pixel_m / 1000.0
    width_km = 4.0 * math.sqrt(ev[0]) * pixel_m / 1000.0

    feats = {
        "contrast_db": contrast,
        "edge_grad": edge_grad,
        "log_area_km2": math.log10(max(area_km2, 1e-4)),
        "complexity": complexity,
        "elongation": elongation,
        "std_db": float(inside.std()),
        "local_wind_proxy": float(np.median(outside)),
        "edge_contrast_ratio": edge_grad / interior_grad,
    }
    geom = dict(area_km2=area_km2, perimeter_km=perimeter_km, orientation_deg=orient,
                length_km=length_km, width_km=width_km)
    return feats, geom


def _contour_lonlat(scene, mask, max_pts=180):
    """Border pixels ordered by angle about the centroid — good enough for a
    map overlay and far cheaper than a full marching-squares trace."""
    border = ndimage.binary_dilation(mask, np.ones((3, 3))) & ~mask
    rr, cc = np.nonzero(border)
    if len(rr) == 0:
        return []
    r0, c0 = rr.mean(), cc.mean()
    ang = np.arctan2(rr - r0, cc - c0)
    order = np.argsort(ang)
    rr, cc = rr[order], cc[order]
    if len(rr) > max_pts:
        idx = np.linspace(0, len(rr) - 1, max_pts).astype(int)
        rr, cc = rr[idx], cc[idx]
    out = []
    for r, c in zip(rr, cc):
        lat, lon = scene.latlon_of_pixel(r, c)
        out.append([float(lon), float(lat)])
    return out


# ---------------------------------------------------------------- classifier
def load_model():
    try:
        with open(os.path.abspath(_MODEL_PATH)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return _FALLBACK


def score(feats, model=None):
    m = model or load_model()
    z = m["bias"]
    for k in FEATURES:
        mu = m["mu"].get(k, 0.0)
        sd = m["sigma"].get(k, 1.0) or 1.0
        z += m["weights"][k] * ((feats[k] - mu) / sd)
    return float(1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, z)))))


# ------------------------------------------------------------------ pipeline
def detect(scene, p_threshold=0.5, model=None) -> List[Detection]:
    db = preprocess(scene.sigma0_db, looks=scene.spec.looks)
    cand = dark_spot_candidates(db)
    lab, n = ndimage.label(cand)
    model = model or load_model()
    out = []
    for i in range(1, n + 1):
        mask = lab == i
        feats, geom = _region_features(db, mask, scene.spec.pixel_m)
        p = score(feats, model)
        if p < p_threshold:
            continue
        r0, c0 = ndimage.center_of_mass(mask)
        lat, lon = scene.latlon_of_pixel(r0, c0)
        out.append(Detection(
            id=f"SLK-{i:03d}", mask_index=i, features=feats, p_oil=p,
            area_km2=geom["area_km2"], perimeter_km=geom["perimeter_km"],
            centroid_rc=(float(r0), float(c0)), centroid_lonlat=(float(lon), float(lat)),
            orientation_deg=geom["orientation_deg"], length_km=geom["length_km"],
            width_km=geom["width_km"], contour_lonlat=_contour_lonlat(scene, mask)))
    out.sort(key=lambda d: -d.area_km2)
    return out, lab


def evaluate(pred_mask, truth_mask):
    """IoU / precision / recall for the detection stage."""
    inter = float((pred_mask & truth_mask).sum())
    union = float((pred_mask | truth_mask).sum())
    p = inter / max(float(pred_mask.sum()), 1.0)
    r = inter / max(float(truth_mask.sum()), 1.0)
    return dict(iou=inter / max(union, 1.0), precision=p, recall=r,
                f1=2 * p * r / max(p + r, 1e-9))
