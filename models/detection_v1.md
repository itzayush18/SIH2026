# Oil Spill Detection Model — v1 (Placeholder)

## Model Identity

| Field | Value |
|-------|-------|
| Name | OilTrace Detection v1 |
| Version | stub_v0 |
| Task | Binary segmentation (oil vs. non-oil) |
| Architecture | TBD (likely U-Net variant or Mask R-CNN) |
| Input | Sentinel-1 GRD (VV+VH), 10m resolution |
| Output | Binary mask + confidence map |

## Intended Use

Detect oil spills on ocean surfaces from SAR imagery. Designed to work with
Sentinel-1 IW GRD products in the Indian Ocean / Arabian Sea region.

## Training Data

TBD — will use labelled spill events from INCOIS, EMSA CleanSeaNet, and
manually annotated Sentinel-1 scenes.

## Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| IoU (oil class) | ≥ 0.70 | TBD |
| Precision | ≥ 0.85 | TBD |
| Recall | ≥ 0.80 | TBD |
| F1 | ≥ 0.82 | TBD |

## Limitations

- Not trained yet — this is a scaffold placeholder.
- Look-alikes (biogenic slicks, wind shadows, low-wind zones) will be a
  significant source of false positives.
- Performance will degrade in high sea states (> Beaufort 5).

## Ethical Considerations

Model output supports an **evidence index** for vessel attribution. It is
**NOT** a probability or guilt determination. All downstream use must respect
this constraint (see `SCORE_TYPE` constant in `packages/schemas/models.py`).
