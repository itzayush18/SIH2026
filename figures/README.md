# Figures

The five standard AI/ML plots, generated **from this project's own outputs**.
No mock data, no illustrative numbers, no hand-tuned benchmark values.

Regenerate:

```bash
.venv/bin/python scripts/eval_classifier.py   # ~2 min, writes data/classifier_eval.npz
.venv/bin/python scripts/make_figures.py      # writes figures/*.png
```

## Data provenance

| Source | What it provides |
|---|---|
| `data/validation.json` | 10-seed batch validation (seeds 11…74), ground truth known |
| `data/out/*/report.json` | 7 real incident reports — 26 detections, 37 ranked suspects |
| `sagar/data/oil_classifier.json` | shipped classifier: 11,013 regions, Zenodo 8346860 Sentinel-1 |
| `data/classifier_eval.npz` | 63 held-out regions (seed0=7000, unseen), scored by the shipped model |

## The figures

**1 · Line — `1_line_metrics_per_seed.png`**
Segmentation F1, segmentation IoU and source-inversion IoU per validation seed.
Mean F1 = 0.813, mean IoU = 0.699. Trend/variance across independent scenes.

**2 · Bar — `2_bar_attribution_and_weights.png`**
Left: six-axis attribution 100% top-1 vs the nearest-vessel baseline at 0%
(top-3: 100% vs 30%) — the headline result, on ground truth.
Right: the eight learned logistic weights. `log_area_km2` and `contrast_db`
push toward oil; `complexity` and `local_wind_proxy` push toward look-alike.

**3 · Histogram — `3_histogram_areas_and_scores.png`**
Left: slick-area distribution over 26 real detections (median 28.9 km²,
right-skewed). Right: P(oil) distribution by true class.

**4 · Scatter — `4_scatter_feature_vs_probability.png`**
Left: damping contrast vs P(oil), coloured by true label (Pearson r = 0.28).
Right: area vs P(oil) for real detections, sized/coloured by slick length.

**5 · Confusion matrix — `5_confusion_matrix.png`**
TN 2 · FP 30 · FN 0 · TP 31 — accuracy 0.52, precision 0.51, **recall 1.00**.

### Reading figures 3–5 honestly

The classifier is trained on **real Sentinel-1 imagery** (Zenodo 8346860) but
these held-out scenes are **synthetic**. On its own real-data test split it
scores AUC 0.959 / accuracy 0.923 (recorded in `oil_classifier.json`). Here it
catches every true slick (recall 1.00) but flags most look-alikes as oil too —
30 false positives.

That is a **domain gap**, not a coding error: synthetic look-alikes do not
reproduce the backscatter statistics the model learned from real SAR. The
scoring path was verified identical to `sagar/core/detect.py::score()` to
2.2e-16. It is shown as measured rather than swapped for a flattering split —
a confusion matrix earns its place precisely by exposing this.

To plot the model in its own domain, download the Zenodo set
(`gpu/get_zenodo.sh`) and score its held-out split.
