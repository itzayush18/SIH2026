"""Patrol / response recommendation — spec §25.

Emphatically NOT tactical interception guidance. Spec §66 explicitly forbids
that. What we return is a prioritised list of decision-support suggestions:
where to look, at what asset class, and why. The reasoning is written out so an
operations centre can accept, reject or escalate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict


class _NS(dict):
    """dict with attribute access, so patrol.py can read `.p_oil` on the
    exported dict form without the caller unwrapping every field."""
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)


@dataclass
class PatrolTask:
    id: str
    priority: str          # "P1" | "P2" | "P3"
    action: str            # "MONITOR" | "OBSERVE" | "INVESTIGATE" | "PREPARE_RESPONSE"
    asset_class: str       # "SATELLITE" | "AIRCRAFT" | "DRONE" | "PATROL_VESSEL" | "SHORE_TEAM"
    target: str
    lat: float
    lon: float
    radius_km: float
    eta_hint: str
    reason: str

    def dict(self):
        return asdict(self)


def recommend(rep, jurisdiction, coast_km, coast_name):
    """Produce ~4-6 tasks covering: source zone monitoring, prime-suspect
    shadowing, coast preparation and (if MARPOL Special Area) escalation.

    Consumes the exported (dict) form of the report — dataclasses would work
    too but the dict is what /api/incidents/{id}/patrol already ships.
    """
    top = _NS(rep["detections"][0])
    src = _NS(rep["source"])
    disp = rep["source"].get("search_dispersion", {})
    tasks = []
    n = 1

    # Task 1: keep eyes on the reconstructed source corridor.
    tasks.append(PatrolTask(
        f"P-{n:03d}", "P1", "OBSERVE", "SATELLITE",
        target=f"Reconstructed source corridor — release window "
               f"{src.t_start/3600:+.1f} to {(src.t_start+src.duration)/3600:+.1f} h",
        lat=src.start_lat, lon=src.start_lon,
        radius_km=max(6.0, disp.get("position_sd_km", 3.0) * 3.0),
        eta_hint="task next Sentinel-1 pass",
        reason="A repeat SAR acquisition in the source corridor confirms or refutes "
               "the inversion and tightens the release window.")); n += 1

    # Task 2: shadow the prime suspect if attribution is confident.
    if rep["suspects"] and rep["suspects"][0]["score"] >= .6:
        s = _NS(rep["suspects"][0])
        pos = s.track[-1] if s.track else None
        lat = pos[1] if pos else src.start_lat
        lon = pos[0] if pos else src.start_lon
        tasks.append(PatrolTask(
            f"P-{n:03d}", "P1", "INVESTIGATE", "PATROL_VESSEL",
            target=f"Prime attribution candidate — {s.name} (MMSI {s.mmsi})",
            lat=lat, lon=lon, radius_km=25.0,
            eta_hint="dispatch nearest available surface asset",
            reason="Multi-factor attribution score {:.2f} with corroborating behaviour. "
                   "Boarding decision requires port state cooperation and oil "
                   "fingerprinting — this task is intelligence-gathering, not "
                   "interception.".format(s.score))); n += 1
    # (variable `s` above shadows the loop-less scope intentionally — the
    # prime-suspect block runs at most once.)

    # Task 3: coastal preparation, scaled by proximity.
    if coast_km < 80:
        pri = "P1" if coast_km < 30 else "P2"
        tasks.append(PatrolTask(
            f"P-{n:03d}", pri, "PREPARE_RESPONSE", "SHORE_TEAM",
            target=f"Coastal watch — {coast_name} ({coast_km:.0f} km away)",
            lat=top.centroid_lonlat[1], lon=top.centroid_lonlat[0],
            radius_km=coast_km,
            eta_hint="pre-position containment booms",
            reason="Forecast drift places the slick within landfall range within "
                   "24 h. Mobilise the local response chain now, not after landfall.")); n += 1

    # Task 4: aerial confirmation.
    tasks.append(PatrolTask(
        f"P-{n:03d}", "P2", "OBSERVE", "AIRCRAFT",
        target="Aerial visual confirmation over slick centroid",
        lat=top.centroid_lonlat[1], lon=top.centroid_lonlat[0],
        radius_km=max(top.length_km, 15.0),
        eta_hint="next tasking window",
        reason="Independent optical confirmation moves the incident from "
               "'SAR-classified' to 'visually confirmed'."))
    n += 1

    if jurisdiction.marpol_regime == "special_area":
        tasks.insert(0, PatrolTask(
            f"P-{n:03d}", "P1", "MONITOR", "SHORE_TEAM",
            target=f"MARPOL Special Area escalation — {jurisdiction.name}",
            lat=top.centroid_lonlat[1], lon=top.centroid_lonlat[0], radius_km=1.0,
            eta_hint="immediate paperwork",
            reason="A discharge inside the Oman Area is subject to the stricter "
                   "MARPOL regime. Notify DG Shipping and the appropriate port "
                   "state through standard channels."))

    return [t.dict() for t in tasks]
