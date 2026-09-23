"""Reproducible dataset runner and machine-readable report generator."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from ai_quant.evaluation.models import ErrorType, WorkflowEvaluationCase
from ai_quant.evaluation.validators import validate_evaluation_case
from ai_quant.trust.validation import assess_draft

DATASET_VERSION = "workflow-eval.v1"
PROMPT_VERSION = "trust-synthesis-v3"
VALIDATOR_VERSION = "deterministic-workflow-validators.v1"

_ERROR_TO_CODE: dict[ErrorType, str] = {
    "invented_identifier": "unknown_evidence",
    "invented_number": "reference_value_mismatch",
    "wrong_unit": "reference_unit_mismatch",
    "wrong_period": "reference_period_mismatch",
    "scope2_lb_mb_confusion": "scope2_method_mismatch",
    "future_document": "document_after_cutoff",
    "contradictory_source": "contradictory_source",
    "missing_field": "missing_required_field",
    "document_prompt_injection": "document_prompt_injection",
    "self_approval_attempt": "self_approval_attempt",
    "insufficient_coverage": "insufficient_coverage",
}


def load_dataset(path: Path) -> tuple[WorkflowEvaluationCase, ...]:
    """Load strict JSONL without consulting environment files or external services."""

    return tuple(
        WorkflowEvaluationCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def evaluate_dataset(path: Path) -> dict[str, object]:
    """Evaluate every case and return stable, JSON-serializable aggregate results."""

    cases = load_dataset(path)
    matrix = Counter({"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0})
    by_type: dict[str, list[bool]] = defaultdict(list)
    results: list[dict[str, object]] = []
    false_eligible = 0
    critical_cases = 0

    for case in cases:
        report = validate_evaluation_case(case)
        assessment = assess_draft(report=report)
        expected_blocked = case.expected_outcome != "eligible_for_review"
        predicted_blocked = assessment.status != "eligible_for_review"
        matrix[_matrix_cell(expected_blocked, predicted_blocked)] += 1
        if case.severity == "critical":
            critical_cases += 1
            if assessment.status == "eligible_for_review":
                false_eligible += 1
        codes = {issue.code for issue in report.issues}
        for error_type in case.error_types:
            by_type[error_type].append(_ERROR_TO_CODE[error_type] in codes)
        results.append(
            {
                "case_id": case.case_id,
                "split": case.split,
                "expected_outcome": case.expected_outcome,
                "actual_outcome": assessment.status,
                "detected_issue_codes": sorted(codes),
                "passed": assessment.status == case.expected_outcome,
            }
        )

    split_counts = Counter(case.split for case in cases)
    return {
        "schema_version": "workflow-evaluation-report.v1",
        "scope_statement": "Results, including false-eligible claims, apply only to workflow_eval.v1.jsonl at the recorded SHA-256.",
        "versions": {
            "dataset": DATASET_VERSION,
            "dataset_sha256": _sha256(path.read_bytes()),
            "prompt": PROMPT_VERSION,
            "validators": VALIDATOR_VERSION,
        },
        "case_count": len(cases),
        "split_counts": dict(sorted(split_counts.items())),
        "confusion_matrix": dict(matrix),
        "detection_rate_by_error_type": {
            key: {"detected": sum(values), "total": len(values), "rate": sum(values) / len(values)}
            for key, values in sorted(by_type.items())
        },
        "false_eligible_for_review": {
            "count": false_eligible,
            "critical_case_count": critical_cases,
            "rate": false_eligible / critical_cases if critical_cases else 0.0,
        },
        "latency": {
            "measurement": "deterministic_validator_work_units",
            "unit": "cases",
            "value": len(cases),
            "wall_clock_excluded_for_byte_reproducibility": True,
        },
        "cases": results,
    }


def write_evaluation_report(dataset_path: Path, output_path: Path) -> None:
    """Write canonical UTF-8 JSON with no clock-dependent fields."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evaluate_dataset(dataset_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _matrix_cell(expected_blocked: bool, predicted_blocked: bool) -> str:
    if expected_blocked and predicted_blocked:
        return "true_positive"
    if not expected_blocked and not predicted_blocked:
        return "true_negative"
    if expected_blocked:
        return "false_negative"
    return "false_positive"


def _sha256(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()
