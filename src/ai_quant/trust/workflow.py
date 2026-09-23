"""In-memory Block 3 workflow with explicit states and authority boundaries."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from ai_quant.llm import (
    LLMClient,
    LLMClientError,
    LLMEvidenceInput,
    LLMMetricInput,
    SynthesisLimits,
    SynthesisRequest,
)
from ai_quant.market_data import FrozenSnapshotProvider, SnapshotRun
from ai_quant.model_calls import ModelCallMetadata
from ai_quant.quant import QuantAnalysis, analyze_portfolio, demo_portfolio, demo_risk_free_rate
from ai_quant.retrieval import PassageFilter, RetrievalResult, evidence_records_from_results
from ai_quant.trust.generation import (
    FixtureDraftGenerator,
    GenerationBudget,
    GenerationController,
    GenerationError,
    LLMStructuredDraftGenerator,
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
    "retrieve_evidence_fixture",
    "generate_draft_fixture",
    "validate_draft",
    "assess",
    "request_human_review",
)


class WorkflowTransitionError(RuntimeError):
    """Raised when a run attempts a forbidden state transition."""


class PassageRetriever(Protocol):
    """Minimal injected retrieval interface used by the workflow."""

    def search(
        self,
        query: str,
        *,
        filters: PassageFilter | None = None,
        top_k: int = 3,
    ) -> tuple[RetrievalResult, ...]:
        """Return ranked, fully traceable passages."""


class WorkflowGenerationError(RuntimeError):
    """Generation failed after deterministic metrics and evidence were preserved."""

    def __init__(
        self,
        *,
        analysis: QuantAnalysis,
        metrics: tuple[MetricRecord, ...],
        evidence: tuple[EvidenceRecord, ...],
        model_call: ModelCallMetadata | None,
        error_code: str,
        generation_calls: int,
    ) -> None:
        super().__init__("Structured generation failed; trusted inputs remain available.")
        self.analysis = analysis
        self.metric_records = metrics
        self.evidence_records = evidence
        self.model_call = model_call
        self.error_code = error_code
        self.status = "generation_failed" if model_call is None else model_call.status
        self.generation_calls = generation_calls
        self.draft = None
        self.validation_report = None


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
        retriever: PassageRetriever | None = None,
        retrieval_query: str = "climate emissions energy targets",
        retrieval_filters: PassageFilter | None = None,
        llm_client: LLMClient | None = None,
        synthesis_limits: SynthesisLimits | None = None,
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

        if generator is not None and llm_client is not None:
            raise ValueError("Inject either generator or llm_client, not both.")
        fixture_generator: FixtureDraftGenerator | None = None
        if llm_client is None:
            if isinstance(generator, FixtureDraftGenerator):
                fixture_generator = generator
            elif generator is None:
                fixture_generator = (
                    FixtureDraftGenerator.valid()
                    if scenario == "valid"
                    else FixtureDraftGenerator.blocked()
                )

        if retriever is None:
            approved_evidence = (
                ()
                if fixture_generator is None
                else fixture_generator.public_evidence_for(run_id)
            )
            if approved_evidence:
                evidence_records = approved_evidence
                steps.append("retrieve_evidence_fixture")
            else:
                evidence_records = create_fake_evidence(run_id)
                steps.append("retrieve_evidence_fake")
        else:
            retrieval_results = retriever.search(
                retrieval_query,
                filters=retrieval_filters,
                top_k=3,
            )
            evidence_records = evidence_records_from_results(run_id, retrieval_results)
            steps.append("retrieve_evidence")

        if llm_client is not None:
            selected_limits = synthesis_limits or SynthesisLimits()
            if budget is not None and budget.timeout_seconds < selected_limits.timeout_seconds:
                raise ValueError(
                    "Generation budget timeout cannot be shorter than the transport timeout."
                )
            request = build_synthesis_request(
                run_id=run_id,
                metrics=metric_records,
                evidence=evidence_records,
                limits=selected_limits,
            )
            selected_generator: StructuredDraftGenerator = LLMStructuredDraftGenerator(
                llm_client,
                request,
            )
            generation_step = "generate_draft"
            selected_budget = budget or GenerationBudget(
                timeout_seconds=selected_limits.timeout_seconds
            )
        else:
            selected_generator = generator or fixture_generator
            assert selected_generator is not None
            generation_step = "generate_draft_fixture"
            selected_budget = budget or GenerationBudget()
        controller = GenerationController(
            selected_generator,
            selected_budget,
            clock=clock,
        )
        generation_failure: WorkflowGenerationError | None = None
        try:
            proposal, metadata = controller.generate(
                allowed_metric_ids=tuple(record.metric_id for record in metric_records),
                allowed_evidence_ids=tuple(record.evidence_id for record in evidence_records),
            )
        except (LLMClientError, GenerationError) as exc:
            model_call = (
                exc.metadata if isinstance(exc, LLMClientError) else exc.model_call
            )
            generation_failure = WorkflowGenerationError(
                analysis=analysis,
                metrics=metric_records,
                evidence=evidence_records,
                model_call=model_call,
                error_code=exc.error_code,
                generation_calls=controller.calls_used,
            )
        if generation_failure is not None:
            raise generation_failure from None
        steps.append(generation_step)
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
            report=report,
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


def build_synthesis_request(
    *,
    run_id: str,
    metrics: tuple[MetricRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
    limits: SynthesisLimits,
    context: str | None = None,
    prompt_version: str = "trust-synthesis-v3",
) -> SynthesisRequest:
    """Build the strict LLM request from server-owned run records."""

    metric_inputs = tuple(
        LLMMetricInput(
            metric_id=record.metric_id,
            run_id=record.run_id,
            metric_name=record.metric_name,
            value=record.value,
            unit=record.unit,
        )
        for record in metrics
    )
    evidence_inputs = tuple(
        LLMEvidenceInput(
            evidence_id=record.evidence_id,
            run_id=record.run_id,
            excerpt=record.excerpt,
            provenance_label=record.status,
        )
        for record in evidence
    )
    selected_context = context or "\n\n".join(
        f"evidence_id={record.evidence_id}\n{record.excerpt}" for record in evidence
    )
    return SynthesisRequest(
        run_id=run_id,
        prompt_version=prompt_version,
        context=selected_context or "No evidence was retrieved.",
        metrics=metric_inputs,
        evidence=evidence_inputs,
        allowed_metric_ids=tuple(record.metric_id for record in metric_inputs),
        allowed_evidence_ids=tuple(record.evidence_id for record in evidence_inputs),
        limits=limits,
    )
