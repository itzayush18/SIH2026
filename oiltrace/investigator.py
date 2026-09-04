"""Rule-based investigator — spec §45-46.

A rule-based answering engine over one incident's report. It does not call an
LLM: no API key required, deterministic, and every answer cites the field it
was derived from. Genuinely useful for the demo — the LLM path lives alongside
via `oiltrace.notify` and can be swapped in when creds exist.
"""
from __future__ import annotations

import re


def _fmt_lat(x): return f"{abs(x):.4f}°{'N' if x>=0 else 'S'}"
def _fmt_lon(x): return f"{abs(x):.4f}°{'E' if x>=0 else 'W'}"


def _q_who(rep):
    if not rep["suspects"]:
        return "No candidate vessels could be scored.", []
    s = rep["suspects"][0]
    return (f"The prime attribution candidate is <b>{s['name']}</b> "
            f"(MMSI {s['mmsi']}, {s['type_name']}, {s['length']:.0f} m). "
            f"Attribution score {s['score']:.2f} — "
            f"a {int((s['score']-rep['suspects'][1]['score'])*100)}pp margin over the runner-up "
            f"{rep['suspects'][1]['name']}."
            if len(rep["suspects"])>1 else
            f"The prime attribution candidate is <b>{s['name']}</b> "
            f"(MMSI {s['mmsi']}). Score {s['score']:.2f}.",
            [f"suspects[0]", f"suspects[1]" if len(rep["suspects"])>1 else ""])


def _q_where(rep):
    d = rep["detections"][0]
    lat, lon = d["centroid_lonlat"][1], d["centroid_lonlat"][0]
    j = rep["oiltrace"]["jurisdiction"]
    nc = rep["oiltrace"]["nearest_coast"]
    return (f"The slick centroid sits at <b>{_fmt_lat(lat)} {_fmt_lon(lon)}</b>, "
            f"inside <b>{j['name']}</b> — MARPOL regime "
            f"<b>{j['marpol_regime']}</b>. "
            f"Nearest coast: {nc['name']} at {nc['km']:.0f} km.",
            ["detections[0].centroid_lonlat", "oiltrace.jurisdiction", "oiltrace.nearest_coast"])


def _q_when(rep):
    src = rep["source"]
    hb = -src["t_start"] / 3600.0
    dh = src["duration"] / 3600.0
    return (f"Source-term inversion places the release <b>{hb:.1f} hours before</b> "
            f"the SAR acquisition, over a duration of <b>{dh:.1f} h</b> "
            f"(IoU {src['iou']:.2f}). Search dispersion is "
            f"{src['search_dispersion']['position_sd_km']:.1f} km / "
            f"{src['search_dispersion']['t_start_sd_h']:.1f} h.",
            ["source.t_start", "source.duration", "source.search_dispersion"])


def _q_why(rep):
    if not rep["suspects"]:
        return "No candidate to explain — inversion or AIS came back empty.", []
    s = rep["suspects"][0]
    lines = "".join(f"<li>{e}</li>" for e in s["evidence"])
    return (f"Attribution for <b>{s['name']}</b> is driven by six additive log-odds terms. "
            f"The specific evidence pushing the score up:<ul>{lines}</ul>"
            f"Term weights are configurable — open the Model Lab to see the ranking shift under "
            f"different priors.",
            [f"suspects[0].evidence", "attribution.WEIGHTS"])


def _q_how(rep):
    return ("The pipeline is deterministic and modular: "
            "<b>Sentinel-1 → refined-Lee speckle → incidence detrending → "
            "multi-scale adaptive threshold → 8-feature logistic classifier "
            "→ Bonn thickness + Fay/advective/weathering age fusion → "
            "RK2 Lagrangian ensemble (4000 particles, ±0.6% windage) "
            "→ source-term inversion (moving line source, IoU objective) "
            "→ six-axis attribution scoring.</b> "
            "Every stage exposes its uncertainty; see the Overview tab for the numbers.",
            ["pipeline"])


def _q_confidence(rep):
    v = rep.get("validation", {})
    if v.get("segmentation", {}).get("iou") == v.get("segmentation", {}).get("iou"):
        return (f"Self-validation against the known synthetic ground truth: "
                f"segmentation IoU {v['segmentation']['iou']:.3f}, "
                f"F1 {v['segmentation']['f1']:.3f}, "
                f"origin position error {v['inversion_error_km']:.2f} km, "
                f"release time error {v['inversion_time_error_h']*60:.0f} min. "
                f"On real Sentinel-1 no ground truth exists — trust the "
                f"per-stage uncertainty rather than a single number.",
                ["validation"])
    return ("No laboratory ground truth to compare against on this incident "
            "(this is likely a real-scene ingest). Trust the per-stage "
            "uncertainty on the Overview tab.", ["validation"])


def _q_response(rep):
    tasks = rep["oiltrace"].get("patrol", [])
    if not tasks:
        return "No patrol tasks recommended.", []
    p1 = [t for t in tasks if t["priority"] == "P1"]
    return (f"There are {len(tasks)} recommended actions "
            f"({len(p1)} at priority P1). "
            + ("The most urgent: " + "; ".join(t["target"] for t in p1) + "."
               if p1 else ""),
            ["oiltrace.patrol"])


RULES = [
    (r"\b(who|which vessel|prime suspect|source vessel)\b",  _q_who),
    (r"\b(where|location|coordinate|jurisdiction|coast)\b",  _q_where),
    (r"\b(when|time|release|hour|window)\b",                  _q_when),
    (r"\b(why|explain|reason|because|justif)\b",             _q_why),
    (r"\b(how|method|pipeline|algorithm|process)\b",         _q_how),
    (r"\b(confiden|accura|trust|error|uncertain)\b",         _q_confidence),
    (r"\b(action|patrol|respons|do next|next step|deploy)\b", _q_response),
]


def answer(rep, question):
    q = question.lower().strip()
    for pat, fn in RULES:
        if re.search(pat, q):
            text, cites = fn(rep)
            return dict(question=question, answer=text, citations=[c for c in cites if c])
    # Fallback: give the who/where/when combo — the most common ask
    who_t, who_c = _q_who(rep)
    where_t, _  = _q_where(rep)
    when_t, _   = _q_when(rep)
    return dict(question=question,
        answer=f"{who_t}<br><br>{where_t}<br><br>{when_t}",
        citations=who_c + ["detections[0]", "source"])
