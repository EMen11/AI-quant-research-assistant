"""Independent checks for the Block 6 timing sidecar."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_quant.evaluation import cli, runner
from ai_quant.evaluation.models import WorkflowEvaluationTimingReport

DATASET = Path("tests/evaluation/workflow_eval.v1.jsonl")
CANONICAL_REPORT = Path("reports/evaluation/workflow_eval.v1.json")


def test_timing_sidecar_uses_monotonic_clock_and_preserves_canonical_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_before = CANONICAL_REPORT.read_bytes()
    generated_report = tmp_path / "workflow_eval.v1.json"
    timing_sidecar = tmp_path / "chosen-sidecar.json"
    evaluation_calls = 0
    real_evaluate_dataset = runner.evaluate_dataset

    def counted_evaluate_dataset(path: Path) -> dict[str, object]:
        nonlocal evaluation_calls
        evaluation_calls += 1
        return real_evaluate_dataset(path)

    clock_values = iter(
        value
        for observation in range(1, 21)
        for value in (observation * 1_000, observation * 1_000 + observation)
    )
    monkeypatch.setattr(runner, "evaluate_dataset", counted_evaluate_dataset)
    monkeypatch.setattr(runner.time, "perf_counter_ns", lambda: next(clock_values))

    runner.write_evaluation_report(DATASET, generated_report)
    runner.write_evaluation_timing_report(DATASET, timing_sidecar)

    parsed = WorkflowEvaluationTimingReport.model_validate_json(
        timing_sidecar.read_text(encoding="utf-8")
    )
    assert time.get_clock_info("perf_counter").monotonic is True
    assert parsed.clock.name == "time.perf_counter_ns"
    assert parsed.clock.monotonic is True
    assert evaluation_calls == 1 + 3 + 20
    assert len(parsed.observations) == 20
    assert parsed.observations == tuple(range(1, 21))
    assert parsed.summary.minimum == min(parsed.observations)
    assert parsed.summary.median == statistics.median(parsed.observations)
    assert parsed.summary.maximum == max(parsed.observations)
    assert generated_report.read_bytes() == canonical_before
    assert CANONICAL_REPORT.read_bytes() == canonical_before


def test_timing_sidecar_schema_is_closed() -> None:
    payload = json.loads(Path("reports/evaluation/workflow_eval.v1.timing.json").read_text())
    payload["unexpected"] = "rejected"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkflowEvaluationTimingReport.model_validate(payload)


def test_cli_accepts_an_explicit_timing_sidecar_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "report.json"
    timing_path = tmp_path / "custom-timing.json"
    received: tuple[Path, Path, Path] | None = None

    def capture_paths(dataset: Path, report: Path, timing: Path) -> None:
        nonlocal received
        received = (dataset, report, timing)

    monkeypatch.setattr(cli, "write_evaluation_artifacts", capture_paths)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ai_quant.evaluation.cli",
            "--dataset",
            str(DATASET),
            "--output",
            str(report_path),
            "--timing-output",
            str(timing_path),
        ],
    )

    cli.main()

    assert received == (DATASET, report_path, timing_path)
