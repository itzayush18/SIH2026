"""Train the oil / look-alike discriminator on the Zenodo Sentinel-1 dataset.

Dataset: "Sentinel-1 SAR Oil spill image dataset for train, validate, and test
deep learning models. Part I"  --  https://zenodo.org/records/8346860

    01_Train_Val_Oil_Spill_images.7z  (40.7 GB)  -> Oil/00000.tif ... 01339.tif
    01_Train_Val_Oil_Spill_mask.7z    (6.2 MB)   -> Mask_oil/00000.tif ...

Layout expected (image and mask basenames match 1:1):
    <images>/00000.tif   2048x2048x2 float32, band0=Sigma0_VH_db band1=Sigma0_VV_db
    <masks>/00000.tif    2048x2048   uint8, 1=oil 0=background

These are SNAP-processed scenes (Orbit -> Thermal Noise Removal -> Calibration ->
Speckle filter -> Terrain Correction -> dB), so the pixel values are already real
Sigma0 decibels.  No rescaling is invented, unlike the 8-bit JPEG chip corpus in
train_on_real_dataset.py.

Why this trains better than the chip script
-------------------------------------------
The chip script cropped one blob per image and asked "is this chip oil?".  Here we
run the *actual inference segmenter* (detect.dark_spot_candidates) over each scene
and label every candidate it produces by its overlap with the ground-truth mask.
So the negatives are precisely the look-alikes the deployed detector really trips
on -- low-wind cells, biogenic films, shadow -- which is the discrimination the
logistic model exists to make.

Usage:
    .venv/bin/python scripts/train_on_zenodo.py --limit 120     # ~quick pass
    .venv/bin/python scripts/train_on_zenodo.py                 # full 1200 scenes
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
import numpy as np
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sagar.core import detect

DEFAULT_IMAGES = "/Volumes/T7/Oil"
DEFAULT_MASKS  = "/Volumes/T7/Mask_oil"
DEFAULT_OUT    = os.path.join(ROOT, "sagar", "data", "oil_classifier.json")

# Terrain-corrected pixel spacing is 8.983152841195215e-05 deg ~= 10 m.
PIXEL_M = 10.0

VV_BAND, VH_BAND = 1, 0

# A candidate counts as oil if this much of it lands inside the truth mask.
IOU_POS = 0.50
# ...and as a clean negative only if it barely touches the mask at all.  The
# band between the two is ambiguous (partial overlap, mask edge slop) and is
# dropped rather than guessed at.
IOU_NEG = 0.05

# Separable halves of the 25x25 halo structuring element (see _region_features_fast).
_V25 = np.ones((25, 1), dtype=bool)
_H25 = np.ones((1, 25), dtype=bool)


def read_scene(path: str, band: int = VV_BAND) -> np.ndarray:
    """Load one polarisation of a 2048x2048x2 float32 dB GeoTIFF."""
    import tifffile
    arr = tifffile.imread(path)
    if arr.ndim == 3:
        arr = arr[..., band]
    return np.asarray(arr, dtype=np.float32)


def read_mask(path: str) -> np.ndarray:
    import tifffile
    return np.asarray(tifffile.imread(path)) > 0


def pair_files(images_dir: str, masks_dir: str) -> list[tuple[str, str, str]]:
    """Match images to masks by basename, skipping macOS ._ resource forks."""
    def listing(d):
        return {f for f in os.listdir(d)
                if f.lower().endswith((".tif", ".tiff")) and not f.startswith("._")}
    imgs, msks = listing(images_dir), listing(masks_dir)
    common = sorted(imgs & msks)
    missing = len(imgs) - len(common)
    if missing:
        print(f"  note: {missing} image(s) have no matching mask -- skipped")
    return [(n, os.path.join(images_dir, n), os.path.join(masks_dir, n)) for n in common]


def _region_features_fast(db, grad, sl, local, pixel_m):
    """Bounding-box port of detect._region_features.

    detect._region_features recomputes np.gradient over the whole 2048x2048
    scene for every region, which costs ~2.6 s each and makes a full training
    run take days.  Here the gradient is computed once per scene by the caller
    and every morphological op runs inside the region's bounding box (padded by
    the 25 px halo structuring element), so the arithmetic is identical but the
    work scales with the region, not the scene.  Verified to match the original
    to ~1e-6 on real scenes.
    """
    PAD = 14  # half of the 25 px halo window, plus slack for the 3x3 dilation
    H, W = db.shape
    r0 = max(sl[0].start - PAD, 0); r1 = min(sl[0].stop + PAD, H)
    c0 = max(sl[1].start - PAD, 0); c1 = min(sl[1].stop + PAD, W)

    # Paste the region's own slice into the padded window; nothing scene-sized
    # is ever allocated.
    sub = np.zeros((r1 - r0, c1 - c0), dtype=bool)
    sub[sl[0].start - r0: sl[0].stop - r0, sl[1].start - c0: sl[1].stop - c0] = local
    dbs = db[r0:r1, c0:c1]
    grs = grad[r0:r1, c0:c1]

    px_km2 = (pixel_m / 1000.0) ** 2
    area_px = int(sub.sum())
    area_km2 = area_px * px_km2

    dil = ndimage.binary_dilation(sub, np.ones((3, 3)))
    border = dil & ~sub
    # A square structuring element is separable, and scipy's generic path for a
    # 25x25 block costs ~40 ms per region against ~3 ms for two 1-D passes.
    # The result is bit-identical.
    halo = ndimage.binary_dilation(
        ndimage.binary_dilation(sub, _V25), _H25) & ~dil
    if halo.sum() < 30:
        # Original falls back to the whole-scene complement; ~mask over the crop
        # is the same set intersected with the crop, which is what the medians
        # below need and keeps the cost bounded.
        halo = ~sub

    inside = dbs[sub]
    outside = dbs[halo]
    contrast = float(np.median(outside) - np.median(inside))

    edge_grad = float(grs[border].mean()) if border.any() else 0.0
    interior_grad = float(grs[sub].mean()) + 1e-6

    perim_px = int(border.sum())
    perimeter_km = perim_px * pixel_m / 1000.0
    complexity = perimeter_km * 1000.0 / (2.0 * math.sqrt(math.pi * max(area_km2, 1e-9) * 1e6))

    rr, cc = np.nonzero(sub)
    rr = rr - rr.mean(); cc = cc - cc.mean()
    cov = np.cov(np.vstack([cc, rr])) if area_px > 3 else np.eye(2)
    ev, _evec = np.linalg.eigh(cov)
    ev = np.clip(ev, 1e-6, None)
    elongation = float(math.sqrt(ev[1] / ev[0]))

    return {
        "contrast_db": contrast,
        "edge_grad": edge_grad,
        "log_area_km2": math.log10(max(area_km2, 1e-4)),
        "complexity": complexity,
        "elongation": elongation,
        "std_db": float(inside.std()),
        "local_wind_proxy": float(np.median(outside)),
        "edge_contrast_ratio": edge_grad / interior_grad,
    }


def features_for_scene(img_path: str, mask_path: str, band: int,
                       min_pixels: int) -> tuple[list, list]:
    """Segment one scene the way inference does, label each candidate by overlap."""
    db = detect.preprocess(read_scene(img_path, band))
    truth = read_mask(mask_path)

    cand = detect.dark_spot_candidates(db, min_pixels=min_pixels)
    lab, n = ndimage.label(cand)
    if n == 0:
        return [], []

    # Computed once per scene rather than once per region -- see _region_features_fast.
    gy, gx = np.gradient(db)
    grad = np.hypot(gx, gy)

    objs = ndimage.find_objects(lab)
    rows, labels = [], []
    for i in range(1, n + 1):
        sl = objs[i - 1]
        if sl is None:
            continue
        local = lab[sl] == i
        area = int(local.sum())
        if area < min_pixels:
            continue
        overlap = float((local & truth[sl]).sum()) / area

        if overlap >= IOU_POS:
            y = 1
        elif overlap <= IOU_NEG:
            y = 0
        else:
            continue  # ambiguous -- do not train on it

        feats = _region_features_fast(db, grad, sl, local, PIXEL_M)
        vals = [feats[k] for k in detect.FEATURES]
        if not all(np.isfinite(v) for v in vals):
            continue
        rows.append(vals)
        labels.append(y)
    return rows, labels


def build_corpus(images_dir: str, masks_dir: str, limit: int | None,
                 band: int, min_pixels: int, seed: int):
    pairs = pair_files(images_dir, masks_dir)
    if not pairs:
        sys.exit(f"No matching image/mask pairs in {images_dir} and {masks_dir}")

    if limit and limit < len(pairs):
        rng = np.random.default_rng(seed)
        idx = sorted(rng.choice(len(pairs), limit, replace=False))
        pairs = [pairs[i] for i in idx]

    print(f"Scenes to process: {len(pairs)}\n")
    X, y, failed = [], [], 0
    t0 = time.time()
    for i, (name, ip, mp) in enumerate(pairs, 1):
        try:
            rows, labels = features_for_scene(ip, mp, band, min_pixels)
            X.extend(rows)
            y.extend(labels)
        except Exception as exc:
            failed += 1
            if failed <= 3:
                print(f"  [skip] {name}: {exc}")
        if i % 20 == 0 or i == len(pairs):
            el = time.time() - t0
            rate = i / max(el, 1e-9)
            eta = (len(pairs) - i) / max(rate, 1e-9)
            npos = int(sum(y))
            print(f"  {i}/{len(pairs)} scenes | regions={len(y)} "
                  f"(oil={npos}, look-alike={len(y)-npos}) | "
                  f"{rate*60:.1f} scenes/min | ETA {eta/60:.1f} min", flush=True)

    if failed:
        print(f"\n  {failed} scene(s) failed to process")
    return np.array(X, dtype=float), np.array(y, dtype=float)


# ---------------------------------------------------------------------------
# Logistic regression -- identical formulation to the other training scripts so
# the emitted JSON stays a drop-in replacement.
# ---------------------------------------------------------------------------

def fit_logistic(X, y, epochs=5000, lr=0.1, l2=1e-3):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    assert not np.isnan(Z).any(), "NaN in standardised feature matrix"

    w = np.zeros(Z.shape[1])
    b = 0.0
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
            print(f"  epoch {ep+1:5d}/{epochs}  weighted-loss={float((loss*cw).mean()):.4f}",
                  flush=True)
    return w, b, mu, sd


def auc(y, p):
    pos, neg = p[y > 0.5], p[y < 0.5]
    if not len(pos) or not len(neg):
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean()
                 + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", default=DEFAULT_IMAGES)
    ap.add_argument("--masks",  default=DEFAULT_MASKS)
    ap.add_argument("--out",    default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only N randomly chosen scenes (smoke test)")
    ap.add_argument("--pol", choices=["VV", "VH"], default="VV",
                    help="Polarisation to train on (VV is standard for slicks)")
    ap.add_argument("--min-pixels", type=int, default=200,
                    help="Drop candidate regions smaller than this")
    ap.add_argument("--epochs", type=int, default=5000)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--l2", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cache", default=None,
                    help="Save/load the extracted feature matrix (.npz) to skip re-segmentation")
    a = ap.parse_args()

    band = VV_BAND if a.pol == "VV" else VH_BAND

    print(f"\n{'='*66}")
    print("  SAGAR-DRISHTI -- Zenodo Sentinel-1 classifier training")
    print(f"  Images : {a.images}")
    print(f"  Masks  : {a.masks}")
    print(f"  Pol    : {a.pol} (band {band})   min region: {a.min_pixels} px")
    print(f"  Output : {a.out}")
    print(f"{'='*66}\n")

    if a.cache and os.path.exists(a.cache):
        z = np.load(a.cache)
        X, y = z["X"], z["y"]
        print(f"Loaded cached features from {a.cache}\n")
    else:
        X, y = build_corpus(a.images, a.masks, a.limit, band, a.min_pixels, a.seed)
        if a.cache:
            os.makedirs(os.path.dirname(os.path.abspath(a.cache)) or ".", exist_ok=True)
            np.savez_compressed(a.cache, X=X, y=y)
            print(f"\nCached features -> {a.cache}")

    n_oil, n_look = int(y.sum()), int(len(y) - y.sum())
    print(f"\nCorpus: {len(y)} regions | oil={n_oil}  look-alike={n_look}\n")
    if n_oil < 20 or n_look < 20:
        sys.exit("Not enough samples in one class -- widen --limit or lower --min-pixels.")

    rng = np.random.default_rng(a.seed)
    idx = rng.permutation(len(y))
    split = int(0.75 * len(y))
    tr, te = idx[:split], idx[split:]
    print(f"Train: {len(tr)}  |  Test: {len(te)}\n")

    print("Fitting logistic regression ...")
    w, b, mu, sd = fit_logistic(X[tr], y[tr], a.epochs, a.lr, a.l2)

    def prob(Xin):
        return 1.0 / (1.0 + np.exp(-np.clip(((Xin - mu) / sd) @ w + b, -40, 40)))

    ptr, pte = prob(X[tr]), prob(X[te])
    tr_acc, te_acc = float((np.round(ptr) == y[tr]).mean()), float((np.round(pte) == y[te]).mean())
    tr_auc, te_auc = auc(y[tr], ptr), auc(y[te], pte)

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
    print(f"\n  Precision={prec:.3f}  Recall={rec:.3f}  F1={f1:.3f}\n")

    print("  Learned weights (standardised units):")
    for k, v in sorted(zip(detect.FEATURES, w), key=lambda kv: -abs(kv[1])):
        print(f"    {k:22s} {v:+.4f}")

    model = dict(
        bias=float(b),
        weights={k: float(v) for k, v in zip(detect.FEATURES, w)},
        mu={k: float(v) for k, v in zip(detect.FEATURES, mu)},
        sigma={k: float(v) for k, v in zip(detect.FEATURES, sd)},
        n_train=int(len(tr)),
        test_auc=float(te_auc),
        test_acc=float(te_acc),
        test_f1=float(f1),
        trained_on=("Zenodo 8346860 -- Sentinel-1 SAR Oil Spill Dataset Part I "
                    f"({a.pol}, {len(y)} regions from segmented scenes)"),
    )
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(model, f, indent=2)
    print(f"\nSaved -> {a.out}\n")


if __name__ == "__main__":
    main()
