"""Focused regressions for deterministic prose content rules."""

from __future__ import annotations

import json

import pytest

from ai_quant.content_rules import (
    CANONICAL_SUMMARY_EVIDENCE_ONLY,
    CANONICAL_SUMMARY_METRICS_AND_EVIDENCE,
    CANONICAL_SUMMARY_METRICS_ONLY,
    CanonicalSummaryError,
    canonical_summary,
    has_any_placeholder,
    has_implicit_cross_domain_relation,
    has_internal_status_token,
    has_prohibited_risk_language,
    has_unsupported_period_alignment,
    normalize_proposal_summary,
    numeric_literals,
)
from ai_quant.trust import ClaimProposal, DraftProposal


@pytest.mark.parametrize(
    ("has_metrics", "has_evidence", "expected"),
    (
        (True, True, CANONICAL_SUMMARY_METRICS_AND_EVIDENCE),
        (True, False, CANONICAL_SUMMARY_METRICS_ONLY),
        (False, True, CANONICAL_SUMMARY_EVIDENCE_ONLY),
    ),
)
def test_canonical_summary_depends_only_on_trusted_input_shape(
    has_metrics: bool,
    has_evidence: bool,
    expected: str,
) -> None:
    assert canonical_summary(
        has_metrics=has_metrics,
        has_evidence=has_evidence,
    ) == expected
    assert not has_any_placeholder(expected)
    assert not has_implicit_cross_domain_relation(expected)
    assert not has_internal_status_token(expected)
    assert not has_prohibited_risk_language(expected)
    assert not has_unsupported_period_alignment(expected)
    assert numeric_literals(expected) == ()


def test_canonical_summary_rejects_empty_inputs() -> None:
    with pytest.raises(CanonicalSummaryError, match="at least one metric or evidence"):
        canonical_summary(has_metrics=False, has_evidence=False)


def test_summary_normalization_is_deterministic_idempotent_and_summary_only() -> None:
    proposal = DraftProposal(
        summary="Untrusted provider summary.",
        claims=(
            ClaimProposal(
                text_template="Historical metric {{metric:metric-run-test-return}}.",
                claim_type="quantitative",
                metric_ids=("metric-run-test-return",),
                uncertainty="Historical observation only.",
            ),
        ),
        limitations=("Test limitation.",),
    )
    protected_before = json.dumps(
        {
            "claims": [claim.model_dump(mode="json") for claim in proposal.claims],
            "limitations": proposal.limitations,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    first = normalize_proposal_summary(
        proposal,
        has_metrics=True,
        has_evidence=False,
    )
    second = normalize_proposal_summary(
        first,
        has_metrics=True,
        has_evidence=False,
    )
    protected_after = json.dumps(
        {
            "claims": [claim.model_dump(mode="json") for claim in second.claims],
            "limitations": second.limitations,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert first == second
    assert first is second
    assert first.summary == CANONICAL_SUMMARY_METRICS_ONLY
    assert protected_after == protected_before


@pytest.mark.parametrize(
    "text",
    (
        (
            "No claim is made that the metrics and the evidence record cover the same period, "
            "as their explicit dates are not confirmed to be equal in the supplied inputs."
        ),
        "The supplied inputs do not establish temporal comparability.",
        "The periods are not confirmed to align.",
    ),
)
def test_closed_epistemic_period_reservations_are_accepted(text: str) -> None:
    assert not has_unsupported_period_alignment(text)


@pytest.mark.parametrize(
    "text",
    (
        "The metrics and the evidence cover the same period.",
        "Both observations relate to the same reporting period.",
        "The dates are aligned.",
        "They do not cover the same period.",
        "No claim is made that they cover the same period, but the dates are aligned.",
        "The dates are probably aligned.",
    ),
)
def test_other_period_alignment_language_fails_closed(text: str) -> None:
    assert has_unsupported_period_alignment(text)
