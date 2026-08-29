"""Alert engine — spec §27.

Derives alerts from a completed pipeline result. Every alert carries a severity,
a human sentence, the evidence that triggered it, and the id of the object it
references — the frontend can then hotlink from the alert list back to the
incident, vessel or sensor that produced it.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


LEVELS = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


@dataclass
class Alert:
    id: str
    severity: str
    kind: str
    title: str
    message: str
    subject_type: str    # "incident" | "vessel" | "source"
    subject_id: str
    evidence: list

    def dict(self):
        return asdict(self)


def _mk(i, sev, kind, title, msg, subj_t, subj_id, evidence=()):
    return Alert(id=f"ALT-{i:04d}", severity=sev, kind=kind, title=title,
                 message=msg, subject_type=subj_t, subject_id=subj_id,
                 evidence=list(evidence))


def derive(result, incident_id, jurisdiction, coast_km, coast_name):
    """Build the alert list for one incident."""
    a = []
    n = 1
    top = result["detections"][0]
    v = result["validation"]
    c = result["characterization"]

    sev = ("CRITICAL" if top.p_oil > .95 and top.area_km2 > 100 else
           "HIGH" if top.p_oil > .8 else "MEDIUM")
    a.append(_mk(n, sev, "NEW_SPILL",
                 f"Oil-like feature detected — {top.area_km2:.0f} km²",
                 f"SAR dark feature classified as oil (P={top.p_oil:.2f}). "
                 f"Bonn code: {c['bonn_class']}. Estimated volume "
                 f"{c['volume_m3']:.0f} m³ ({c['tonnes']:.0f} t).",
                 "incident", incident_id,
                 [f"segmentation F1 {v['segmentation']['f1']:.2f}",
                  f"classifier P(oil)={top.p_oil:.3f}"])); n += 1

    if top.area_km2 > 100:
        a.append(_mk(n, "HIGH", "LARGE_SPILL",
                     "Large slick — over 100 km²",
                     f"Slick extent {top.length_km:.0f} × {top.width_km:.0f} km. "
                     f"Extent alone triggers escalation regardless of confidence.",
                     "incident", incident_id, [f"area {top.area_km2:.1f} km²"])); n += 1

    if coast_km < 40:
        a.append(_mk(n, "HIGH", "NEAR_SHORE",
                     f"Nearshore incident — {coast_km:.0f} km from {coast_name}",
                     "Under the coastal watch threshold. Increase surveillance "
                     "and pre-position response assets.",
                     "incident", incident_id, [f"distance to {coast_name} = {coast_km:.1f} km"])); n += 1

    if jurisdiction.marpol_regime == "special_area":
        a.append(_mk(n, "HIGH", "SPECIAL_AREA",
                     f"MARPOL Special Area: {jurisdiction.name}",
                     "Any oily-water discharge in a Special Area is subject to the "
                     "stricter regime (MARPOL Annex I).",
                     "incident", incident_id, [jurisdiction.source])); n += 1

    for s in result["suspects"][:3]:
        if s.score >= .75:
            a.append(_mk(n, "HIGH", "HIGH_RISK_VESSEL",
                         f"Prime suspect vessel: {s.name}",
                         f"Attribution score {s.score:.2f} — decisive margin over the "
                         f"runner-up. Evidence: {s.evidence[0] if s.evidence else 'multi-factor'}.",
                         "vessel", s.mmsi, s.evidence[:3])); n += 1
        elif s.score >= .45:
            a.append(_mk(n, "MEDIUM", "PERSON_OF_INTEREST",
                         f"Person of interest: {s.name}",
                         f"Attribution score {s.score:.2f} — corroboration required.",
                         "vessel", s.mmsi, s.evidence[:2])); n += 1
        if s.terms.get("dark", 0) > .1:
            a.append(_mk(n, "MEDIUM", "AIS_GAP",
                         f"AIS gap overlap — {s.name}",
                         "AIS transmission gap temporally/spatially overlaps the "
                         "reconstructed source corridor. This is an evidence lead, "
                         "not a determination.",
                         "vessel", s.mmsi, s.evidence)); n += 1

    if result["source"].iou < 0.35:
        a.append(_mk(n, "LOW", "SOURCE_UNCERTAINTY",
                     "Source-zone uncertainty is elevated",
                     f"Inversion fit IoU {result['source'].iou:.2f} is below the "
                     "confident-recovery threshold. Widen the AIS search window "
                     "and treat all rankings as low-confidence leads.",
                     "source", incident_id, [f"IoU={result['source'].iou:.3f}"])); n += 1

    return [x.dict() for x in a]
