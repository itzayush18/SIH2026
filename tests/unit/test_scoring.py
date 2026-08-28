"""
OilTrace — Unit tests for the attribution scoring formula.

Tests the evidence index function with known inputs/outputs,
verifies weights, and enforces the score_type product rule.
"""

import pytest

from packages.schemas.models import (
    compute_evidence_index,
    SCORE_TYPE,
    SCORING_WEIGHTS,
)


class TestComputeEvidenceIndex:
    """Test the R(v) formula:
    R(v) = 100 * q_case * q_ais * (0.35*s_space + 0.25*s_time + 0.25*s_fit + 0.15*s_beh)
    """

    def test_perfect_scores(self):
        """All components at 1.0 → score should be 100.0."""
        score = compute_evidence_index(
            q_case=1.0, q_ais=1.0,
            s_space=1.0, s_time=1.0, s_fit=1.0, s_beh=1.0,
        )
        assert score == 100.0

    def test_zero_quality(self):
        """q_case=0 should produce score 0 regardless of components."""
        score = compute_evidence_index(
            q_case=0.0, q_ais=1.0,
            s_space=1.0, s_time=1.0, s_fit=1.0, s_beh=1.0,
        )
        assert score == 0.0

    def test_zero_ais_quality(self):
        """q_ais=0 should produce score 0."""
        score = compute_evidence_index(
            q_case=1.0, q_ais=0.0,
            s_space=1.0, s_time=1.0, s_fit=1.0, s_beh=1.0,
        )
        assert score == 0.0

    def test_all_zero_components(self):
        """All component scores at 0 → score 0."""
        score = compute_evidence_index(
            q_case=1.0, q_ais=1.0,
            s_space=0.0, s_time=0.0, s_fit=0.0, s_beh=0.0,
        )
        assert score == 0.0

    def test_known_demo_value(self):
        """
        Reproduce the demo candidate score:
        q_case=1.0, q_ais=0.94
        s_space=0.91, s_time=0.82, s_fit=0.73, s_beh=0.31
        Expected: 100 * 1.0 * 0.94 * (0.35*0.91 + 0.25*0.82 + 0.25*0.73 + 0.15*0.31)
        """
        score = compute_evidence_index(
            q_case=1.0, q_ais=0.94,
            s_space=0.91, s_time=0.82, s_fit=0.73, s_beh=0.31,
        )
        # Manual calculation:
        # weighted = 0.35*0.91 + 0.25*0.82 + 0.25*0.73 + 0.15*0.31
        #          = 0.3185 + 0.205 + 0.1825 + 0.0465
        #          = 0.7525
        # R = 100 * 1.0 * 0.94 * 0.7525 = 70.735
        expected = round(100.0 * 1.0 * 0.94 * 0.7525, 2)
        assert score == expected

    def test_half_scores(self):
        """All components at 0.5 → 50% of max adjusted by quality."""
        score = compute_evidence_index(
            q_case=1.0, q_ais=1.0,
            s_space=0.5, s_time=0.5, s_fit=0.5, s_beh=0.5,
        )
        # weighted = 0.35*0.5 + 0.25*0.5 + 0.25*0.5 + 0.15*0.5 = 0.5
        assert score == 50.0

    def test_weights_are_applied(self):
        """Only spatial score set → should reflect 35% weight."""
        score = compute_evidence_index(
            q_case=1.0, q_ais=1.0,
            s_space=1.0, s_time=0.0, s_fit=0.0, s_beh=0.0,
        )
        assert score == 35.0

    def test_score_clamped_to_100(self):
        """Score should never exceed 100 even with weird inputs."""
        score = compute_evidence_index(
            q_case=2.0, q_ais=2.0,
            s_space=1.0, s_time=1.0, s_fit=1.0, s_beh=1.0,
        )
        assert score == 100.0

    def test_score_clamped_to_0(self):
        """Score should never go below 0."""
        score = compute_evidence_index(
            q_case=-1.0, q_ais=1.0,
            s_space=1.0, s_time=1.0, s_fit=1.0, s_beh=1.0,
        )
        assert score == 0.0

    def test_returns_float(self):
        score = compute_evidence_index(
            q_case=1.0, q_ais=1.0,
            s_space=0.5, s_time=0.5, s_fit=0.5, s_beh=0.5,
        )
        assert isinstance(score, float)


class TestScoringConstants:
    def test_score_type_is_evidence_index(self):
        """HARD PRODUCT RULE: Must be 'evidence_index'."""
        assert SCORE_TYPE == "evidence_index"

    def test_score_type_not_probability(self):
        assert "probability" not in SCORE_TYPE
        assert "prob" not in SCORE_TYPE

    def test_score_type_not_guilty(self):
        assert "guilty" not in SCORE_TYPE
        assert "guilt" not in SCORE_TYPE

    def test_weights_frozen(self):
        assert SCORING_WEIGHTS["space"] == 0.35
        assert SCORING_WEIGHTS["time"] == 0.25
        assert SCORING_WEIGHTS["forward_fit"] == 0.25
        assert SCORING_WEIGHTS["behaviour"] == 0.15

    def test_weights_sum_to_one(self):
        total = sum(SCORING_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9
