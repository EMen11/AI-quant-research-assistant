"""Deterministic reference and numeric-injection tests."""

from __future__ import annotations

import pytest

from ai_quant.trust import (
    ClaimProposal,
    DraftProposal,
    InMemoryTrustWorkflow,
    assess_draft,
    render_validated_draft,
    validate_draft,
)
from ai_quant.trust.records import materialize_generated_draft


@pytest.fixture(scope="module")
def valid_result():  # type: ignore[no-untyped-def]
    return InMemoryTrustWorkflow().run("valid")


def _draft_with_claim(valid_result, claim: ClaimProposal):  # type: ignore[no-untyped-def]
    proposal = DraftProposal(
        summary="Synthetic test proposal.",
        claims=(claim,),
        limitations=("Offline test only.",),
    )
    return materialize_generated_draft(
        valid_result.run_id, proposal, valid_result.draft.generation
    )


def test_unknown_current_run_metric_is_blocked(valid_result) -> None:  # type: ignore[no-untyped-def]
    metric_id = "metric-run-demo-valid-not-present"
    draft = _draft_with_claim(
        valid_result,
        ClaimProposal(
            text_template=f"Return is {{{{metric:{metric_id}}}}}.",
            claim_type="quantitative",
            metric_ids=(metric_id,),
        ),
    )
    report = validate_draft(
        run_id=valid_result.run_id,
        draft=draft,
        metrics=valid_result.metric_records,
        evidence=valid_result.evidence_records,
    )

    assert "unknown_metric" in {issue.code for issue in report.issues}
    assert report.has_blocking_issues


def test_unknown_current_run_evidence_is_blocked(valid_result) -> None:  # type: ignore[no-untyped-def]
    evidence_id = "evidence-run-demo-valid-not-present"
    draft = _draft_with_claim(
        valid_result,
        ClaimProposal(
            text_template=f"Source is {{{{evidence:{evidence_id}}}}}.",
            claim_type="evidence",
            evidence_ids=(evidence_id,),
        ),
    )
    report = validate_draft(
        run_id=valid_result.run_id,
        draft=draft,
        metrics=valid_result.metric_records,
        evidence=valid_result.evidence_records,
    )

    assert "unknown_evidence" in {issue.code for issue in report.issues}


def test_cross_run_metric_reference_is_blocked(valid_result) -> None:  # type: ignore[no-untyped-def]
    other_result = InMemoryTrustWorkflow().run("blocked")
    metric_id = other_result.metric_records[0].metric_id
    draft = _draft_with_claim(
        valid_result,
        ClaimProposal(
            text_template=f"Return is {{{{metric:{metric_id}}}}}.",
            claim_type="quantitative",
            metric_ids=(metric_id,),
        ),
    )
    report = validate_draft(
        run_id=valid_result.run_id,
        draft=draft,
        metrics=valid_result.metric_records + other_result.metric_records,
        evidence=valid_result.evidence_records,
    )

    assert "cross_run_reference" in {issue.code for issue in report.issues}


def test_cross_run_evidence_reference_is_blocked(valid_result) -> None:  # type: ignore[no-untyped-def]
    other_result = InMemoryTrustWorkflow().run("blocked")
    evidence_id = other_result.evidence_records[0].evidence_id
    draft = _draft_with_claim(
        valid_result,
        ClaimProposal(
            text_template=f"Source is {{{{evidence:{evidence_id}}}}}.",
            claim_type="evidence",
            evidence_ids=(evidence_id,),
        ),
    )
    report = validate_draft(
        run_id=valid_result.run_id,
        draft=draft,
        metrics=valid_result.metric_records,
        evidence=valid_result.evidence_records + other_result.evidence_records,
    )

    assert "cross_run_reference" in {issue.code for issue in report.issues}


def test_python_injects_metric_values_and_creates_references(valid_result) -> None:  # type: ignore[no-untyped-def]
    rendered = valid_result.rendered_draft
    expected_values = {f"{metric.value:.2%}" for metric in valid_result.metric_records}
    actual_values = {
        reference.rendered_value
        for claim in rendered.claims
        for reference in claim.metric_references
    }

    assert rendered.reliable
    assert expected_values == actual_values
    assert all(value in rendered.final_text for value in expected_values)  # type: ignore[operator]
    assert "{{metric:" not in rendered.final_text  # type: ignore[operator]


def test_invented_number_blocks_rendering(valid_result) -> None:  # type: ignore[no-untyped-def]
    metric_id = valid_result.metric_records[0].metric_id
    draft = _draft_with_claim(
        valid_result,
        ClaimProposal(
            text_template=(
                f"Return is 12.3% while the record is {{{{metric:{metric_id}}}}}."
            ),
            claim_type="quantitative",
            metric_ids=(metric_id,),
        ),
    )
    report = validate_draft(
        run_id=valid_result.run_id,
        draft=draft,
        metrics=valid_result.metric_records,
        evidence=valid_result.evidence_records,
    )
    rendered = render_validated_draft(
        draft=draft,
        report=report,
        metrics=valid_result.metric_records,
        evidence=valid_result.evidence_records,
    )

    assert "free_numeric_literal" in {issue.code for issue in report.issues}
    assert not rendered.reliable
    assert rendered.final_text is None


def test_missing_trusted_inputs_force_abstention(valid_result) -> None:  # type: ignore[no-untyped-def]
    assessment = assess_draft(
        run_id=valid_result.run_id,
        report=valid_result.validation_report,
        metrics=(),
        evidence=(),
    )

    assert assessment.status == "abstain"
