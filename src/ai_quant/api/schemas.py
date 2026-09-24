"""Closed public API contracts; ORM types never cross this boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_quant.trust.models import (
    AssessmentStatus,
    EvidenceStatus,
    HumanDisposition,
    IssueCode,
    IssueSeverity,
    RunState,
)

ApiErrorCode = Literal[
    "invalid_request",
    "not_found",
    "conflict",
    "correction_unrepresentable",
    "persistence_conflict",
    "internal_error",
]
DataOrigin = Literal["frozen_offline_fixture"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AnalysisCreate(ApiModel):
    scenario: Literal["valid", "blocked"]
    data_mode: DataOrigin = "frozen_offline_fixture"


class FindingResponse(ApiModel):
    code: IssueCode
    severity: IssueSeverity
    claim_id: str | None
    message: str


class ClaimReferenceAuditResponse(ApiModel):
    """Declared audit input kept separate from FK-backed accepted references."""

    claim_id: str
    declared_metric_ids: tuple[str, ...]
    declared_evidence_ids: tuple[str, ...]
    accepted_metric_ids: tuple[str, ...]
    accepted_evidence_ids: tuple[str, ...]
    reference_status: Literal["accepted", "declared_untrusted"]


class AnalysisResponse(ApiModel):
    analysis_id: str
    state: RunState
    scenario: Literal["valid", "blocked"]
    data_origin: DataOrigin
    draft_id: str
    draft_version: int
    summary: str
    claims: tuple[str, ...]
    claim_references: tuple[ClaimReferenceAuditResponse, ...]
    automated_status: AssessmentStatus
    reliable: bool
    final_text: str | None
    findings: tuple[FindingResponse, ...]
    created_at: datetime


class EvidenceResponse(ApiModel):
    evidence_id: str
    document_id: str
    document_sha256: str
    status: EvidenceStatus
    payload: dict[str, object]


class ClaimReferenceReplacement(ApiModel):
    """Complete declared-reference replacement for one corrected claim position."""

    declared_metric_ids: list[Annotated[str, Field(min_length=1, max_length=160)]]
    declared_evidence_ids: list[Annotated[str, Field(min_length=1, max_length=160)]]

    @model_validator(mode="after")
    def references_are_unique(self) -> ClaimReferenceReplacement:
        if len(set(self.declared_metric_ids)) != len(self.declared_metric_ids):
            raise ValueError("declared_metric_ids must be unique within a claim")
        if len(set(self.declared_evidence_ids)) != len(self.declared_evidence_ids):
            raise ValueError("declared_evidence_ids must be unique within a claim")
        return self


class ReviewCreate(ApiModel):
    draft_id: Annotated[str, Field(min_length=3, max_length=160)]
    draft_version: Annotated[int, Field(gt=0)]
    reviewer: Annotated[str, Field(min_length=1, max_length=200)]
    disposition: HumanDisposition
    comment: Annotated[str, Field(min_length=1, max_length=2_000)]
    corrected_summary: Annotated[str, Field(min_length=1, max_length=2_000)] | None = None
    corrected_claims: list[Annotated[str, Field(min_length=1, max_length=1_000)]] | None = None
    corrected_references: list[ClaimReferenceReplacement] | None = None

    @field_validator("reviewer", "comment")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("corrected_summary")
    @classmethod
    def optional_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("corrected_claims")
    @classmethod
    def corrected_claims_not_blank(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value]
        if not cleaned or any(not item for item in cleaned):
            raise ValueError("corrected_claims must contain non-blank claims")
        return cleaned


class ReviewResponse(ApiModel):
    review_id: str
    analysis_id: str
    draft_id: str
    draft_version: int
    reviewer_entered: str
    reviewer_identity: Literal["entered_unverified_unauthenticated"]
    disposition: HumanDisposition
    comment: str
    reviewed_at: datetime
    resulting_draft_id: str | None = None
    resulting_draft_version: int | None = None


class EvaluationResponse(ApiModel):
    evaluation_id: str
    schema_version: str
    dataset_sha256: str
    case_count: int
    report: dict[str, object]
    created_at: datetime


class HealthResponse(ApiModel):
    status: Literal["ok"]
    database: Literal["reachable"]


class ErrorBody(ApiModel):
    code: ApiErrorCode
    message: str


class ErrorResponse(ApiModel):
    error: ErrorBody
