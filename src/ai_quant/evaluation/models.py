"""Closed schemas for the versioned workflow evaluation dataset."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_quant.trust.models import Identifier, StrictModel

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
