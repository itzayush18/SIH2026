"""Run a trained U-Net segmenter (from scripts/train_unet.py) on a Scene and
return detections in the SAME format as `sagar.core.detect.detect`, so the rest
of the pipeline (characterise / drift / invert / attribute) is unchanged.

The U-Net was trained on Zenodo 8-bit SAR images normalised to 0-1. Pipeline
scenes are sigma0 in dB (~ -35..5), so we bridge with the same robust min-max
normalisation the dashboard's SAR PNG uses — turning dB into the 0-1 range the
network expects. This is a pragmatic bridge, not a guarantee the two intensity
distributions match exactly; validate IoU on a labelled real scene before
trusting the numbers.

Usage:
    from sagar.core import unet_detect
    dets, labels = unet_detect.detect(scene, "data/models/unet_v1.pt",
                                      prob_threshold=0.5)
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import detect as _detect
from .detect import Detection

_MODEL_CACHE = {}


def _norm01(db):
    """dB array -> 0..1 via robust 2/98 percentile stretch (matches the SAR PNG)."""
    lo, hi = np.percentile(db, 2), np.percentile(db, 98)
    if hi <= lo:
        lo, hi = float(db.min()), float(db.max() or 1.0)
    return np.clip((db - lo) / (hi - lo + 1e-9), 0.0, 1.0).astype(np.float32)


def _load(model_path):
    if model_path in _MODEL_CACHE:
        return _MODEL_CACHE[model_path]
    import torch
    import segmentation_models_pytorch as smp
    ckpt = torch.load(model_path, map_location="cpu")
    channels = ckpt.get("channels", 1)
    size = ckpt.get("size", 512)
    model = smp.Unet(encoder_name="resnet34", encoder_weights=None,
                     in_channels=channels, classes=1, activation=None)
    model.load_state_dict(ckpt["model"])
    model.eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev)
    out = (model, channels, size, dev, torch)
    _MODEL_CACHE[model_path] = out
    return out


def probability_map(scene, model_path):
    """Per-pixel oil probability at the scene's native resolution."""
    model, channels, size, dev, torch = _load(model_path)
    from PIL import Image
    x01 = _norm01(scene.sigma0_db)
    H, W = x01.shape
    img = np.array(Image.fromarray((x01 * 255).astype(np.uint8)).resize(
        (size, size), Image.BILINEAR)).astype(np.float32) / 255.0
    t = torch.from_numpy(img)[None, None].to(dev)
    if channels > 1:
        t = t.repeat(1, channels, 1, 1)
    with torch.no_grad():
        prob = torch.sigmoid(model(t))[0, 0].cpu().numpy()
    # back to native scene size
    return np.array(Image.fromarray((prob * 255).astype(np.uint8)).resize(
        (W, H), Image.BILINEAR)).astype(np.float32) / 255.0


def detect(scene, model_path, prob_threshold=0.5, min_pixels=150):
    """U-Net detections in detect.detect's (list[Detection], label_array) format."""
    prob = probability_map(scene, model_path)
    binary = prob >= prob_threshold
    binary = ndimage.binary_opening(binary, np.ones((3, 3)))   # drop specks
    lab, n = ndimage.label(binary)
    out = []
    for i in range(1, n + 1):
        mask = lab == i
        if int(mask.sum()) < min_pixels:
            continue
        feats, geom = _detect._region_features(
            _detect.preprocess(scene.sigma0_db, looks=scene.spec.looks),
            mask, scene.spec.pixel_m)
        p = float(prob[mask].mean())              # learned confidence for the region
        r0, c0 = ndimage.center_of_mass(mask)
        lat, lon = scene.latlon_of_pixel(r0, c0)
        out.append(Detection(
            id=f"SLK-{i:03d}", mask_index=i, features=feats, p_oil=p,
            area_km2=geom["area_km2"], perimeter_km=geom["perimeter_km"],
            centroid_rc=(float(r0), float(c0)), centroid_lonlat=(float(lon), float(lat)),
            orientation_deg=geom["orientation_deg"], length_km=geom["length_km"],
            width_km=geom["width_km"], contour_lonlat=_detect._contour_lonlat(scene, mask)))
    out.sort(key=lambda d: -d.area_km2)
    return out, lab
