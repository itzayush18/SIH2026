"""Generate the five standard AI/ML figures from THIS project's real outputs.

Every number plotted here comes from artefacts the pipeline actually produced:
  - data/validation.json         : 10-seed batch validation run
  - data/out/*/report.json       : real incident reports (detections + suspects)
  - sagar/data/oil_classifier.json : the shipped classifier, trained on Zenodo
Nothing is invented, mocked, or hand-tuned for presentation.

Usage:  .venv/bin/python scripts/make_figures.py
Output: figures/*.png
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

INK, MUTED, GRID = "#1a1a1a", "#6b7280", "#e5e7eb"
OIL, LOOK, ACCENT = "#0f766e", "#c2410c", "#1d4ed8"

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160,
    "font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7,
    "axes.axisbelow": True, "figure.facecolor": "white",
})


def _style(ax, title, sub=None):
    ax.set_title(title, fontweight="bold", pad=14 if sub else 8, loc="left")
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8.5,
                color=MUTED, va="bottom")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _save(fig, name):
    p = os.path.join(FIG, name)
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote figures/{name}")
    return p


def load_reports():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "out", "*", "report.json"))):
        try:
            out.append(json.load(open(f)))
        except Exception:
            continue
    return out


# ---------------------------------------------------------------- 1 · line
def fig_line(val):
    """Per-seed metric trajectory across the 10-run validation batch."""
    runs = sorted(val["runs"], key=lambda r: r["seed"])
    seeds = [r["seed"] for r in runs]
    iou = [r["iou"] for r in runs]
    f1 = [r["f1"] for r in runs]
    inv = [r["inversion_iou"] for r in runs]

    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.plot(seeds, f1, "-o", color=OIL, lw=2, ms=5, label="Segmentation F1")
    ax.plot(seeds, iou, "-o", color=ACCENT, lw=2, ms=5, label="Segmentation IoU")
    ax.plot(seeds, inv, "-o", color=LOOK, lw=2, ms=5, label="Source-inversion IoU")
    ax.axhline(np.mean(f1), color=OIL, ls=":", lw=1.2, alpha=.7)
    ax.set_xlabel("Validation seed"); ax.set_ylabel("Score")
    ax.set_ylim(0, 1.02); ax.set_xticks(seeds)
    ax.legend(frameon=False, fontsize=8.5, loc="lower left", ncol=3)
    _style(ax, "Detection quality across 10 independent scenes",
           f"data/validation.json · mean F1 = {np.mean(f1):.3f}, "
           f"mean IoU = {np.mean(iou):.3f}")
    return _save(fig, "1_line_metrics_per_seed.png")


# ----------------------------------------------------------------- 2 · bar
def fig_bar(val, reports):
    """Left: attribution vs the proximity baseline. Right: learned feature weights."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.2, 4.2))

    b = val["baseline"]
    labels = ["Top-1", "Top-3"]
    ours = [b["ours_top1"] * 100, b["ours_top3"] * 100]
    prox = [b["proximity_top1"] * 100, b["proximity_top3"] * 100]
    x = np.arange(2); w = 0.36
    r1 = a1.bar(x - w/2, ours, w, color=OIL, label="Six-axis attribution")
    r2 = a1.bar(x + w/2, prox, w, color=MUTED, label="Nearest-vessel baseline")
    for r in list(r1) + list(r2):
        a1.text(r.get_x() + r.get_width()/2, r.get_height() + 2,
                f"{r.get_height():.0f}%", ha="center", fontsize=9, color=INK)
    a1.set_xticks(x); a1.set_xticklabels(labels); a1.set_ylim(0, 126)
    a1.set_ylabel("Correct attribution (%)")
    a1.legend(frameon=False, fontsize=8.5, loc="upper center",
              bbox_to_anchor=(0.5, 1.0), ncol=1)
    _style(a1, "Attribution vs baseline", f"n = {val['n']} scenes, ground truth known")

    W = json.load(open(os.path.join(ROOT, "sagar", "data", "oil_classifier.json")))
    it = sorted(W["weights"].items(), key=lambda kv: kv[1])
    names = [k for k, _ in it]; vals = [v for _, v in it]
    cols = [OIL if v > 0 else LOOK for v in vals]
    a2.barh(names, vals, color=cols)
    a2.axvline(0, color=MUTED, lw=1)
    a2.set_xlabel("Logistic weight (standardised features)")
    _style(a2, "What the classifier learned",
           f"trained on {W['n_train']:,} real Sentinel-1 regions")
    fig.tight_layout()
    return _save(fig, "2_bar_attribution_and_weights.png")


# ----------------------------------------------------------- 3 · histogram
def fig_hist(reports, ev):
    """Left: slick areas from real incidents. Right: classifier score separation."""
    areas = [d["area_km2"] for r in reports for d in r["detections"]]
    y, p = ev["y"], ev["p"]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.2, 4.2))
    a1.hist(areas, bins=12, color=ACCENT, edgecolor="white", lw=.8)
    a1.axvline(float(np.median(areas)), color=LOOK, ls="--", lw=1.6,
               label=f"median {np.median(areas):.1f} km²")
    a1.set_xlabel("Slick area (km²)"); a1.set_ylabel("Detections")
    a1.legend(frameon=False, fontsize=8.5)
    _style(a1, "Detected slick area distribution",
           f"{len(areas)} detections across {len(reports)} incidents")

    bins = np.linspace(0, 1, 21)
    a2.hist(p[y < .5], bins=bins, color=LOOK, alpha=.75, edgecolor="white",
            lw=.6, label=f"look-alike (n={int((y<.5).sum())})")
    a2.hist(p[y > .5], bins=bins, color=OIL, alpha=.75, edgecolor="white",
            lw=.6, label=f"oil (n={int((y>.5).sum())})")
    a2.axvline(0.5, color=INK, ls="--", lw=1.4, label="decision threshold")
    a2.set_xlabel("P(oil)"); a2.set_ylabel("Regions")
    a2.legend(frameon=False, fontsize=8.5)
    _style(a2, "Classifier score distribution",
           "held-out synthetic scenes - Zenodo-trained model over-predicts oil")
    fig.tight_layout()
    return _save(fig, "3_histogram_areas_and_scores.png")


# ------------------------------------------------------------- 4 · scatter
def fig_scatter(ev, reports):
    """Left: the single most-separating feature vs P(oil). Right: real detections."""
    X, y, p, feats = ev["X"], ev["y"], ev["p"], list(ev["feats"])
    i = feats.index("contrast_db")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.2, 4.2))
    a1.scatter(X[y < .5, i], p[y < .5], s=34, color=LOOK, alpha=.75,
               edgecolor="white", lw=.6, label="look-alike")
    a1.scatter(X[y > .5, i], p[y > .5], s=34, color=OIL, alpha=.75,
               edgecolor="white", lw=.6, label="oil")
    a1.axhline(0.5, color=INK, ls="--", lw=1.2)
    a1.set_xlabel("Damping contrast (dB)"); a1.set_ylabel("P(oil)")
    a1.set_ylim(-.04, 1.04); a1.legend(frameon=False, fontsize=8.5, loc="center right")
    r = float(np.corrcoef(X[:, i], p)[0, 1])
    _style(a1, "Contrast drives the decision", f"Pearson r = {r:.2f}, n = {len(y)} regions")

    ar = np.array([d["area_km2"] for r_ in reports for d in r_["detections"]])
    po = np.array([d["p_oil"] for r_ in reports for d in r_["detections"]])
    ln = np.array([d["length_km"] for r_ in reports for d in r_["detections"]])
    sc = a2.scatter(ar, po, s=28 + 3.2 * ln, c=ln, cmap="viridis",
                    alpha=.85, edgecolor="white", lw=.6)
    a2.set_xscale("log")
    a2.set_xlabel("Slick area (km², log)"); a2.set_ylabel("P(oil)")
    fig.colorbar(sc, ax=a2, label="slick length (km)", pad=.02)
    _style(a2, "Real incident detections", f"{len(ar)} detections, all above threshold")
    fig.tight_layout()
    return _save(fig, "4_scatter_feature_vs_probability.png")


# ------------------------------------------------------ 5 · confusion matrix
def fig_confusion(ev):
    y, p = ev["y"], ev["p"]
    pred = (p > 0.5).astype(int); true = (y > 0.5).astype(int)
    tn = int(((pred == 0) & (true == 0)).sum()); fp = int(((pred == 1) & (true == 0)).sum())
    fn = int(((pred == 0) & (true == 1)).sum()); tp = int(((pred == 1) & (true == 1)).sum())
    cm = np.array([[tn, fp], [fn, tp]])

    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    acc = (tp + tn) / cm.sum()

    fig, ax = plt.subplots(figsize=(5.6, 4.9))
    ax.imshow(cm, cmap="Blues", vmin=0, vmax=cm.max())
    names = [["TN", "FP"], ["FN", "TP"]]
    for i in range(2):
        for j in range(2):
            dark = cm[i, j] > cm.max() * 0.55
            ax.text(j, i - .10, f"{cm[i,j]}", ha="center", va="center",
                    fontsize=23, fontweight="700", color="white" if dark else INK)
            ax.text(j, i + .22, names[i][j], ha="center", va="center",
                    fontsize=10, color="white" if dark else MUTED)
    ax.set_xticks([0, 1], ["look-alike", "oil"])
    ax.set_yticks([0, 1], ["look-alike", "oil"])
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.grid(False)
    _style(ax, "Oil vs look-alike confusion matrix",
           f"acc {acc:.2f} · precision {prec:.2f} · recall {rec:.2f} · F1 {f1:.2f}"
           f"   |   real-SAR model on synthetic scenes (domain gap)")
    fig.tight_layout()
    return _save(fig, "5_confusion_matrix.png")


def main():
    val = json.load(open(os.path.join(ROOT, "data", "validation.json")))
    reports = load_reports()
    cache = os.environ.get("EVAL_NPZ", os.path.join(ROOT, "data", "classifier_eval.npz"))
    if not os.path.exists(cache):
        sys.exit(f"missing {cache} - run scripts/eval_classifier.py first")
    ev = np.load(cache, allow_pickle=True)

    print(f"Sources: validation n={val['n']}, reports={len(reports)}, "
          f"eval regions={len(ev['y'])}")
    fig_line(val)
    fig_bar(val, reports)
    fig_hist(reports, ev)
    fig_scatter(ev, reports)
    fig_confusion(ev)
    print(f"\nAll five figures in {FIG}/")


if __name__ == "__main__":
    main()
