"""Fit the oil / look-alike discriminator.

Generates a corpus of simulated scenes with randomised wind, slick geometry and
look-alike population, runs the *same* segmentation stage used at inference,
labels each candidate region by its overlap with the ground-truth slick, and
fits a standardised logistic regression by gradient descent.

Training on segmenter output (rather than on hand-cut chips) is deliberate: the
classifier only ever sees the feature distribution it will face in production,
including the segmenter's own leakage and bleed.

    python scripts/train_classifier.py --scenes 24
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sagar.core import detect, scenario
from sagar.core.geoutil import Origin

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "sagar", "data", "oil_classifier.json")


def corpus(n_scenes, size=768, seed0=1000):
    X, y = [], []
    rng = np.random.default_rng(seed0)
    for i in range(n_scenes):
        origin = Origin(lat=float(rng.uniform(15.0, 22.0)), lon=float(rng.uniform(69.0, 74.0)))
        scene, _, _ = scenario.build(
            origin, seed=seed0 + i, size=size, pixel_m=60.0,
            release_h_ago=float(rng.uniform(6.0, 20.0)),
            discharge_h=float(rng.uniform(0.6, 2.4)),
            course=float(rng.uniform(0, 360)),
            speed_kn=float(rng.uniform(4.0, 11.0)))
        db = detect.preprocess(scene.sigma0_db, looks=scene.spec.looks)
        cand = detect.dark_spot_candidates(db)
        lab, n = ndimage.label(cand)
        for k in range(1, n + 1):
            mask = lab == k
            f, _ = detect._region_features(db, mask, scene.spec.pixel_m)
            overlap = (mask & scene.truth_mask).sum() / max(mask.sum(), 1)
            X.append([f[c] for c in detect.FEATURES])
            y.append(1 if overlap > 0.5 else 0)
        print(f"  scene {i+1}/{n_scenes}: {n} candidates, "
              f"{sum(y[-n:]) if n else 0} oil", flush=True)
    return np.array(X, float), np.array(y, float)


def fit(X, y, epochs=4000, lr=0.15, l2=1e-3):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    w = np.zeros(Z.shape[1])
    b = 0.0
    # Class weights: look-alike regions vastly outnumber oil regions.
    pos = max(y.sum(), 1.0); neg = max(len(y) - y.sum(), 1.0)
    cw = np.where(y > 0.5, len(y) / (2 * pos), len(y) / (2 * neg))
    for _ in range(epochs):
        p = 1.0 / (1.0 + np.exp(-np.clip(Z @ w + b, -40, 40)))
        g = (p - y) * cw
        w -= lr * (Z.T @ g / len(y) + l2 * w)
        b -= lr * g.mean()
    return w, b, mu, sd


def auc(y, p):
    pos, neg = p[y > 0.5], p[y < 0.5]
    if not len(pos) or not len(neg):
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean()
                 + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=int, default=16)
    ap.add_argument("--size", type=int, default=768)
    a = ap.parse_args()

    print(f"Generating {a.scenes} scenes ...")
    X, y = corpus(a.scenes, size=a.size)
    print(f"{len(y)} candidate regions, {int(y.sum())} oil / {int(len(y)-y.sum())} look-alike")
    if y.sum() < 3 or len(y) - y.sum() < 3:
        sys.exit("not enough of both classes — increase --scenes")

    rng = np.random.default_rng(0)
    idx = rng.permutation(len(y))
    split = int(0.75 * len(y))
    tr, te = idx[:split], idx[split:]

    w, b, mu, sd = fit(X[tr], y[tr])
    ptr = 1 / (1 + np.exp(-(((X[tr] - mu) / sd) @ w + b)))
    pte = 1 / (1 + np.exp(-(((X[te] - mu) / sd) @ w + b)))
    print(f"train acc {(np.round(ptr)==y[tr]).mean():.3f}  AUC {auc(y[tr],ptr):.3f}")
    print(f" test acc {(np.round(pte)==y[te]).mean():.3f}  AUC {auc(y[te],pte):.3f}")

    model = dict(bias=float(b),
                 weights={k: float(v) for k, v in zip(detect.FEATURES, w)},
                 mu={k: float(v) for k, v in zip(detect.FEATURES, mu)},
                 sigma={k: float(v) for k, v in zip(detect.FEATURES, sd)},
                 n_train=int(len(tr)),
                 test_auc=float(auc(y[te], pte)),
                 test_acc=float((np.round(pte) == y[te]).mean()))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(model, f, indent=2)
    print("wrote", OUT)
    for k, v in sorted(model["weights"].items(), key=lambda kv: -abs(kv[1])):
        print(f"  {k:22s} {v:+.3f}")


if __name__ == "__main__":
    main()
