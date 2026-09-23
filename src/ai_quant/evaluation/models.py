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
    "reference_claim_key_mismatch",
    "cross_run_reference",
    "insufficient_trusted_inputs",
]
PositiveNanoseconds = Annotated[int, Field(gt=0)]


class ReferenceValue(StrictModel):
    """Server-side source of truth supplied to deterministic validators."""

    reference_id: Identifier
    run_id: Identifier
    claim_key: Identifier
    value: Decimal
    unit: str
    period: str
    scope2_method: Scope2Method
    publication_date: date
    source_id: Identifier
    contradicted_by_source_id: Identifier | None = None
    document_text: str = "Official issuer disclosure."


class ProposedClaim(StrictModel):
    """Untrusted claim fields to compare with a reference record."""

    claim_id: Identifier
    claim_key: Identifier
    claim_text: Annotated[str, Field(min_length=1, max_length=1_000)]
    reference_id: Identifier | None
    value: Decimal | None
    unit: str | None
    period: str | None
    scope2_method: Scope2Method | None


class EvaluationInputs(StrictModel):
    """Complete bounded run input, with trusted and untrusted sections separated."""

    run_id: Identifier
    cutoff_date: date
    minimum_claims: int = Field(ge=1)
    references: tuple[ReferenceValue, ...]
    proposed_claims: tuple[ProposedClaim, ...]

    @model_validator(mode="after")
    def run_and_record_identifiers_are_consistent(self) -> EvaluationInputs:
        if len({reference.reference_id for reference in self.references}) != len(
            self.references
        ):
            raise ValueError("reference_id values must be unique within an evaluation case.")
        if len({claim.claim_id for claim in self.proposed_claims}) != len(
            self.proposed_claims
        ):
            raise ValueError("claim_id values must be unique within an evaluation case.")
        if any(
            not claim.claim_id.startswith(f"claim-{self.run_id}-")
            for claim in self.proposed_claims
        ):
            raise ValueError("Every claim_id must belong to the active evaluation run.")
        if any(
            not reference.reference_id.startswith(f"evidence-{reference.run_id}-")
            for reference in self.references
        ):
            raise ValueError("Every reference_id must agree with its declared run_id.")
        return self


class WorkflowEvaluationCase(StrictModel):
    """One independently specified behavior and oracle in workflow_eval.v1."""

    schema_version: Literal["workflow-eval.v1"]
    case_id: Identifier
    split: Split
    inputs: EvaluationInputs
    required_claims: tuple[Identifier, ...]
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
    filename: Annotated[str, Field(min_length=1)]
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
    measurement_scope: Literal["deterministic_validation_evaluation_pipeline"]
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
