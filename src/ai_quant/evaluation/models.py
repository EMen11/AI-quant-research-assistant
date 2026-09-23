"""Closed schemas for the versioned workflow evaluation dataset."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from statistics import median
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_quant.trust.models import Identifier, Sha256, StrictModel

Split = Literal["dev", "validation", "holdout"]
ExpectedOutcome = Literal["eligible_for_review", "review_required", "abstain"]
Scope2Method = Literal["location_based", "market_based", "not_applicable"]
ErrorType = Literal[
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
]
PositiveNanoseconds = Annotated[int, Field(gt=0)]


class ReferenceValue(StrictModel):
    """Server-side source of truth supplied to deterministic validators."""

    reference_id: Identifier
    claim_key: Identifier
    value: Decimal
    unit: str
    period: str
    scope2_method: Scope2Method
    publication_date: date
    source_id: Identifier
    contradicted: bool = False
    document_text: str = "Official issuer disclosure."


class ProposedClaim(StrictModel):
    """Untrusted claim fields to compare with a reference record."""

    claim_id: Identifier
    claim_key: Identifier
    reference_id: Identifier | None
    value: Decimal | None
    unit: str | None
    period: str | None
    scope2_method: Scope2Method | None
    requested_assessment: ExpectedOutcome | None = None


class EvaluationInputs(StrictModel):
    """Complete bounded run input, with trusted and untrusted sections separated."""

    run_id: Identifier
    cutoff_date: date
    minimum_claims: int = Field(ge=1)
    references: Annotated[tuple[ReferenceValue, ...], Field(min_length=1)]
    proposed_claims: Annotated[tuple[ProposedClaim, ...], Field(min_length=1)]


class WorkflowEvaluationCase(StrictModel):
    """One independently specified behavior and oracle in workflow_eval.v1."""

    schema_version: Literal["workflow-eval.v1"]
    case_id: Identifier
    split: Split
    inputs: EvaluationInputs
    required_claims: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    acceptable_claims: tuple[Identifier, ...]
    forbidden_claims: tuple[Identifier, ...]
    expected_outcome: ExpectedOutcome
    severity: Literal["none", "warning", "error", "critical"]
    error_types: tuple[ErrorType, ...]

    @model_validator(mode="after")
    def oracle_is_coherent(self) -> WorkflowEvaluationCase:
        if self.severity == "none" and self.error_types:
            raise ValueError("A clean case cannot declare an error type.")
        if self.severity == "critical" and self.expected_outcome == "eligible_for_review":
            raise ValueError("A known critical case cannot be eligible for review.")
        claim_sets = (set(self.required_claims), set(self.acceptable_claims), set(self.forbidden_claims))
        if claim_sets[0] & claim_sets[2] or claim_sets[1] & claim_sets[2]:
            raise ValueError("Forbidden claims cannot also be required or acceptable.")
        return self


class TimingClock(StrictModel):
    """Monotonic clock used for the wall-clock observations."""

    name: Literal["time.perf_counter_ns"]
    monotonic: Literal[True]
    resolution_ns: PositiveNanoseconds


class TimingDataset(StrictModel):
    """Dataset identity for the measured workflow."""

    version: Literal["workflow-eval.v1"]
    sha256: Sha256
    path: Annotated[str, Field(min_length=1)]
    case_count: int = Field(gt=0)


class TimingEnvironment(StrictModel):
    """Non-secret execution environment metadata relevant to timing variability."""

    python_version: Annotated[str, Field(min_length=1)]
    python_implementation: Annotated[str, Field(min_length=1)]
    python_compiler: Annotated[str, Field(min_length=1)]
    platform_system: Annotated[str, Field(min_length=1)]
    platform_release: Annotated[str, Field(min_length=1)]
    platform_machine: Annotated[str, Field(min_length=1)]
    processor: str
    logical_cpu_count: int | None = Field(default=None, gt=0)


class TimingSummary(StrictModel):
    """Summary statistics computed directly from the observations."""

    minimum: PositiveNanoseconds
    median: float = Field(gt=0)
    maximum: PositiveNanoseconds


class WorkflowEvaluationTimingReport(StrictModel):
    """Closed, versioned schema for non-reproducible workflow timings."""

    schema_version: Literal["workflow-evaluation-timing.v1"]
    measurement_scope: Literal[
        "dataset_loading_validation_assessment_report_aggregation"
    ]
    warmup_runs: Literal[3]
    measured_runs: Literal[20]
    unit: Literal["nanoseconds"]
    clock: TimingClock
    dataset: TimingDataset
    environment: TimingEnvironment
    observations: Annotated[
        tuple[PositiveNanoseconds, ...], Field(min_length=20, max_length=20)
    ]
    summary: TimingSummary
    reproducibility_notice: Literal[
        "Durations depend on hardware, caches, scheduling, and system load; "
        "they are not byte-for-byte reproducible and are not a portable benchmark."
    ]

    @model_validator(mode="after")
    def summary_matches_observations(self) -> WorkflowEvaluationTimingReport:
        if self.measured_runs != len(self.observations):
            raise ValueError("measured_runs must match the number of observations.")
        expected = TimingSummary(
            minimum=min(self.observations),
            median=float(median(self.observations)),
            maximum=max(self.observations),
        )
        if self.summary != expected:
            raise ValueError("Timing summary must be derived from the observations.")
        return self
