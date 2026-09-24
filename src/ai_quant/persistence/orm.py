"""SQLAlchemy 2 ORM models; domain models never import this module."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative metadata root used by Alembic only."""


class ResearchRunRow(Base):
    __tablename__ = "research_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('created', 'generated', 'validated', 'pending_review', 'finalized')",
            name="ck_runs_state",
        ),
        CheckConstraint("scenario IN ('valid', 'blocked')", name="ck_runs_scenario"),
        CheckConstraint(
            "data_origin IN ('frozen_offline_fixture')", name="ck_runs_data_origin"
        ),
    )

    run_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(80), nullable=False)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketSnapshotRow(Base):
    __tablename__ = "market_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.run_id", ondelete="RESTRICT"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(160), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    __table_args__ = (UniqueConstraint("run_id", "snapshot_id", name="uq_snapshot_run_id"),)


class MetricRecordRow(Base):
    __tablename__ = "metric_records"
    metric_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(160), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(160), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(200), nullable=False)
    horizon_or_frequency: Mapped[str] = mapped_column(String(200), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(200), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["market_snapshots.run_id", "market_snapshots.snapshot_id"],
            ondelete="RESTRICT",
            name="fk_metric_snapshot_same_run",
        ),
        UniqueConstraint("run_id", "metric_id", name="uq_metric_run_id"),
    )


class SourceDocumentRow(Base):
    __tablename__ = "source_documents"
    document_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('synthetic_demo_evidence', 'official_corpus_passage')",
            name="ck_document_source_kind",
        ),
        UniqueConstraint("document_id", "document_sha256", name="uq_document_identity_hash"),
    )


class EvidenceRecordRow(Base):
    __tablename__ = "evidence_records"
    evidence_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.run_id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(String(160), nullable=False)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "document_sha256"],
            ["source_documents.document_id", "source_documents.document_sha256"],
            ondelete="RESTRICT",
            name="fk_evidence_document_hash",
        ),
        CheckConstraint(
            "status IN ('synthetic_demo_evidence', 'official_corpus_passage')",
            name="ck_evidence_status",
        ),
        UniqueConstraint("run_id", "evidence_id", name="uq_evidence_run_id"),
    )


class GeneratedDraftRow(Base):
    __tablename__ = "generated_drafts"
    draft_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.run_id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    generation_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_draft_version_positive"),
        UniqueConstraint("run_id", "version", name="uq_draft_run_version"),
        UniqueConstraint("run_id", "draft_id", name="uq_draft_run_id"),
        UniqueConstraint(
            "run_id", "draft_id", "version", name="uq_draft_run_id_version"
        ),
    )


class DraftClaimRow(Base):
    __tablename__ = "draft_claims"
    claim_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text_template: Mapped[str] = mapped_column(Text, nullable=False)
    declared_metric_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    declared_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    uncertainty: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "draft_id"],
            ["generated_drafts.run_id", "generated_drafts.draft_id"],
            ondelete="RESTRICT",
            name="fk_claim_draft_same_run",
        ),
        CheckConstraint("position > 0", name="ck_claim_position_positive"),
        CheckConstraint(
            "claim_type IN ('quantitative', 'evidence', 'limitation')",
            name="ck_claim_type",
        ),
        CheckConstraint(
            "jsonb_typeof(declared_metric_ids) = 'array' AND "
            "jsonb_path_query_array(declared_metric_ids, "
            "'$[*] ? (@.type() == \"string\")') = declared_metric_ids",
            name="ck_claim_declared_metric_ids_string_array",
        ),
        CheckConstraint(
            "jsonb_typeof(declared_evidence_ids) = 'array' AND "
            "jsonb_path_query_array(declared_evidence_ids, "
            "'$[*] ? (@.type() == \"string\")') = declared_evidence_ids",
            name="ck_claim_declared_evidence_ids_string_array",
        ),
        UniqueConstraint("draft_id", "position", name="uq_claim_draft_position"),
        UniqueConstraint("run_id", "claim_id", name="uq_claim_run_id"),
        UniqueConstraint(
            "run_id", "draft_id", "claim_id", name="uq_claim_run_draft_id"
        ),
    )


class DraftClaimMetricRefRow(Base):
    """Ordered relational claim-to-metric reference with same-run enforcement."""

    __tablename__ = "draft_claim_metric_refs"
    run_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    metric_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "draft_id", "claim_id"],
            ["draft_claims.run_id", "draft_claims.draft_id", "draft_claims.claim_id"],
            ondelete="RESTRICT",
            name="fk_claim_metric_ref_claim_same_run",
        ),
        ForeignKeyConstraint(
            ["run_id", "metric_id"],
            ["metric_records.run_id", "metric_records.metric_id"],
            ondelete="RESTRICT",
            name="fk_claim_metric_ref_metric_same_run",
        ),
        CheckConstraint("position > 0", name="ck_claim_metric_ref_position_positive"),
        UniqueConstraint(
            "run_id",
            "draft_id",
            "claim_id",
            "position",
            name="uq_claim_metric_ref_position",
        ),
    )


class DraftClaimEvidenceRefRow(Base):
    """Ordered relational claim-to-evidence reference with same-run enforcement."""

    __tablename__ = "draft_claim_evidence_refs"
    run_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "draft_id", "claim_id"],
            ["draft_claims.run_id", "draft_claims.draft_id", "draft_claims.claim_id"],
            ondelete="RESTRICT",
            name="fk_claim_evidence_ref_claim_same_run",
        ),
        ForeignKeyConstraint(
            ["run_id", "evidence_id"],
            ["evidence_records.run_id", "evidence_records.evidence_id"],
            ondelete="RESTRICT",
            name="fk_claim_evidence_ref_evidence_same_run",
        ),
        CheckConstraint("position > 0", name="ck_claim_evidence_ref_position_positive"),
        UniqueConstraint(
            "run_id",
            "draft_id",
            "claim_id",
            "position",
            name="uq_claim_evidence_ref_position",
        ),
    )


class ValidationIssueRow(Base):
    __tablename__ = "validation_issues"
    issue_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    claim_id: Mapped[str | None] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "draft_id"],
            ["generated_drafts.run_id", "generated_drafts.draft_id"],
            ondelete="RESTRICT",
            name="fk_issue_draft_same_run",
        ),
        ForeignKeyConstraint(
            ["run_id", "draft_id", "claim_id"],
            ["draft_claims.run_id", "draft_claims.draft_id", "draft_claims.claim_id"],
            ondelete="RESTRICT",
            name="fk_issue_claim_same_draft",
        ),
        CheckConstraint("position > 0", name="ck_issue_position_positive"),
        CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="ck_issue_severity",
        ),
        CheckConstraint(
            "code IN ("
            "'unknown_metric', 'unknown_evidence', 'cross_run_reference', "
            "'free_numeric_literal', 'metric_value_literal', "
            "'evidence_numeric_literal_unverified', 'metric_placeholder_mismatch', "
            "'evidence_reference_mismatch', 'generic_placeholder', "
            "'summary_placeholder', 'unresolved_placeholder', "
            "'unsupported_risk_statement', 'unsupported_period_alignment', "
            "'implicit_cross_domain_relation', 'internal_status_token', "
            "'reference_value_mismatch', 'reference_claim_key_mismatch', "
            "'reference_unit_mismatch', 'reference_period_mismatch', "
            "'scope2_method_mismatch', 'document_after_cutoff', "
            "'contradictory_source', 'missing_required_field', "
            "'insufficient_coverage', 'document_prompt_injection', "
            "'self_approval_attempt', 'insufficient_trusted_inputs')",
            name="ck_issue_code",
        ),
        UniqueConstraint("draft_id", "position", name="uq_issue_draft_position"),
    )


class AutomatedAssessmentRow(Base):
    __tablename__ = "automated_assessments"
    assessment_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "draft_id"],
            ["generated_drafts.run_id", "generated_drafts.draft_id"],
            ondelete="RESTRICT",
            name="fk_assessment_draft_same_run",
        ),
        CheckConstraint(
            "status IN ('eligible_for_review', 'review_required', 'abstain')",
            name="ck_assessment_status",
        ),
        CheckConstraint(
            "(status = 'eligible_for_review' AND "
            "reason_codes = '[\"validated_references\"]'::jsonb) OR "
            "(status = 'review_required' AND "
            "reason_codes = '[\"blocking_validation_issues\"]'::jsonb) OR "
            "(status = 'abstain' AND "
            "reason_codes = '[\"insufficient_trusted_inputs\"]'::jsonb)",
            name="ck_assessment_status_reason_exact",
        ),
        UniqueConstraint("draft_id", name="uq_assessment_draft"),
    )


class HumanReviewRow(Base):
    __tablename__ = "human_reviews"
    review_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(160), nullable=False)
    draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_entered: Mapped[str] = mapped_column(String(200), nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "draft_id", "draft_version"],
            [
                "generated_drafts.run_id",
                "generated_drafts.draft_id",
                "generated_drafts.version",
            ],
            ondelete="RESTRICT",
            name="fk_review_draft_same_run_version",
        ),
        CheckConstraint("draft_version > 0", name="ck_review_version_positive"),
        CheckConstraint("btrim(reviewer_entered) <> ''", name="ck_reviewer_nonblank"),
        CheckConstraint("btrim(comment) <> ''", name="ck_review_comment_nonblank"),
        CheckConstraint(
            "disposition IN ('approved', 'corrected', 'rejected', 'escalated')",
            name="ck_review_disposition",
        ),
        Index("ix_reviews_run_created", "run_id", "reviewed_at"),
    )


class ModelCallRow(Base):
    __tablename__ = "model_calls"
    call_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(160), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    response_origin: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "draft_id"],
            ["generated_drafts.run_id", "generated_drafts.draft_id"],
            ondelete="RESTRICT",
            name="fk_model_call_draft_same_run",
        ),
        CheckConstraint(
            "status IN ('success', 'provider_error', 'timeout', 'schema_error', "
            "'allowlist_error')",
            name="ck_model_call_status",
        ),
        CheckConstraint(
            "response_origin IN ('deterministic_fake', 'synthetic_offline_fixture', "
            "'mocked_provider', 'live_provider')",
            name="ck_model_call_response_origin",
        ),
    )


class EvaluationRunRow(Base):
    __tablename__ = "evaluation_runs"
    evaluation_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    report_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("case_count > 0", name="ck_evaluation_case_count_positive"),
        UniqueConstraint("schema_version", "dataset_sha256", name="uq_evaluation_dataset"),
    )
