"""Deterministic reference and numeric-injection tests."""

from __future__ import annotations

import pytest

from ai_quant.trust import (
    ClaimProposal,
    DraftProposal,
    InMemoryTrustWorkflow,
    ValidationReport,
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
    assert not report.identifier_checks_passed
    assert not report.run_membership_checks_passed


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
    assert all(metric.unit in rendered.final_text for metric in valid_result.metric_records)  # type: ignore[operator]
    assert "{{metric:" not in rendered.final_text  # type: ignore[operator]
    assert "{{evidence:" not in rendered.final_text  # type: ignore[operator]


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


def test_generic_and_unknown_placeholders_fail_closed(valid_result) -> None:  # type: ignore[no-untyped-def]
    for text, expected_code in (
        ("Return is {value}.", "generic_placeholder"),
        ("Unknown {{other:identifier}}.", "unresolved_placeholder"),
    ):
        draft = _draft_with_claim(
            valid_result,
            ClaimProposal(
                text_template=text,
                claim_type="limitation",
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

        assert expected_code in {issue.code for issue in report.issues}
        assert not rendered.reliable
        assert rendered.final_text is None


def test_renderer_independently_rejects_a_residual_placeholder(valid_result) -> None:  # type: ignore[no-untyped-def]
    draft = _draft_with_claim(
        valid_result,
        ClaimProposal(
            text_template="Unknown {{other:identifier}}.",
            claim_type="limitation",
        ),
    )
    forged_clean_report = ValidationReport(
        run_id=draft.run_id,
        draft_id=draft.draft_id,
        issues=(),
        trusted_input_count=(
            len(valid_result.metric_records) + len(valid_result.evidence_records)
        ),
        identifier_checks_passed=True,
        value_checks_passed=True,
        run_membership_checks_passed=True,
    )

    rendered = render_validated_draft(
        draft=draft,
        report=forged_clean_report,
        metrics=valid_result.metric_records,
        evidence=valid_result.evidence_records,
    )

    assert not rendered.reliable
    assert rendered.final_text is None
    assert rendered.claims == ()


@pytest.mark.parametrize("metric_index", (0, 1))
def test_metric_value_in_summary_is_blocked(
    valid_result,
    metric_index: int,
) -> None:  # type: ignore[no-untyped-def]
    metric = valid_result.metric_records[metric_index]
    proposal = DraftProposal(
        summary=f"The summary states {metric.value:.2%} directly.",
        claims=(
            ClaimProposal(
                text_template=f"Metric {{{{metric:{metric.metric_id}}}}}.",
                claim_type="quantitative",
                metric_ids=(metric.metric_id,),
            ),
        ),
        limitations=("Offline test only.",),
    )
    draft = materialize_generated_draft(
        valid_result.run_id,
        proposal,
        valid_result.draft.generation,
    )

    report = validate_draft(
        run_id=valid_result.run_id,
        draft=draft,
        metrics=valid_result.metric_records,
        evidence=valid_result.evidence_records,
    )

    assert "metric_value_literal" in {issue.code for issue in report.issues}
    assert not report.value_checks_passed


def test_policy_consumes_only_validation_report(valid_result) -> None:  # type: ignore[no-untyped-def]
    assessment = assess_draft(
        report=valid_result.validation_report,
    )

    assert assessment.status == "eligible_for_review"


def test_production_validator_abstains_without_server_owned_inputs(valid_result) -> None:  # type: ignore[no-untyped-def]
    draft = _draft_with_claim(
        valid_result,
        ClaimProposal(
            text_template="No trusted basis is available.",
            claim_type="limitation",
        ),
    )

    report = validate_draft(
        run_id=valid_result.run_id,
        draft=draft,
        metrics=(),
        evidence=(),
    )
    assessment = assess_draft(report=report)

    assert {issue.code for issue in report.issues} == {"insufficient_trusted_inputs"}
    assert report.trusted_input_count == 0
    assert assessment.status == "abstain"
    assert assessment.reason_codes == ("insufficient_trusted_inputs",)
