"""Offline vertical-slice and state-machine integration tests."""

from __future__ import annotations

import socket

import pytest

from ai_quant.trust import (
    WORKFLOW_STEPS,
    FixtureDraftGenerator,
    GenerationBudget,
    GenerationBudgetExceeded,
    GenerationController,
    GenerationTimeout,
    InMemoryTrustWorkflow,
    RunStateMachine,
    WorkflowTransitionError,
)


def test_valid_scenario_stops_pending_human_review() -> None:
    result = InMemoryTrustWorkflow().run("valid")

    assert result.state == "pending_review"
    assert result.assessment.status == "eligible_for_review"
    assert result.rendered_draft.reliable
    assert result.rendered_draft.final_text
    assert len(result.metric_records) >= 2
    assert len(result.evidence_records) >= 1
    assert result.human_review is None


def test_blocked_scenario_emits_no_reliable_text_or_human_review() -> None:
    result = InMemoryTrustWorkflow().run("blocked")

    assert result.state == "pending_review"
    assert result.assessment.status == "review_required"
    assert result.validation_report.has_blocking_issues
    assert not result.rendered_draft.reliable
    assert result.rendered_draft.final_text is None
    assert result.rendered_draft.claims == ()
    assert result.human_review is None


def test_workflow_executes_documented_steps_once_in_order() -> None:
    result = InMemoryTrustWorkflow().run("valid")

    assert result.steps == WORKFLOW_STEPS
    assert result.generation_calls == 1


def test_state_machine_allows_only_linear_path() -> None:
    machine = RunStateMachine()
    for state in ("generated", "validated", "pending_review", "finalized"):
        machine.transition(state)

    assert machine.state == "finalized"


def test_state_machine_rejects_skipped_transition_without_mutation() -> None:
    machine = RunStateMachine()

    with pytest.raises(WorkflowTransitionError, match="created -> validated"):
        machine.transition("validated")

    assert machine.state == "created"


def test_generation_call_budget_is_enforced_before_second_call() -> None:
    fake = FixtureDraftGenerator.valid()
    controller = GenerationController(fake, GenerationBudget(max_calls=1))
    controller.generate(
        allowed_metric_ids=(
            "metric-run-demo-valid-cumulative-return",
            "metric-run-demo-valid-maximum-drawdown",
        ),
        allowed_evidence_ids=("evidence-run-demo-valid-retrieval-01",),
    )

    with pytest.raises(GenerationBudgetExceeded, match="budget exhausted"):
        controller.generate(
            allowed_metric_ids=(
                "metric-run-demo-valid-cumulative-return",
                "metric-run-demo-valid-maximum-drawdown",
            ),
            allowed_evidence_ids=("evidence-run-demo-valid-retrieval-01",),
        )

    assert fake.call_count == 1


def test_generation_timeout_uses_injected_clock_without_waiting() -> None:
    ticks = iter((10.0, 12.1))
    controller = GenerationController(
        FixtureDraftGenerator.valid(),
        GenerationBudget(timeout_seconds=2.0),
        clock=lambda: next(ticks),
    )

    with pytest.raises(GenerationTimeout, match="exceeded 2 seconds"):
        controller.generate(
            allowed_metric_ids=(
                "metric-run-demo-valid-cumulative-return",
                "metric-run-demo-valid-maximum-drawdown",
            ),
            allowed_evidence_ids=("evidence-run-demo-valid-retrieval-01",),
        )


def test_demo_results_are_deterministic() -> None:
    first = InMemoryTrustWorkflow().run("valid")
    second = InMemoryTrustWorkflow().run("valid")

    assert first.metric_records == second.metric_records
    assert first.draft == second.draft
    assert first.validation_report == second.validation_report
    assert first.rendered_draft == second.rendered_draft


def test_demo_requires_no_network_or_secret(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def reject_network(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", reject_network)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = InMemoryTrustWorkflow().run("valid")

    assert result.assessment.status == "eligible_for_review"
