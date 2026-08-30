# Research notes- SIH 2026 PS 26143 (NTRO)

Background reading behind the design decisions in this repo. Where a choice in
the code departs from the obvious approach, the reason is recorded here.

## 1. Why SAR, and what oil actually looks like to it

Mineral oil damps the short (centimetre-scale) Bragg waves that generate radar
backscatter over water. A slick therefore appears as a **dark patch** in the
normalised radar cross-section (σ⁰). This is a *relative* signature, which has
three consequences the pipeline has to respect:

- **A wind window exists.** Below roughly 3 m/s there are too few Bragg waves
  for the surrounding sea to be bright, so nothing stands out; above roughly
  10–12 m/s wind mixing breaks the slick up and restores backscatter. Outside
  that band a "no detection" result is not evidence of a clean sea. The
  detector carries wind as a feature (`local_wind_proxy`) for exactly this
  reason.
- **Look-alikes dominate the false-positive budget.** Low-wind cells, biogenic
  films (algal/plankton surfactants), rain cells, upwelling, grease ice and
  ship wakes are all dark. The literature consensus (Solberg; Topouzelis;
  Alpers et al. 2017 on look-alikes) is that dark-spot *detection* is easy and
  dark-spot *classification* is the real problem. That is why this repo splits
  the two stages and trains a classifier on segmenter output.
- **Damping saturates.** Beyond roughly a millimetre of thickness the SAR sees
  no further darkening, so contrast-derived thickness is a lower bound for very
  dark slicks- flagged as `saturated` in `characterize.py`.

Sentinel-1 IW GRDH gives ~10 m pixel spacing, ~250 km swath, VV+VH, with an
equivalent number of looks around 4.4- the values the simulator uses.

## 2. Datasets

| Purpose | Source |
|---|---|
| SAR oil-spill segmentation, labelled | Zenodo Sentinel-1 SAR oil-spill dataset- [Part I (train)](https://zenodo.org/records/8346860), [Part II](https://zenodo.org/records/8253899), [Part III (test: 150 oil / 150 look-alike / 150 clean)](https://zenodo.org/records/13761290). 2048×2048×2 σ⁰ dB TIFFs with masks. |
| Raw imagery | Copernicus Data Space Ecosystem (Sentinel-1 GRD, Sentinel-2 for EO cross-check) |
| AIS | [MarineCadastre](https://marinecadastre.gov/accessais/) for the schema and US coverage; Indian-EEZ AIS via NTRO/DG Shipping/ISRO feeds, or terrestrial AIS receivers |
| Currents | [CMEMS GLOBAL_ANALYSISFORECAST_PHY_001_024](https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/services)- the first CMEMS current product to combine general circulation, tides and waves in one field, which matters because oil drift is sensitive to all three |
| Wind | ERA5 single levels (`u10`, `v10`); Sentinel-1-derived wind fields as a same-scene alternative |
| Reference | [Journal of Remote Sensing, "Oil Slick Segmentation Using Deep Learning"](https://spj.science.org/doi/10.34133/remotesensing.0613)- framework for real-world Sentinel-1 application |

`sagar/data/loaders.py` implements the adapters for the first, second and the
CMEMS/ERA5 pair.

## 3. Drift modelling

The standard operational tool is [OpenDrift/OpenOil](https://opendrift.github.io/)
(MET Norway)- a Lagrangian particle model where each parcel carries mass,
density and viscosity and is moved by current advection, wind drift and Stokes
drift with a stochastic term for turbulent diffusion. This repo implements the
same transport equation directly (`sagar/core/drift.py`) rather than depending
on OpenDrift, so the prototype installs with five pure-Python wheels; the
`sample_xy` contract makes swapping in OpenOil a contained change.

Windage (leeway) is the dominant uncertainty for surface oil- commonly quoted
as ~3% of the 10 m wind, but genuinely variable with emulsification and
thickness. The ensemble therefore perturbs it **per particle** (3.0% ± 0.6%)
rather than using a single nominal value.

## 4. Backtracking, and why a backward cloud is not enough

The obvious approach- run the particles backwards and look for where they
converge- works for an *instantaneous point* release. It fails for the case
this problem statement actually cares about: an operational discharge from a
vessel underway, which is a **line source** laid down over tens of minutes to
hours. The slick's along-track extent was present at t=0 and no amount of
backward integration collapses it.

Measured on the reference scenario: backward spread contracts by under 2% over
26 hours, and the minimum-spread instant sits ~5 h from the true release. The
backward-PDF peak lands **~11 km** from the true origin.

So this repo adds **source-term inversion** (`sagar/core/inversion.py`):
hypothesise a moving line source `(t_start, duration, course, speed, x₀, y₀)`,
forward-advect it through the same fields, and score the resulting footprint
against the observed slick by IoU. This is closest in spirit to the
bidirectional-drift ship-tracing method of
[Mar. Pollut. Bull. (2024)](https://www.sciencedirect.com/science/article/abs/pii/S0025326X24007859),
and it yields something a probability blob cannot: **a candidate source track**
that can be matched against AIS in space *and* time.

## 5. AIS and attribution

Prior work on tracing illegal discharges couples SAR detections with AIS
directly- see [Tracing illegal oil discharges from vessels using SAR and AIS
in the Bohai Sea](https://www.sciencedirect.com/science/article/abs/pii/S0964569121002660),
and the AIS-anomaly + SAR-classifier framework surveyed in
[Detecting Oil Spills Using AIS and Satellite Datasets](https://computersciencejournal.org/wp-content/uploads/17.pdf).

Two failure modes recur and both are designed against here:

1. **Proximity-only scoring convicts the nearest ship.** Hence the decoy set in
   `ais.synthesize()`: right place/wrong time, right time/wrong place, and a
   clean transit through the origin. A scorer that cannot separate those is not
   doing attribution.
2. **Dark vessels.** A ship that switches its transponder off during a
   discharge is invisible to AIS-only reasoning. The transponder *gap* is
   itself scored as evidence, and SAR bright-target detection provides the
   independent channel- the same asymmetry exploited in
   [dark ship-to-ship transfer detection](https://arxiv.org/html/2404.07607v1).

Legally, MARPOL Annex I caps operational oily-water discharge at
[15 ppm](https://www.imo.org/en/ourwork/environment/pages/oilpollution-default.aspx),
with stricter rules inside
[Special Areas](https://www.imo.org/en/ourwork/environment/pages/special-areas-marpol.aspx)-
which include the Oman area of the Arabian Sea. EMSA's CleanSeaNet is the
closest operational analogue to this system in Europe. Any output of this
pipeline is an **investigative lead**, not proof: attribution in an enforcement
sense requires corroboration, typically oil fingerprinting against a sample
taken at port state inspection.

## 6. What the honest limitations are

- The classifier is trained on **simulated** scenes. The simulator models the
  right physics (Bragg damping, Gamma speckle, incidence trend, wind cells,
  biogenic films) but real look-alikes are more varied; expect the reported
  separation to degrade on the Zenodo test split. `loaders.py` + the existing
  `train_classifier.py` feature path is the migration route.
- Single-polarisation intensity only. Adding VH and polarimetric features
  (entropy/alpha, co-pol phase difference) is the standard next lever for
  oil-vs-look-alike separation.
- No land/ice masking, no ambiguity or azimuth-shift handling.
- The metocean fields are analytic. Real CMEMS/ERA5 fields have structure the
  inversion will find harder- and the honest test of this design is how much
  the inversion error grows when they are swapped in.
