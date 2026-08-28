"""
OilTrace — Attribution service.

Responsible for:
  - Gating: filtering candidate vessels by proximity to origin contours
  - Scoring: computing the evidence index R(v) for each candidate
  - Explanations: generating human-readable evidence summaries
  - Abstention: detecting when evidence is insufficient to rank

Scaffold pass: uses real scoring formula with hardcoded component scores.

IMPORTANT: The output is an EVIDENCE INDEX, not a probability or guilt
determination. See SCORE_TYPE constant in schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from packages.schemas.models import (
    CandidateEvidence,
    CandidateResponse,
    compute_evidence_index,
    SCORE_TYPE,
)


# Demo candidate vessels with pre-set component scores
_DEMO_CANDIDATES = [
    {
        "vessel_key": "mmsi:538007689",
        "components": {"space": 0.91, "time": 0.82, "forward_fit": 0.73, "behaviour": 0.31},
        "ais_quality": 0.94,
        "flags": ["short_gap_interpolated"],
    },
    {
        "vessel_key": "mmsi:636092804",
        "components": {"space": 0.65, "time": 0.71, "forward_fit": 0.42, "behaviour": 0.18},
        "ais_quality": 0.88,
        "flags": [],
    },
    {
        "vessel_key": "mmsi:477553000",
        "components": {"space": 0.45, "time": 0.55, "forward_fit": 0.30, "behaviour": 0.62},
        "ais_quality": 0.72,
        "flags": ["dark_period_detected"],
    },
]


def gate_candidates(
    contours: dict[str, Any],
    tracks: list[Any],
) -> list[dict[str, Any]]:
    """
    Filter candidate vessels by spatial proximity to origin contours.

    Scaffold: returns all demo candidates (no real gating).
    Production: point-in-polygon test for each vessel position vs contours.
    """
    return _DEMO_CANDIDATES


def score_candidates(
    case_id: str,
    candidates: list[dict[str, Any]],
    q_case: float = 1.0,
) -> CandidateResponse:
    """
    Score and rank candidate vessels using the evidence index formula.

    R(v) = 100 * q_case * q_ais(v) * (
        0.35 * s_space + 0.25 * s_time + 0.25 * s_fit + 0.15 * s_beh
    )

    This is a real implementation of the formula, even though inputs are
    currently hardcoded demo data.

    Args:
        case_id: Case identifier.
        candidates: List of candidate dicts with component scores.
        q_case: Overall case quality factor (0-1).

    Returns:
        CandidateResponse with ranked candidates and score_type = "evidence_index".
    """
    scored: list[CandidateEvidence] = []

    for cand in candidates:
        comp = cand["components"]
        q_ais = cand.get("ais_quality", 1.0)

        score = compute_evidence_index(
            q_case=q_case,
            q_ais=q_ais,
            s_space=comp["space"],
            s_time=comp["time"],
            s_fit=comp["forward_fit"],
            s_beh=comp["behaviour"],
        )

        scored.append(CandidateEvidence(
            vessel_key=cand["vessel_key"],
            score=score,
            components=comp,
            ais_quality=q_ais,
            evidence_time_utc=datetime(2026, 8, 20, 4, 15, 0),
            flags=cand.get("flags", []),
        ))

    # Sort descending by score
    scored.sort(key=lambda c: c.score, reverse=True)

    # Determine abstention reasons
    abstention_reasons: list[str] = []
    if not scored:
        abstention_reasons.append("no_candidates_in_aoi")
    elif scored[0].score < 20.0:
        abstention_reasons.append("max_score_below_threshold")

    return CandidateResponse(
        case_id=case_id,
        status="review_required",
        score_type=SCORE_TYPE,  # ALWAYS "evidence_index"
        candidates=scored,
        abstention_reasons=abstention_reasons,
    )


def generate_explanation(candidate: CandidateEvidence) -> str:
    """
    Generate a human-readable explanation for a candidate's score.

    Scaffold: returns a template-based summary.
    Production: natural-language generation with component breakdowns.
    """
    comp = candidate.components
    return (
        f"Vessel {candidate.vessel_key} received an evidence index of "
        f"{candidate.score:.1f}/100. "
        f"Spatial proximity scored {comp.get('space', 0):.0%}, "
        f"temporal proximity {comp.get('time', 0):.0%}, "
        f"forward-drift fit {comp.get('forward_fit', 0):.0%}, "
        f"and behavioural indicators {comp.get('behaviour', 0):.0%}. "
        f"AIS data quality: {candidate.ais_quality:.0%}."
    )
