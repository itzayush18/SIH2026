"""Score held-out scenes with the SHIPPED classifier and cache the predictions.

Builds a labelled corpus the same way scripts/train_classifier.py does (region
label = >50% overlap with the ground-truth slick mask), but from a seed range
the shipped model never saw, then scores it with sagar/data/oil_classifier.json
exactly as sagar/core/detect.py does at inference time.

Output: data/classifier_eval.npz  (X, y, p, feats) -- consumed by make_figures.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sagar.core import detect
from scripts.train_classifier import corpus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "classifier_eval.npz")
MODEL = os.path.join(ROOT, "sagar", "data", "oil_classifier.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=int, default=14)
    ap.add_argument("--size", type=int, default=768)
    # 7000 is well clear of train_classifier.py's default seed0=1000, so these
    # scenes are genuinely unseen by the shipped weights.
    ap.add_argument("--seed0", type=int, default=7000)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    print(f"Generating {a.scenes} held-out scenes (seed0={a.seed0}) ...")
    X, y = corpus(a.scenes, size=a.size, seed0=a.seed0)

    W = json.load(open(MODEL))
    feats = list(detect.FEATURES)
    w = np.array([W["weights"][f] for f in feats])
    mu = np.array([W["mu"].get(f, 0.0) for f in feats])
    sd = np.array([W["sigma"].get(f, 1.0) or 1.0 for f in feats])
    z = (X - mu) / sd
    p = 1.0 / (1.0 + np.exp(-np.clip(z @ w + W["bias"], -40, 40)))

    np.savez(a.out, X=X, y=y, p=p, feats=np.array(feats))
    acc = float(((p > .5) == (y > .5)).mean())
    print(f"{len(y)} regions - {int(y.sum())} oil / {int(len(y)-y.sum())} look-alike")
    print(f"accuracy @0.5 = {acc:.3f}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
