"""Deterministic validation evaluation and separate local timing reporting."""

from __future__ import annotations

import json
import os
import platform
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from ai_quant.evaluation.models import (
    ErrorType,
    TimingClock,
    TimingDataset,
    TimingEnvironment,
    TimingSummary,
    WorkflowEvaluationCase,
    WorkflowEvaluationTimingReport,
)
from ai_quant.evaluation.validators import validate_evaluation_case
from ai_quant.trust.validation import assess_draft

DATASET_VERSION = "workflow-eval.v1"
PROMPT_VERSION = "trust-synthesis-v3"
VALIDATOR_VERSION = "production-validation-adapter.v2"
TIMING_SCHEMA_VERSION = "workflow-evaluation-timing.v1"
TIMING_WARMUP_RUNS = 3
TIMING_MEASURED_RUNS = 20
TIMING_REPRODUCIBILITY_NOTICE = (
    "Durations depend on hardware, caches, scheduling, and system load; "
    "they are not byte-for-byte reproducible and are not a portable benchmark."
)

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
    "reference_claim_key_mismatch": "reference_claim_key_mismatch",
    "cross_run_reference": "cross_run_reference",
    "insufficient_trusted_inputs": "insufficient_trusted_inputs",
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
    split_matrices = {
        split: Counter(
            {
                "true_positive": 0,
                "true_negative": 0,
                "false_positive": 0,
                "false_negative": 0,
            }
        )
        for split in ("dev", "validation", "holdout")
    }
    split_passed = Counter({split: 0 for split in split_matrices})
    false_eligible = 0
    critical_cases = 0

    for case in cases:
        report = validate_evaluation_case(case)
        assessment = assess_draft(report=report)
        expected_blocked = case.expected_outcome != "eligible_for_review"
        predicted_blocked = assessment.status != "eligible_for_review"
        matrix_cell = _matrix_cell(expected_blocked, predicted_blocked)
        matrix[matrix_cell] += 1
        split_matrices[case.split][matrix_cell] += 1
        split_passed[case.split] += assessment.status == case.expected_outcome
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
        "schema_version": "workflow-evaluation-report.v2",
        "scope_statement": (
            "Results apply only to the exact workflow_eval.v1.jsonl SHA-256 and the "
            "versioned attack families represented there; they do not establish real-world "
            "generalization or universal prompt-injection protection."
        ),
        "versions": {
            "dataset": DATASET_VERSION,
            "dataset_sha256": _sha256(path.read_bytes()),
            "prompt": PROMPT_VERSION,
            "validators": VALIDATOR_VERSION,
        },
        "case_count": len(cases),
        "split_counts": dict(sorted(split_counts.items())),
        "confusion_matrix": dict(matrix),
        "metrics_by_split": {
            split: {
                "case_count": split_counts[split],
                "passed": split_passed[split],
                "confusion_matrix": dict(split_matrices[split]),
            }
            for split in ("dev", "validation", "holdout")
        },
        "detection_rate_by_error_type": {
            key: {"detected": sum(values), "total": len(values), "rate": sum(values) / len(values)}
            for key, values in sorted(by_type.items())
        },
        "false_eligible_for_review": {
            "count": false_eligible,
            "critical_case_count": critical_cases,
            "rate": false_eligible / critical_cases if critical_cases else 0.0,
        },
        "workload": {
            "measurement": "evaluated_cases",
            "case_count": len(cases),
            "timing_reported_separately": True,
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


def measure_evaluation_pipeline(dataset_path: Path) -> WorkflowEvaluationTimingReport:
    """Measure complete sequential evaluations after fixed untimed warmups."""

    for _ in range(TIMING_WARMUP_RUNS):
        evaluate_dataset(dataset_path)

    observations: list[int] = []
    last_report: dict[str, object] | None = None
    for _ in range(TIMING_MEASURED_RUNS):
        started_ns = time.perf_counter_ns()
        last_report = evaluate_dataset(dataset_path)
        elapsed_ns = time.perf_counter_ns() - started_ns
        observations.append(elapsed_ns)

    assert last_report is not None
    clock_info = time.get_clock_info("perf_counter")
    resolution_ns = max(1, round(clock_info.resolution * 1_000_000_000))
    versions = last_report["versions"]
    assert isinstance(versions, dict)
    dataset_sha256 = versions["dataset_sha256"]
    assert isinstance(dataset_sha256, str)
    case_count = last_report["case_count"]
    assert isinstance(case_count, int)

    return WorkflowEvaluationTimingReport(
        schema_version=TIMING_SCHEMA_VERSION,
        measurement_scope="deterministic_validation_evaluation_pipeline",
        warmup_runs=TIMING_WARMUP_RUNS,
        measured_runs=TIMING_MEASURED_RUNS,
        unit="nanoseconds",
        clock=TimingClock(
            name="time.perf_counter_ns",
            monotonic=clock_info.monotonic,
            resolution_ns=resolution_ns,
        ),
        dataset=TimingDataset(
            version=DATASET_VERSION,
            sha256=dataset_sha256,
            filename=dataset_path.name,
            case_count=case_count,
        ),
        environment=TimingEnvironment(
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            python_compiler=platform.python_compiler(),
            platform_system=platform.system(),
            platform_release=platform.release(),
            platform_machine=platform.machine(),
            processor=platform.processor(),
            logical_cpu_count=os.cpu_count(),
        ),
        observations=tuple(observations),
        summary=TimingSummary(
            minimum=min(observations),
            median=float(statistics.median(observations)),
            maximum=max(observations),
        ),
        reproducibility_notice=TIMING_REPRODUCIBILITY_NOTICE,
    )


def write_evaluation_timing_report(dataset_path: Path, output_path: Path) -> None:
    """Write the non-deterministic timing sidecar separately from the canonical report."""

    timing_report = measure_evaluation_pipeline(dataset_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(timing_report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_evaluation_artifacts(
    dataset_path: Path,
    report_path: Path,
    timing_path: Path,
) -> None:
    """Write the deterministic report and machine-dependent timing sidecar."""

    write_evaluation_report(dataset_path, report_path)
    write_evaluation_timing_report(dataset_path, timing_path)


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
