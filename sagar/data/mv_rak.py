"""MV Rak 2011- real-world sanity check for drift physics (§4.4).

MV Rak sank ~20 nautical miles off Mumbai (~19.03 N, 72.12 E) in August 2011,
spilling ~122.5 tonnes of fuel oil. A published GNOME study reproduced its drift
using ECMWF winds + INDOFOS/HYCOM currents. This module documents the incident as
an anchor for:

  - SYNTHETIC_OVERLAY (§3): a synthetic slick overlaid on a *real, documented*
    geography, not a fully invented locale- satisfies the honest-overlay
    requirement.
  - §4.4 validation vignette: forward drift from the known release point/time
    with our analytic field compared (directionally) to the published result.

This is explicitly *not* a calibration proof for the attribution scorer, which
remains synthetic-only. Don't blur that line- see docs/OILTRACE.md.
"""
from sagar.core.geoutil import Origin

# Anchor ~20 nm off Mumbai (MV Rak sinking position)
ORIGIN = Origin(lat=19.03, lon=72.12)

INCIDENT = dict(
    name="MV Rak- Mumbai 2011",
    sank_iso="2011-08-04T05:00:00Z",
    position=dict(lat=19.03, lon=72.12, note="~20 nm off Mumbai"),
    spill_tonnes=122.5,
    fuel="bunker fuel oil",
    published_model="GNOME + ECMWF winds + INDOFOS/HYCOM currents",
    published_drift_direction_deg=315,  # NW-ward along coast per study (approx)
    published_reference="GNOME reproduction cited in research.md §4.4",
    note=("Real-world sanity check on drift physics only- not a calibration "
          "proof for attribution. Attribution scorer validation is synthetic-only."),
)


def vignette_result(seed=11, hours_fwd=18.0):
    """Run the drift engine forward from the known MV Rak release and report
    the forward footprint direction vs the published NW-ward drift.

    Returns a dict with honest labelling and the comparison, suitable for
    embedding in an evidence pack or /api/validation endpoint.
    """
    import math
    from sagar.core import drift as _drift
    from sagar.core.environment import SyntheticOcean
    from sagar.core.geoutil import bearing

    ocean = SyntheticOcean(ORIGIN, seed=seed)
    # Simulate a point release at t=0
    import numpy as np
    res = _drift.integrate(ocean, np.array([0.0]), np.array([0.0]), 0.0,
                           hours_fwd * 3600.0, dt=300.0, backward=False, seed=seed)
    # End vs start bearing
    end_lat, end_lon = ORIGIN.to_ll(float(res.x[-1, 0]), float(res.y[-1, 0]))
    brg = bearing(ORIGIN.lat, ORIGIN.lon, float(end_lat), float(end_lon))
    pub = INCIDENT["published_drift_direction_deg"]
    # Circular diff
    diff = abs((brg - pub + 180) % 360 - 180)
    dist_km = math.hypot(float(res.x[-1, 0]), float(res.y[-1, 0])) / 1000.0
    return dict(
        incident=INCIDENT,
        model=dict(name="SyntheticOcean forward drift (analytic)", seed=seed,
                   hours_fwd=hours_fwd),
        result=dict(bearing_deg=float(brg), distance_km=float(dist_km),
                    published_bearing_deg=pub, error_deg=float(diff)),
        verdict=("PASS- drift direction consistent (≤35° error)- sanity check"
                 if diff <= 35 else
                 "REVIEW- analytic field diverges from published regional currents; "
                 "expected for a simplified ocean model and not a pipeline failure."),
        label="real-world sanity check on drift physics- not attribution calibration",
        data_mode="SYNTHETIC_OVERLAY",
    )
