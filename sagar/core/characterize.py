"""Slick characterisation: thickness class, volume and age.

Three independent age estimators are computed and fused, because each fails in
a different regime and the disagreement between them is itself the honest
uncertainty estimate:

  * **Advective age**- an elongated slick is a trail. Its downstream extent
    divided by the local drift speed is the time since the head was laid down.
    Best for fresh, ship-track-shaped discharges (exactly the SIH case).
  * **Fay spreading age**- inverts the gravity-viscous spreading law for the
    observed area given an estimated volume. Best for instantaneous releases.
  * **Weathering age**- a sheen that has thinned to the point of losing SAR
    contrast is old; damping ratio decays quasi-exponentially with evaporation
    and dispersion.
"""
from __future__ import annotations

import math

# Bonn Agreement Oil Appearance Code -> representative thickness (metres).
BONN_CLASSES = [
    ("sheen",              0.00000005, 0.0000003),
    ("rainbow",            0.0000003,  0.000005),
    ("metallic",           0.000005,   0.00005),
    ("discontinuous true", 0.00005,    0.0002),
    ("continuous true",    0.0002,     0.005),
]

RHO_OIL = 870.0      # kg/m3, typical marine fuel oil
RHO_SEA = 1025.0
NU_SEA = 1.0e-6      # m2/s
G = 9.81


def thickness_from_contrast(contrast_db):
    """Damping contrast -> Bonn appearance class and a thickness estimate.

    Damping saturates: beyond ~1 mm the SAR sees no further darkening, so this
    is a lower bound on thickness for very dark slicks and we say so.
    """
    c = max(contrast_db, 0.0)
    if c < 3.0:
        cls, lo, hi = BONN_CLASSES[0]
    elif c < 5.5:
        cls, lo, hi = BONN_CLASSES[1]
    elif c < 8.0:
        cls, lo, hi = BONN_CLASSES[2]
    elif c < 11.0:
        cls, lo, hi = BONN_CLASSES[3]
    else:
        cls, lo, hi = BONN_CLASSES[4]
    h = math.sqrt(lo * hi)  # geometric mean of the class band
    return dict(bonn_class=cls, thickness_m=h, thickness_lo_m=lo, thickness_hi_m=hi,
                saturated=c >= 11.0)


def volume_estimate(area_km2, thickness):
    a = area_km2 * 1e6
    v = a * thickness["thickness_m"]
    return dict(volume_m3=v,
                volume_lo_m3=a * thickness["thickness_lo_m"],
                volume_hi_m3=a * thickness["thickness_hi_m"],
                tonnes=v * RHO_OIL / 1000.0)


def advective_age_s(length_km, drift_speed_ms):
    if drift_speed_ms <= 0.01:
        return None
    return length_km * 1000.0 / drift_speed_ms


def fay_age_s(area_km2, volume_m3):
    """Invert the Fay gravity-viscous spreading law r = k2 (d g V^2 t^0.5 / nu^0.5)^(1/6)."""
    if volume_m3 <= 0 or area_km2 <= 0:
        return None
    r = math.sqrt(area_km2 * 1e6 / math.pi)
    delta = (RHO_SEA - RHO_OIL) / RHO_SEA
    k2 = 1.45
    denom = delta * G * volume_m3 ** 2 / math.sqrt(NU_SEA)
    if denom <= 0:
        return None
    return ((r / k2) ** 6 / denom) ** 2


def weathering_age_s(contrast_db, wind_speed):
    """Contrast decays as the slick evaporates and disperses; the decay constant
    scales with wind. Returns the time needed to fall from a fresh ~14 dB."""
    fresh = 14.0
    c = max(min(contrast_db, fresh - 0.1), 0.5)
    tau = 9.0 * 3600.0 * (6.0 / max(wind_speed, 1.5))  # e-folding time
    return tau * math.log(fresh / c)


def characterize(detection, forcing, drift_speed_ms):
    th = thickness_from_contrast(detection.features["contrast_db"])
    vol = volume_estimate(detection.area_km2, th)
    ages = {
        "advective_s": advective_age_s(detection.length_km, drift_speed_ms),
        "fay_s": fay_age_s(detection.area_km2, vol["volume_m3"]),
        "weathering_s": weathering_age_s(detection.features["contrast_db"],
                                         forcing.wind_speed),
    }
    vals = [v for v in ages.values() if v and 0 < v < 14 * 24 * 3600]
    if vals:
        # Log-space mean: the estimators can disagree by an order of magnitude.
        logm = sum(math.log(v) for v in vals) / len(vals)
        best = math.exp(logm)
        spread = max(vals) / min(vals) if len(vals) > 1 else 2.0
    else:
        best, spread = 6 * 3600.0, 6.0
    return dict(
        **th, **vol,
        age_estimates_s=ages,
        age_best_s=best,
        age_best_h=best / 3600.0,
        age_uncertainty_factor=spread,
        confidence="high" if spread < 3 else ("medium" if spread < 8 else "low"),
    )
