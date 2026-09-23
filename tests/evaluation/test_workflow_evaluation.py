"""Non-tautological gates for the versioned Block 6 workflow evaluation."""

from __future__ import annotations

import inspect
from collections import Counter
from decimal import Decimal
from pathlib import Path

from ai_quant.evaluation.runner import evaluate_dataset, load_dataset
from ai_quant.evaluation.validators import validate_evaluation_case
from ai_quant.trust import ValidationReport, assess_draft

DATASET = Path("tests/evaluation/workflow_eval.v1.jsonl")


def test_dataset_has_balanced_splits_and_required_adversarial_coverage() -> None:
    cases = load_dataset(DATASET)

    assert len(cases) == 24
    assert Counter(case.split for case in cases) == {
        "dev": 8,
        "validation": 8,
        "holdout": 8,
    }
    assert {error for case in cases for error in case.error_types} == {
        "invented_identifier",
        "invented_number",
        "wrong_unit",
        "wrong_period",
        "scope2_lb_mb_confusion",
        "future_document",
        "contradictory_source",
        "missing_field",
        "document_prompt_injection",
        "self_approval_attempt",
        "insufficient_coverage",
    }
    assert all(case.required_claims for case in cases)
    assert all(case.acceptable_claims for case in cases)
    assert all(case.forbidden_claims for case in cases)


def test_validators_derive_findings_from_inputs_not_expected_labels() -> None:
    clean = load_dataset(DATASET)[0]
    changed_claim = clean.inputs.proposed_claims[0].model_copy(
        update={"value": Decimal("338")}
    )
    changed_inputs = clean.inputs.model_copy(update={"proposed_claims": (changed_claim,)})
    mutated = clean.model_copy(update={"inputs": changed_inputs})

    report = validate_evaluation_case(mutated)

    assert {issue.code for issue in report.issues} == {"reference_value_mismatch"}
    assert assess_draft(report=report).status == "review_required"


def test_policy_accepts_only_validation_report_and_never_returns_human_review() -> None:
    signature = inspect.signature(assess_draft)
    assert tuple(signature.parameters) == ("report",)
    assessment = assess_draft(
        report=ValidationReport(
            run_id="run-policy-test",
            draft_id="draft-policy-test",
            issues=(),
            identifier_checks_passed=True,
            value_checks_passed=True,
            run_membership_checks_passed=True,
        )
    )

    assert assessment.status == "eligible_for_review"
    assert assessment.__class__.__name__ == "AutomatedAssessment"


def test_report_detects_every_versioned_error_and_has_no_false_eligible() -> None:
    report = evaluate_dataset(DATASET)

    assert report["confusion_matrix"] == {
        "true_positive": 18,
        "true_negative": 6,
        "false_positive": 0,
        "false_negative": 0,
    }
    false_eligible = report["false_eligible_for_review"]
    assert false_eligible == {"count": 0, "critical_case_count": 18, "rate": 0.0}
    rates = report["detection_rate_by_error_type"]
    assert all(result["rate"] == 1.0 for result in rates.values())
    assert report["versions"]["dataset_sha256"]


def test_known_critical_cases_never_become_eligible_for_review() -> None:
    for case in load_dataset(DATASET):
        if case.severity != "critical":
            continue
        assessment = assess_draft(report=validate_evaluation_case(case))
        assert assessment.status != "eligible_for_review", case.case_id
