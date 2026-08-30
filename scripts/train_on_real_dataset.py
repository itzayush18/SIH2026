"""Train the oil / look-alike discriminator on the Kaggle Sentinel-1 dataset.

Dataset layout expected:
    data/dataset/data/Class_0/class_0_XXXXX.jpg   <- no-oil / look-alike (3695 images)
    data/dataset/data/Class_1/class_1_XXXXX.jpg   <- confirmed oil spill (1843 images)

Each image is a 400x400 RGB JPEG chip from a Sentinel-1 IW GRDH scene.
We convert to grayscale dB, run the exact same feature extractor used at
inference (detect._region_features), then fit the same logistic model so the
saved json is a drop-in replacement for the simulated one.

Usage:
    .venv/Scripts/python scripts/train_on_real_dataset.py                 # full run
    .venv/Scripts/python scripts/train_on_real_dataset.py --max-per-class 200  # quick test
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sagar.core import detect

DEFAULT_DATASET = os.path.join(ROOT, "data", "dataset", "data")
DEFAULT_OUT     = os.path.join(ROOT, "sagar", "data", "oil_classifier.json")

# Approximate pixel spacing for these 400x400 chips (Sentinel-1 IW GRDH ~10 m,
# but chips are likely sub-sampled; 60 m gives sensible area values).
PIXEL_M = 60.0


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def jpg_to_db(path: str) -> np.ndarray:
    """Load a JPEG chip and return float32 in simulated dB units.

    Pixel 0 -> -20 dB (dark sea / shadow), pixel 255 -> +5 dB (bright).
    This matches the Sentinel-1 IW VV dynamic range and preserves contrast.
    """
    from PIL import Image
    arr = np.array(Image.open(path).convert("L"), dtype=np.float32)
    return arr / 255.0 * 25.0 - 20.0   # [-20, +5] dB


# ---------------------------------------------------------------------------
# Feature extraction from a pre-cropped chip
# ---------------------------------------------------------------------------

def extract_features_from_chip(db: np.ndarray) -> dict | None:
    """Preprocess + segment + extract the 8 physics features for one chip.

    Key design decisions:
      - We must always have pixels *outside* the mask so the contrast and
        local_wind_proxy features can compare inside vs outside.  We cap the
        mask to at most 80% of the image so there is always a valid halo.
      - If no dark region found (very uniform chip), we create a central
        50x50 mask so the chip still produces a feature row (it will score
        near zero on contrast and edge, correctly flagging it as a look-alike).
      - NaN results propagate to the caller, which drops those rows.
    """
    # 1. Same preprocessing as inference
    db_pp = detect.preprocess(db, looks=4.4)

    # 2. Adaptive threshold on the chip
    med = float(np.median(db_pp))
    mad = float(np.median(np.abs(db_pp - med))) * 1.4826
    thresh = med - 0.8 * max(mad, 0.3)
    mask = db_pp < thresh

    # Morphological cleanup
    mask = ndimage.binary_opening(mask, np.ones((3, 3)))
    mask = ndimage.binary_closing(mask, np.ones((5, 5)))
    mask = ndimage.binary_fill_holes(mask)

    total_px = db_pp.size

    # If mask is too small, use a central square (low-contrast chip)
    if mask.sum() < 50:
        h, w = db_pp.shape
        cy, cx = h // 2, w // 2
        r = 25
        mask = np.zeros_like(mask)
        mask[cy-r:cy+r, cx-r:cx+r] = True

    # Cap mask to 80% of image so the halo is never empty
    if mask.sum() > 0.80 * total_px:
        # Erode until <= 80%
        struct = np.ones((7, 7))
        tmp = mask.copy()
        for _ in range(20):
            tmp = ndimage.binary_erosion(tmp, struct)
            if tmp.sum() <= 0.80 * total_px and tmp.sum() >= 50:
                mask = tmp
                break
        else:
            # Fallback: just blank the border 15px
            mask2 = np.zeros_like(mask)
            mask2[15:-15, 15:-15] = mask[15:-15, 15:-15]
            if mask2.sum() >= 50:
                mask = mask2

    # Keep only the largest connected component
    labeled, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, labeled, range(1, n + 1))
        mask = labeled == (int(np.argmax(sizes)) + 1)

    feats, _ = detect._region_features(db_pp, mask, PIXEL_M)

    # Sanity check: reject if any feature is NaN/Inf
    if any(not np.isfinite(v) for v in feats.values()):
        return None

    return feats


# ---------------------------------------------------------------------------
# Build corpus
# ---------------------------------------------------------------------------

def build_corpus(dataset_dir: str, max_per_class: int | None = None,
                 seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)

    def collect(folder: str, label: int, limit: int | None):
        paths = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif"))
        ])
        if limit and len(paths) > limit:
            idx = rng.choice(len(paths), limit, replace=False)
            paths = [paths[i] for i in sorted(idx)]

        rows, labels, skipped = [], [], 0
        for i, p in enumerate(paths):
            try:
                feats = extract_features_from_chip(jpg_to_db(p))
                if feats is None:
                    skipped += 1
                    continue
                rows.append([feats[k] for k in detect.FEATURES])
                labels.append(label)
            except Exception as exc:
                skipped += 1
                if skipped <= 3:
                    print(f"  [skip] {os.path.basename(p)}: {exc}", flush=True)
            if (i + 1) % 300 == 0:
                print(f"    {i+1}/{len(paths)} processed ({skipped} skipped)", flush=True)

        print(f"  class {label}: {len(rows)} ok, {skipped} dropped", flush=True)
        return rows, labels

    c0 = os.path.join(dataset_dir, "Class_0")
    c1 = os.path.join(dataset_dir, "Class_1")
    assert os.path.isdir(c0), f"Missing: {c0}"
    assert os.path.isdir(c1), f"Missing: {c1}"

    print("Loading Class_0 (look-alike / no-oil) ...", flush=True)
    r0, l0 = collect(c0, 0, max_per_class)
    print("Loading Class_1 (oil spill) ...", flush=True)
    r1, l1 = collect(c1, 1, max_per_class)

    X = np.array(r0 + r1, dtype=float)
    y = np.array(l0 + l1, dtype=float)

    assert not np.isnan(X).any(), "BUG: NaN survived into feature matrix"
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


# ---------------------------------------------------------------------------
# Logistic regression (dependency-free, mirrors train_classifier.py)
# ---------------------------------------------------------------------------

def fit_logistic(X: np.ndarray, y: np.ndarray,
                 epochs: int = 5000, lr: float = 0.1, l2: float = 1e-3):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd

    # Verify no NaN made it through
    assert not np.isnan(Z).any(), "NaN in standardised feature matrix"

    w = np.zeros(Z.shape[1])
    b = 0.0

    # Inverse-frequency class weights
    pos = max(float(y.sum()), 1.0)
    neg = max(float(len(y) - y.sum()), 1.0)
    cw = np.where(y > 0.5, len(y) / (2 * pos), len(y) / (2 * neg))

    for ep in range(epochs):
        logit = np.clip(Z @ w + b, -40, 40)
        p = 1.0 / (1.0 + np.exp(-logit))
        g = (p - y) * cw
        w -= lr * (Z.T @ g / len(y) + l2 * w)
        b -= lr * g.mean()
        if (ep + 1) % 1000 == 0:
            loss = -(y * np.log(p + 1e-9) + (1 - y) * np.log(1 - p + 1e-9))
            print(f"  epoch {ep+1:5d}/{epochs}  "
                  f"weighted-loss={float((loss * cw).mean()):.4f}", flush=True)
    return w, b, mu, sd


def auc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = p[y > 0.5], p[y < 0.5]
    if not len(pos) or not len(neg):
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean()
                 + 0.5 * (pos[:, None] == neg[None, :]).mean())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=DEFAULT_DATASET,
                    help="Folder containing Class_0/ and Class_1/ subfolders")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="Output JSON path for the classifier")
    ap.add_argument("--max-per-class", type=int, default=None,
                    help="Cap images per class (e.g. 200 for a quick smoke test)")
    ap.add_argument("--epochs", type=int, default=5000)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--l2", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    print(f"\n{'='*62}")
    print("  SAGAR-DRISHTI -- real-data classifier training")
    print(f"  Dataset : {a.dataset}")
    print(f"  Output  : {a.out}")
    print(f"{'='*62}\n")

    # 1. Build corpus
    X, y = build_corpus(a.dataset, max_per_class=a.max_per_class, seed=a.seed)
    n_oil = int(y.sum())
    n_look = int(len(y) - y.sum())
    print(f"\nCorpus: {len(y)} samples | oil={n_oil}  look-alike={n_look}\n")

    if n_oil < 5 or n_look < 5:
        sys.exit("Not enough samples in one class -- check --dataset path.")

    # 2. 75/25 split
    rng = np.random.default_rng(a.seed)
    idx = rng.permutation(len(y))
    split = int(0.75 * len(y))
    tr, te = idx[:split], idx[split:]
    print(f"Train: {len(tr)}  |  Test: {len(te)}\n")

    # 3. Fit
    print("Fitting logistic regression ...")
    w, b, mu, sd = fit_logistic(X[tr], y[tr], a.epochs, a.lr, a.l2)

    # 4. Evaluate
    def prob(Xin):
        return 1.0 / (1.0 + np.exp(-np.clip(((Xin - mu) / sd) @ w + b, -40, 40)))

    ptr, pte = prob(X[tr]), prob(X[te])
    tr_acc  = float((np.round(ptr) == y[tr]).mean())
    te_acc  = float((np.round(pte) == y[te]).mean())
    tr_auc  = auc(y[tr], ptr)
    te_auc  = auc(y[te], pte)

    tp = int(((np.round(pte) == 1) & (y[te] == 1)).sum())
    fp = int(((np.round(pte) == 1) & (y[te] == 0)).sum())
    fn = int(((np.round(pte) == 0) & (y[te] == 1)).sum())
    tn = int(((np.round(pte) == 0) & (y[te] == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec  = tp / max(tp + fn, 1)
    f1   = 2 * prec * rec / max(prec + rec, 1e-9)

    print(f"\n  train  acc={tr_acc:.3f}  AUC={tr_auc:.3f}")
    print(f"   test  acc={te_acc:.3f}  AUC={te_auc:.3f}")
    print(f"\n  Confusion matrix (test set):")
    print(f"               Pred Oil  Pred Look-alike")
    print(f"  True Oil        {tp:4d}       {fn:4d}")
    print(f"  True Look-alike {fp:4d}       {tn:4d}")
    print(f"\n  Precision={prec:.3f}  Recall={rec:.3f}  F1={f1:.3f}")

    # 5. Save model (same schema as the simulated model)
    model = dict(
        bias=float(b),
        weights={k: float(v) for k, v in zip(detect.FEATURES, w)},
        mu={k: float(v) for k, v in zip(detect.FEATURES, mu)},
        sigma={k: float(v) for k, v in zip(detect.FEATURES, sd)},
        n_train=int(len(tr)),
        test_auc=float(te_auc),
        test_acc=float(te_acc),
        test_f1=float(f1),
        trained_on="Kaggle Sentinel-1 SAR Oil Spill Detection Dataset (CSIRO)",
    )
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(model, f, indent=2)
    print(f"\nWrote --> {a.out}")

    print("\nFeature weights (sorted by |weight|):")
    for k, v in sorted(model["weights"].items(), key=lambda kv: -abs(kv[1])):
        bar = "+" * min(int(abs(v) * 8), 40)
        print(f"  {k:24s}  {v:+.3f}  {bar}")

    print(f"\n{'='*62}")
    print("  Done. Run `python scripts/run_demo.py` to verify the pipeline.")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
