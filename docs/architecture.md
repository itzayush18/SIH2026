# Architecture

```
                    ┌─────────────────────────────────────────────┐
  Sentinel-1 GRD ──▶│ 1. PREPROCESS   Lee speckle filter          │
  (or simulator)    │                 incidence-trend removal     │
                    └────────────────────┬────────────────────────┘
                                         ▼
                    ┌─────────────────────────────────────────────┐
                    │ 2. SEGMENT      multi-scale adaptive        │
                    │                 threshold + global MAD      │
                    │                 → dark-spot candidates      │
                    └────────────────────┬────────────────────────┘
                                         ▼
                    ┌─────────────────────────────────────────────┐
                    │ 3. CLASSIFY     8 physical features →       │
                    │                 logistic model → P(oil)     │
                    │                 rejects look-alikes         │
                    └────────────────────┬────────────────────────┘
                                         ▼
        ┌────────────────────────────────┴──────────────────────────────┐
        ▼                                                               ▼
┌────────────────────────┐                        ┌────────────────────────────────┐
│ 4. CHARACTERISE        │   CMEMS currents ────▶ │ 5a. HINDCAST (backward cloud)  │
│  Bonn class, thickness │   ERA5 winds           │     → space-time origin PDF    │
│  volume, 3 age models  │                        │ 5b. INVERT (source-term)       │
└────────────────────────┘                        │     → moving line source       │
                                                  │ 5c. FORECAST (forward cloud)   │
                                                  └───────────────┬────────────────┘
                                                                  ▼
   AIS (MarineCadastre schema) ──▶ ┌──────────────────────────────────────────────┐
                                   │ 6. ATTRIBUTE                                 │
                                   │    filter irrelevant traffic                 │
                                   │    6 evidence axes → logistic score          │
                                   │    ranked suspects + written justification   │
                                   └───────────────────┬──────────────────────────┘
                                                       ▼
                                   ┌──────────────────────────────────────────────┐
                                   │ 7. REPORT   report.json + PNG overlays        │
                                   │             Leaflet operations dashboard      │
                                   └──────────────────────────────────────────────┘
```

## Module map

| Module | Role |
|---|---|
| `sagar/core/geoutil.py` | equirectangular ENU ↔ WGS84, bearings; array-aware |
| `sagar/core/environment.py` | `SyntheticOcean` — analytic currents (mean + M2 tide + two eddies) and wind |
| `sagar/core/sarsim.py` | Sentinel-1-like σ⁰ simulator: CMOD-like background, Gamma speckle, damping patches, **two look-alike classes**, bright targets |
| `sagar/core/scenario.py` | ground truth built *by the same physics the pipeline inverts* |
| `sagar/core/detect.py` | preprocess → segment → classify; `evaluate()` for IoU/P/R/F1 |
| `sagar/core/characterize.py` | Bonn thickness class, volume, three fused age estimators |
| `sagar/core/drift.py` | RK2 Lagrangian ensemble, forward and backward; origin PDF |
| `sagar/core/inversion.py` | source-term inversion → moving line source + `source_track_match` |
| `sagar/core/ais.py` | MarineCadastre CSV I/O, track interpolation, gap detection, traffic synthesis with decoys |
| `sagar/core/attribute.py` | six-axis suspect scoring with per-term written evidence |
| `sagar/core/pipeline.py` | orchestration + self-validation against ground truth |
| `sagar/api/export.py` | `report.json` + PNG overlays (NaN-safe) |
| `sagar/data/loaders.py` | Zenodo TIFF, georeferenced GeoTIFF, CMEMS/ERA5 NetCDF adapters |
| `web/index.html` | Leaflet operations dashboard |

## The two contracts

Everything algorithmic depends on exactly two interfaces, which is what makes
the swap from simulator to operational data a configuration change:

```python
scene.sigma0_db                 # ndarray, dB
scene.latlon_of_pixel(r, c)     # → (lat, lon)
ocean.sample_xy(t, x, y)        # → (u_cur, v_cur, u_wind, v_wind), all ndarray
```

`SyntheticOcean` and `NetCDFOcean` both satisfy the second; `simulate()` and
`load_zenodo_tiff()`/`load_geotiff()` both produce the first.

## Design decisions worth defending

**Segmentation deliberately over-detects.** Recall at stage 2 is cheap; a slick
missed there can never be recovered. Precision is stage 3's job, and stage 3 is
trained on stage 2's actual output so it sees the real feature distribution.

**The scale set brackets the slick.** A threshold window smaller than the
feature sits *inside* it, the local mean tracks the slick itself and the
contrast vanishes — this cost 98% of recall before it was fixed. The global MAD
term catches slicks larger than every window; the small windows catch filaments
the global term misses.

**Source-term inversion, not just a backward cloud.** See
[research.md §4](research.md#4-backtracking-and-why-a-backward-cloud-is-not-enough).
The backward PDF is still computed and still used — it is the robust fallback
and it defines the AIS search window — but the sharp estimate comes from
inverting a *moving line source*, which also yields a track to match against AIS.

**Attribution is additive log-odds with published weights.** Every term is
reported alongside a sentence of justification. An analyst can see that a vessel
scored 0.94 because of source-track coincidence and a speed drop, not because a
neural network said so. `prior` (vessel type/size) carries the smallest weight
by design: it must never be able to convict on its own.

**Three age estimators, fused in log space, with their disagreement reported.**
Advective, Fay-spreading and weathering ages fail in different regimes; the
spread between them *is* the uncertainty, surfaced as `age_uncertainty_factor`.
