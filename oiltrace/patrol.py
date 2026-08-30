"""Patrol / response recommendation- spec §25.

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


# Representative Indian Coast Guard / response assets- demo only.
# Coordinates are public approximate station locations; not operationally sensitive.
# Used to turn "dispatch nearest asset" from vague prose into an ETA an analyst
# can act on, per §4.6. Do not use for tactical planning; source: public ICG district listings.
ICG_STATIONS = [
    ("ICG Mumbai (Worli)", 19.02, 72.81, "ICG West- Maharashtra"),
    ("ICG Porbandar", 21.64, 69.60, "ICG North-West- Gujarat"),
    ("ICG Kochi (Fort Kochi)", 9.96, 76.24, "ICG South-West- Kerala"),
    ("ICG Chennai (Royapuram)", 13.11, 80.30, "ICG East- Tamil Nadu"),
    ("ICG Visakhapatnam", 17.69, 83.23, "ICG East- Andhra"),
    ("ICG Port Blair", 11.64, 92.74, "ICG A&N- Andaman"),
    ("ICG Karwar", 14.81, 74.12, "ICG West- Karnataka"),
    ("ICG Daman", 20.42, 72.85, "ICG North-West- Daman"),
    ("ICG Paradip", 20.26, 86.61, "ICG East- Odisha"),
]

# Typical platform speeds for ETA math (conservative, publicly quoted)
# SATELLITE is not a transit asset- no finite speed; handled as special case.
_SPEED_KN = {"PATROL_VESSEL": 18.0, "AIRCRAFT": 140.0, "DRONE": 45.0,
             "SHORE_TEAM": 35.0, "SATELLITE": None}


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    import math as _m
    p1 = _m.radians(lat1); p2 = _m.radians(lat2)
    dp = p2 - p1; dl = _m.radians(lon2 - lon1)
    a = _m.sin(dp/2)**2 + _m.cos(p1)*_m.cos(p2)*_m.sin(dl/2)**2
    return 2*R*_m.asin(_m.sqrt(a))


def _nearest_asset(lat, lon, asset_class="PATROL_VESSEL"):
    best = None; best_km = 1e9
    for name, la, lo, region in ICG_STATIONS:
        d = _haversine_km(lat, lon, la, lo)
        if d < best_km:
            best_km = d; best = (name, la, lo, region)
    # ETA from nearest station at platform speed
    kn = _SPEED_KN.get(asset_class, 18.0)
    if kn is None:
        eta = "next orbital pass- check Sentinel-1 acquisition plan"
        return dict(station=best[0], region=best[3], station_lat=best[1], station_lon=best[2],
                    distance_km=round(best_km, 1), speed_kn=None, eta=eta)
    # 1 km = 0.53996 nm; hours = nm / kn
    nm = best_km * 0.53996
    hrs = nm / max(float(kn), 1.0)
    if hrs < 1:
        eta = f"~{int(hrs*60)} min from {best[0]} ({best_km:.0f} km @ {kn:.0f} kn)"
    elif hrs < 8:
        eta = f"~{hrs:.1f} h from {best[0]} ({best_km:.0f} km @ {kn:.0f} kn)"
    else:
        eta = f"~{hrs:.0f} h from {best[0]} ({best_km:.0f} km @ {kn:.0f} kn)"
    return dict(station=best[0], region=best[3], station_lat=best[1], station_lon=best[2],
                distance_km=round(best_km, 1), speed_kn=float(kn), eta=eta)


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
    # Extended §4.6: nearest response asset & ETA (turns "ranked list" into "what happens next hour")
    nearest_asset: dict = None
    distance_km: float = float("nan")
    eta: str = ""

    def dict(self):
        d = asdict(self)
        # Ensure JSON-safe: eta field mirrors eta_hint for backward compat
        if self.nearest_asset and not d.get("eta"):
            d["eta"] = self.eta_hint
        return d


def recommend(rep, jurisdiction, coast_km, coast_name):
    """Produce ~4-6 tasks covering: source zone monitoring, prime-suspect
    shadowing, coast preparation and (if MARPOL Special Area) escalation.

    Consumes the exported (dict) form of the report- dataclasses would work
    too but the dict is what /api/incidents/{id}/patrol already ships.
    """
    top = _NS(rep["detections"][0])
    src = _NS(rep["source"])
    disp = rep["source"].get("search_dispersion", {})
    tasks = []
    n = 1

    # Task 1: keep eyes on the reconstructed source corridor.
    na = _nearest_asset(src.start_lat, src.start_lon, "SATELLITE")
    tasks.append(PatrolTask(
        f"P-{n:03d}", "P1", "OBSERVE", "SATELLITE",
        target=f"Reconstructed source corridor- release window "
               f"{src.t_start/3600:+.1f} to {(src.t_start+src.duration)/3600:+.1f} h",
        lat=src.start_lat, lon=src.start_lon,
        radius_km=max(6.0, disp.get("position_sd_km", 3.0) * 3.0),
        eta_hint=na["eta"],
        reason="A repeat SAR acquisition in the source corridor confirms or refutes "
               "the inversion and tightens the release window.",
        nearest_asset=na, distance_km=na["distance_km"], eta=na["eta"])); n += 1

    # Task 2: shadow the prime suspect if attribution is confident.
    if rep["suspects"] and rep["suspects"][0]["score"] >= .6:
        s = _NS(rep["suspects"][0])
        pos = s.track[-1] if s.track else None
        lat = pos[1] if pos else src.start_lat
        lon = pos[0] if pos else src.start_lon
        na2 = _nearest_asset(lat, lon, "PATROL_VESSEL")
        tasks.append(PatrolTask(
            f"P-{n:03d}", "P1", "INVESTIGATE", "PATROL_VESSEL",
            target=f"Prime attribution candidate- {s.name} (MMSI {s.mmsi})",
            lat=lat, lon=lon, radius_km=25.0,
            eta_hint=na2["eta"],
            reason="Multi-factor attribution score {:.2f} with corroborating behaviour. "
                   "Boarding decision requires port state cooperation and oil "
                   "fingerprinting- this task is intelligence-gathering, not "
                   "interception.".format(s.score),
            nearest_asset=na2, distance_km=na2["distance_km"], eta=na2["eta"])); n += 1
    # (variable `s` above shadows the loop-less scope intentionally- the
    # prime-suspect block runs at most once.)

    # Task 3: coastal preparation, scaled by proximity.
    if coast_km < 80:
        pri = "P1" if coast_km < 30 else "P2"
        na3 = _nearest_asset(top.centroid_lonlat[1], top.centroid_lonlat[0], "SHORE_TEAM")
        tasks.append(PatrolTask(
            f"P-{n:03d}", pri, "PREPARE_RESPONSE", "SHORE_TEAM",
            target=f"Coastal watch- {coast_name} ({coast_km:.0f} km away)",
            lat=top.centroid_lonlat[1], lon=top.centroid_lonlat[0],
            radius_km=coast_km,
            eta_hint=na3["eta"],
            reason="Forecast drift places the slick within landfall range within "
                   "24 h. Mobilise the local response chain now, not after landfall.",
            nearest_asset=na3, distance_km=na3["distance_km"], eta=na3["eta"])); n += 1

    # Task 4: aerial confirmation.
    na4 = _nearest_asset(top.centroid_lonlat[1], top.centroid_lonlat[0], "AIRCRAFT")
    tasks.append(PatrolTask(
        f"P-{n:03d}", "P2", "OBSERVE", "AIRCRAFT",
        target="Aerial visual confirmation over slick centroid",
        lat=top.centroid_lonlat[1], lon=top.centroid_lonlat[0],
        radius_km=max(top.length_km, 15.0),
        eta_hint=na4["eta"],
        reason="Independent optical confirmation moves the incident from "
               "'SAR-classified' to 'visually confirmed'.",
        nearest_asset=na4, distance_km=na4["distance_km"], eta=na4["eta"]))
    n += 1

    if jurisdiction.marpol_regime == "special_area":
        na5 = _nearest_asset(top.centroid_lonlat[1], top.centroid_lonlat[0], "SHORE_TEAM")
        tasks.insert(0, PatrolTask(
            f"P-{n:03d}", "P1", "MONITOR", "SHORE_TEAM",
            target=f"MARPOL Special Area escalation- {jurisdiction.name}",
            lat=top.centroid_lonlat[1], lon=top.centroid_lonlat[0], radius_km=1.0,
            eta_hint=na5["eta"],
            reason="A discharge inside the Oman Area is subject to the stricter "
                   "MARPOL regime. Notify DG Shipping and the appropriate port "
                   "state through standard channels.",
            nearest_asset=na5, distance_km=na5["distance_km"], eta=na5["eta"]))

    return [t.dict() for t in tasks]
