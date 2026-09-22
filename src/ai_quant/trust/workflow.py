"""In-memory Block 3 workflow with explicit states and authority boundaries."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from ai_quant.market_data import FrozenSnapshotProvider, SnapshotRun
from ai_quant.quant import QuantAnalysis, analyze_portfolio, demo_portfolio, demo_risk_free_rate
from ai_quant.trust.generation import (
    FixtureDraftGenerator,
    GenerationBudget,
    GenerationController,
    StructuredDraftGenerator,
)
from ai_quant.trust.models import (
    AutomatedAssessment,
    EvidenceRecord,
    GeneratedDraft,
    HumanReview,
    MetricRecord,
    RenderedDraft,
    RunState,
    ValidationReport,
)
from ai_quant.trust.records import (
    create_fake_evidence,
    create_metric_records,
    materialize_generated_draft,
)
from ai_quant.trust.validation import assess_draft, render_validated_draft, validate_draft

DemoScenario = Literal["valid", "blocked"]

WORKFLOW_STEPS = (
    "validate_request",
    "load_snapshot",
    "compute_quant_metrics",
    "retrieve_evidence_fake",
    "generate_draft_fake",
    "validate_draft",
    "assess",
    "request_human_review",
)


class WorkflowTransitionError(RuntimeError):
    """Raised when a run attempts a forbidden state transition."""


class RunStateMachine:
    """Small explicit state machine; automated work stops at pending review."""

    _ALLOWED: dict[RunState, tuple[RunState, ...]] = {
        "created": ("generated",),
        "generated": ("validated",),
        "validated": ("pending_review",),
        "pending_review": ("finalized",),
        "finalized": (),
    }

    def __init__(self) -> None:
        self._state: RunState = "created"

    @property
    def state(self) -> RunState:
        """Return the current state."""

        return self._state

    def transition(self, target: RunState) -> None:
        """Apply an allowed transition or reject it without changing state."""

        if target not in self._ALLOWED[self._state]:
            raise WorkflowTransitionError(
                f"Forbidden workflow transition: {self._state} -> {target}."
            )
        self._state = target


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Complete in-memory result with generation, validation and review kept distinct."""

    run_id: str
    scenario: DemoScenario
    state: RunState
    steps: tuple[str, ...]
    analysis: QuantAnalysis
    metric_records: tuple[MetricRecord, ...]
    evidence_records: tuple[EvidenceRecord, ...]
    draft: GeneratedDraft
    validation_report: ValidationReport
    assessment: AutomatedAssessment
    rendered_draft: RenderedDraft
    human_review: HumanReview | None
    generation_calls: int


class InMemoryTrustWorkflow:
    """Run the fully offline vertical slice without persistence or external services."""

    def run(
        self,
        scenario: DemoScenario,
        *,
        analysis: QuantAnalysis | None = None,
        generator: StructuredDraftGenerator | None = None,
        budget: GenerationBudget | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> WorkflowResult:
        """Execute exactly one bounded fake generation and stop at human review."""

        if scenario not in {"valid", "blocked"}:
            raise ValueError(f"Unsupported demo scenario: {scenario}.")

        run_id = f"run-demo-{scenario}"
        steps: list[str] = ["validate_request"]
        state = RunStateMachine()

        if analysis is None:
            portfolio = demo_portfolio()
            snapshot_run = SnapshotRun(FrozenSnapshotProvider.demo())
            snapshot_run.snapshot_for(portfolio)
            steps.append("load_snapshot")
            analysis = analyze_portfolio(portfolio, snapshot_run, demo_risk_free_rate())
        else:
            steps.append("load_snapshot")
        steps.append("compute_quant_metrics")
        metric_records = create_metric_records(run_id, analysis)

        evidence_records = create_fake_evidence(run_id)
        steps.append("retrieve_evidence_fake")

        selected_generator = generator or (
            FixtureDraftGenerator.valid()
            if scenario == "valid"
            else FixtureDraftGenerator.blocked()
        )
        controller = GenerationController(
            selected_generator,
            budget or GenerationBudget(),
            clock=clock,
        )
        proposal, metadata = controller.generate(
            allowed_metric_ids=tuple(record.metric_id for record in metric_records),
            allowed_evidence_ids=tuple(record.evidence_id for record in evidence_records),
        )
        steps.append("generate_draft_fake")
        draft = materialize_generated_draft(run_id, proposal, metadata)
        state.transition("generated")

        report = validate_draft(
            run_id=run_id,
            draft=draft,
            metrics=metric_records,
            evidence=evidence_records,
        )
        steps.append("validate_draft")
        state.transition("validated")

        assessment = assess_draft(
            run_id=run_id,
            report=report,
            metrics=metric_records,
            evidence=evidence_records,
        )
        rendered = render_validated_draft(
            draft=draft,
            report=report,
            metrics=metric_records,
            evidence=evidence_records,
        )
        steps.append("assess")
        state.transition("pending_review")

        # A human review can only arrive through a later explicit human action.
        human_review = None
        steps.append("request_human_review")
        return WorkflowResult(
            run_id=run_id,
            scenario=scenario,
            state=state.state,
            steps=tuple(steps),
            analysis=analysis,
            metric_records=metric_records,
            evidence_records=evidence_records,
            draft=draft,
            validation_report=report,
            assessment=assessment,
            rendered_draft=rendered,
            human_review=human_review,
            generation_calls=controller.calls_used,
        )


def build_demo_trust_scenarios(
    analysis: QuantAnalysis,
) -> tuple[WorkflowResult, WorkflowResult]:
    """Build both deterministic scenarios over the already-computed Block 2 analysis."""

    workflow = InMemoryTrustWorkflow()
    return workflow.run("valid", analysis=analysis), workflow.run("blocked", analysis=analysis)
