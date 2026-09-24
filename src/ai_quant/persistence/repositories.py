"""Explicit append-only repositories and domain-to-ORM mappings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ai_quant.persistence.orm import (
    AutomatedAssessmentRow,
    DraftClaimEvidenceRefRow,
    DraftClaimMetricRefRow,
    DraftClaimRow,
    EvaluationRunRow,
    EvidenceRecordRow,
    GeneratedDraftRow,
    HumanReviewRow,
    MarketSnapshotRow,
    MetricRecordRow,
    ModelCallRow,
    ResearchRunRow,
    SourceDocumentRow,
    ValidationIssueRow,
)
from ai_quant.trust import (
    AutomatedAssessment,
    ClaimDraft,
    EvidenceRecord,
    GeneratedDraft,
    GenerationMetadata,
    MetricRecord,
    RenderedDraft,
    ValidationIssue,
    ValidationReport,
    WorkflowResult,
    assess_draft,
    render_validated_draft,
    validate_draft,
)
from ai_quant.trust.validation import build_validation_report


class PersistenceConflict(RuntimeError):
    """A requested append would overwrite or contradict historical state."""


class IdempotencyConflict(PersistenceConflict):
    """An idempotency key was reused with a different canonical payload."""


@dataclass(frozen=True, slots=True)
class StoredRun:
    run_id: str
    response_payload: dict[str, object]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredCorrection:
    draft: GeneratedDraftRow
    validation_report: ValidationReport
    assessment: AutomatedAssessment
    rendered_draft: RenderedDraft


@dataclass(frozen=True, slots=True)
class StoredClaimReferenceAudit:
    claim_id: str
    declared_metric_ids: tuple[str, ...]
    declared_evidence_ids: tuple[str, ...]
    accepted_metric_ids: tuple[str, ...]
    accepted_evidence_ids: tuple[str, ...]


def canonical_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ResearchRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_idempotency_key(self, key: str) -> None:
        """Serialize creators for one key for the current PostgreSQL transaction."""

        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )

    def by_idempotency_key(self, key: str) -> ResearchRunRow | None:
        return self._session.scalar(
            select(ResearchRunRow).where(ResearchRunRow.idempotency_key == key)
        )

    def get(self, run_id: str) -> ResearchRunRow | None:
        return self._session.get(ResearchRunRow, run_id)

    def get_for_update(self, run_id: str) -> ResearchRunRow | None:
        """Lock the stable run row before reading a mutable current-version projection."""

        return self._session.scalar(
            select(ResearchRunRow)
            .where(ResearchRunRow.run_id == run_id)
            .with_for_update()
        )

    def add(self, row: ResearchRunRow) -> None:
        if self.get(row.run_id) is not None:
            raise PersistenceConflict("research run already exists")
        self._session.add(row)


class ArtifactRepository:
    """Append complete workflow artifacts; no update or delete operation is exposed."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append_workflow(self, result: WorkflowResult, *, created_at: datetime) -> None:
        snapshot = result.analysis.snapshot
        self._session.add(
            MarketSnapshotRow(
                run_id=result.run_id,
                snapshot_id=snapshot.snapshot_id,
                provider=snapshot.provider,
                content_sha256=snapshot.content_sha256,
                artifact_uri=snapshot.artifact_uri,
                retrieved_at=snapshot.retrieved_at,
                payload=_jsonable(snapshot),
            )
        )
        self._session.flush()
        self._session.add_all(
            MetricRecordRow(**record.model_dump(mode="json"))
            for record in result.metric_records
        )
        for record in result.evidence_records:
            self._session.execute(
                pg_insert(SourceDocumentRow)
                .values(
                    document_id=record.document_id,
                    document_sha256=record.document_sha256,
                    title=record.document_id,
                    source_kind=record.status,
                    metadata_payload={
                        "publication_date": (
                            record.publication_date.isoformat()
                            if record.publication_date
                            else None
                        ),
                        "issuer_id": record.issuer_id,
                    },
                )
                .on_conflict_do_nothing(index_elements=["document_id"])
            )
            document_hash = self._session.scalar(
                select(SourceDocumentRow.document_sha256).where(
                    SourceDocumentRow.document_id == record.document_id
                )
            )
            if document_hash != record.document_sha256:
                raise PersistenceConflict("source document identity has a different hash")
            self._session.add(
                EvidenceRecordRow(
                    evidence_id=record.evidence_id,
                    run_id=record.run_id,
                    document_id=record.document_id,
                    document_sha256=record.document_sha256,
                    status=record.status,
                    payload=record.model_dump(mode="json"),
                )
            )

        draft = result.draft
        self._session.add(
            GeneratedDraftRow(
                draft_id=draft.draft_id,
                run_id=draft.run_id,
                version=1,
                summary=draft.summary,
                limitations=list(draft.limitations),
                generation_payload=draft.generation.model_dump(mode="json"),
                created_at=created_at,
            )
        )
        self._session.flush()
        self._append_claims(
            draft,
            allowed_metric_ids=frozenset(
                record.metric_id for record in result.metric_records
            ),
            allowed_evidence_ids=frozenset(
                record.evidence_id for record in result.evidence_records
            ),
        )
        self._session.add_all(
            ValidationIssueRow(
                issue_id=f"issue-{draft.draft_id}-{position:03d}",
                run_id=draft.run_id,
                draft_id=draft.draft_id,
                position=position,
                code=issue.code,
                severity=issue.severity,
                claim_id=issue.claim_id,
                message=issue.message,
            )
            for position, issue in enumerate(result.validation_report.issues, start=1)
        )
        self._session.add(
            AutomatedAssessmentRow(
                assessment_id=f"assessment-{draft.draft_id}",
                run_id=draft.run_id,
                draft_id=draft.draft_id,
                status=result.assessment.status,
                reason_codes=list(result.assessment.reason_codes),
                created_at=created_at,
            )
        )
        call = draft.generation.model_call
        if call is not None:
            self._session.add(
                ModelCallRow(
                    call_id=f"call-{draft.draft_id}",
                    run_id=draft.run_id,
                    draft_id=draft.draft_id,
                    provider=call.provider,
                    model_id=call.model_id,
                    status=call.status,
                    response_origin=call.response_origin,
                    payload=call.model_dump(mode="json"),
                )
            )

    def evidence(self, run_id: str) -> list[EvidenceRecordRow]:
        return list(
            self._session.scalars(
                select(EvidenceRecordRow)
                .where(EvidenceRecordRow.run_id == run_id)
                .order_by(EvidenceRecordRow.evidence_id)
            )
        )

    def current_draft(self, run_id: str) -> GeneratedDraftRow | None:
        return self._session.scalar(
            select(GeneratedDraftRow)
            .where(GeneratedDraftRow.run_id == run_id)
            .order_by(desc(GeneratedDraftRow.version))
            .limit(1)
        )

    def assessment(self, draft_id: str) -> AutomatedAssessmentRow | None:
        return self._session.scalar(
            select(AutomatedAssessmentRow).where(
                AutomatedAssessmentRow.draft_id == draft_id
            )
        )

    def claims(self, draft_id: str) -> tuple[DraftClaimRow, ...]:
        return tuple(
            self._session.scalars(
                select(DraftClaimRow)
                .where(DraftClaimRow.draft_id == draft_id)
                .order_by(DraftClaimRow.position)
            )
        )

    def domain_claims(self, draft_id: str) -> tuple[ClaimDraft, ...]:
        return tuple(
            ClaimDraft.model_construct(
                claim_id=row.claim_id,
                run_id=row.run_id,
                text_template=row.text_template,
                claim_type=row.claim_type,  # type: ignore[arg-type]
                metric_ids=tuple(row.declared_metric_ids),
                evidence_ids=tuple(row.declared_evidence_ids),
                uncertainty=row.uncertainty,
            )
            for row in self.claims(draft_id)
        )

    def claim_reference_audits(
        self, draft_id: str
    ) -> tuple[StoredClaimReferenceAudit, ...]:
        """Expose declared audit data and FK-backed accepted references separately."""

        metric_refs = self._ordered_metric_refs(draft_id)
        evidence_refs = self._ordered_evidence_refs(draft_id)
        return tuple(
            StoredClaimReferenceAudit(
                claim_id=row.claim_id,
                declared_metric_ids=tuple(row.declared_metric_ids),
                declared_evidence_ids=tuple(row.declared_evidence_ids),
                accepted_metric_ids=tuple(metric_refs.get(row.claim_id, ())),
                accepted_evidence_ids=tuple(evidence_refs.get(row.claim_id, ())),
            )
            for row in self.claims(draft_id)
        )

    def domain_assessment(self, draft_id: str) -> AutomatedAssessment | None:
        """Revalidate persisted authorization state through the domain model."""

        row = self.assessment(draft_id)
        if row is None:
            return None
        try:
            return AutomatedAssessment(
                run_id=row.run_id,
                status=row.status,  # type: ignore[arg-type]
                reason_codes=tuple(row.reason_codes),  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as error:
            raise PersistenceConflict(
                "persisted assessment violates the domain authorization contract"
            ) from error

    def issues(self, draft_id: str) -> tuple[ValidationIssueRow, ...]:
        return tuple(
            self._session.scalars(
                select(ValidationIssueRow)
                .where(ValidationIssueRow.draft_id == draft_id)
                .order_by(ValidationIssueRow.position)
            )
        )

    def domain_draft(self, row: GeneratedDraftRow) -> GeneratedDraft:
        return GeneratedDraft(
            draft_id=row.draft_id,
            run_id=row.run_id,
            summary=row.summary,
            claims=self.domain_claims(row.draft_id),
            limitations=tuple(row.limitations),
            generation=GenerationMetadata.model_validate_json(
                json.dumps(row.generation_payload)
            ),
        )

    def validation_report(self, row: GeneratedDraftRow) -> ValidationReport:
        issues = tuple(
            ValidationIssue(
                code=issue.code,  # type: ignore[arg-type]
                severity=issue.severity,  # type: ignore[arg-type]
                claim_id=issue.claim_id,
                message=issue.message,
            )
            for issue in self.issues(row.draft_id)
        )
        return build_validation_report(
            run_id=row.run_id,
            draft_id=row.draft_id,
            issues=issues,
            trusted_input_count=len(self.metrics(row.run_id)) + len(self.domain_evidence(row.run_id)),
        )

    def rendered_draft(self, row: GeneratedDraftRow) -> RenderedDraft:
        return render_validated_draft(
            draft=self.domain_draft(row),
            report=self.validation_report(row),
            metrics=self.metrics(row.run_id),
            evidence=self.domain_evidence(row.run_id),
        )

    def metrics(self, run_id: str) -> tuple[MetricRecord, ...]:
        rows = self._session.scalars(
            select(MetricRecordRow)
            .where(MetricRecordRow.run_id == run_id)
            .order_by(MetricRecordRow.metric_id)
        )
        return tuple(
            MetricRecord(
                metric_id=row.metric_id,
                run_id=row.run_id,
                metric_name=row.metric_name,
                value=row.value,
                unit=row.unit,
                horizon_or_frequency=row.horizon_or_frequency,
                formula_version=row.formula_version,
                snapshot_id=row.snapshot_id,
            )
            for row in rows
        )

    def domain_evidence(self, run_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(
            EvidenceRecord.model_validate_json(json.dumps(row.payload))
            for row in self.evidence(run_id)
        )

    def append_correction(
        self,
        current: GeneratedDraftRow,
        *,
        summary: str,
        claim_templates: tuple[str, ...],
        declared_metric_ids: tuple[tuple[str, ...], ...] | None,
        declared_evidence_ids: tuple[tuple[str, ...], ...] | None,
        created_at: datetime,
    ) -> StoredCorrection:
        old_draft = self.domain_draft(current)
        old_claims = old_draft.claims
        if len(old_claims) != len(claim_templates):
            raise PersistenceConflict("correction must preserve the atomic claim count")
        if declared_metric_ids is not None and len(declared_metric_ids) != len(old_claims):
            raise PersistenceConflict("metric reference replacements must match claim count")
        if declared_evidence_ids is not None and len(declared_evidence_ids) != len(old_claims):
            raise PersistenceConflict("evidence reference replacements must match claim count")
        version = current.version + 1
        draft_id = f"draft-{current.run_id}-v{version:02d}"
        corrected_draft = GeneratedDraft(
            draft_id=draft_id,
            run_id=current.run_id,
            summary=summary,
            claims=tuple(
                ClaimDraft.model_construct(
                    claim_id=f"claim-{current.run_id}-v{version:02d}-{position:02d}",
                    run_id=current.run_id,
                    text_template=template,
                    claim_type=old.claim_type,
                    metric_ids=(
                        declared_metric_ids[position - 1]
                        if declared_metric_ids is not None
                        else old.metric_ids
                    ),
                    evidence_ids=(
                        declared_evidence_ids[position - 1]
                        if declared_evidence_ids is not None
                        else old.evidence_ids
                    ),
                    uncertainty=old.uncertainty,
                )
                for position, (old, template) in enumerate(
                    zip(old_claims, claim_templates, strict=True), start=1
                )
            ),
            limitations=old_draft.limitations,
            generation=old_draft.generation,
        )
        metrics = self.metrics(current.run_id)
        evidence = self.domain_evidence(current.run_id)
        report = validate_draft(
            run_id=current.run_id,
            draft=corrected_draft,
            metrics=metrics,
            evidence=evidence,
        )
        assessment = assess_draft(report=report)
        rendered = render_validated_draft(
            draft=corrected_draft,
            report=report,
            metrics=metrics,
            evidence=evidence,
        )
        row = GeneratedDraftRow(
            draft_id=draft_id,
            run_id=current.run_id,
            version=version,
            summary=summary,
            limitations=list(corrected_draft.limitations),
            generation_payload=corrected_draft.generation.model_dump(mode="json"),
            created_at=created_at,
        )
        self._session.add(row)
        self._session.flush()
        self._append_claims(
            corrected_draft,
            allowed_metric_ids=frozenset(record.metric_id for record in metrics),
            allowed_evidence_ids=frozenset(record.evidence_id for record in evidence),
        )
        self._session.add_all(
            ValidationIssueRow(
                issue_id=f"issue-{draft_id}-{position:03d}",
                run_id=current.run_id,
                draft_id=draft_id,
                position=position,
                code=issue.code,
                severity=issue.severity,
                claim_id=issue.claim_id,
                message=issue.message,
            )
            for position, issue in enumerate(report.issues, start=1)
        )
        self._session.add(
            AutomatedAssessmentRow(
                assessment_id=f"assessment-{draft_id}",
                run_id=current.run_id,
                draft_id=draft_id,
                status=assessment.status,
                reason_codes=list(assessment.reason_codes),
                created_at=created_at,
            )
        )
        return StoredCorrection(
            draft=row,
            validation_report=report,
            assessment=assessment,
            rendered_draft=rendered,
        )

    def _append_claims(
        self,
        draft: GeneratedDraft,
        *,
        allowed_metric_ids: frozenset[str],
        allowed_evidence_ids: frozenset[str],
    ) -> None:
        self._session.add_all(
            DraftClaimRow(
                claim_id=claim.claim_id,
                run_id=claim.run_id,
                draft_id=draft.draft_id,
                position=position,
                claim_type=claim.claim_type,
                text_template=claim.text_template,
                declared_metric_ids=list(claim.metric_ids),
                declared_evidence_ids=list(claim.evidence_ids),
                uncertainty=claim.uncertainty,
            )
            for position, claim in enumerate(draft.claims, start=1)
        )
        self._session.flush()
        metric_refs = []
        evidence_refs = []
        for claim in draft.claims:
            metric_refs.extend(
                DraftClaimMetricRefRow(
                    run_id=draft.run_id,
                    draft_id=draft.draft_id,
                    claim_id=claim.claim_id,
                    metric_id=metric_id,
                    position=position,
                )
                for position, metric_id in enumerate(
                    (
                        metric_id
                        for metric_id in claim.metric_ids
                        if metric_id in allowed_metric_ids
                    ),
                    start=1,
                )
            )
            evidence_refs.extend(
                DraftClaimEvidenceRefRow(
                    run_id=draft.run_id,
                    draft_id=draft.draft_id,
                    claim_id=claim.claim_id,
                    evidence_id=evidence_id,
                    position=position,
                )
                for position, evidence_id in enumerate(
                    (
                        evidence_id
                        for evidence_id in claim.evidence_ids
                        if evidence_id in allowed_evidence_ids
                    ),
                    start=1,
                )
            )
        self._session.add_all((*metric_refs, *evidence_refs))
        self._session.flush()

    def _ordered_metric_refs(self, draft_id: str) -> dict[str, list[str]]:
        references: dict[str, list[str]] = {}
        rows = self._session.scalars(
            select(DraftClaimMetricRefRow)
            .where(DraftClaimMetricRefRow.draft_id == draft_id)
            .order_by(DraftClaimMetricRefRow.claim_id, DraftClaimMetricRefRow.position)
        )
        for row in rows:
            references.setdefault(row.claim_id, []).append(row.metric_id)
        return references

    def _ordered_evidence_refs(self, draft_id: str) -> dict[str, list[str]]:
        references: dict[str, list[str]] = {}
        rows = self._session.scalars(
            select(DraftClaimEvidenceRefRow)
            .where(DraftClaimEvidenceRefRow.draft_id == draft_id)
            .order_by(DraftClaimEvidenceRefRow.claim_id, DraftClaimEvidenceRefRow.position)
        )
        for row in rows:
            references.setdefault(row.claim_id, []).append(row.evidence_id)
        return references


class HumanReviewRepository:
    """Append reviews only; reviewer text is entered, unverified and unauthenticated."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, row: HumanReviewRow) -> None:
        if self._session.get(HumanReviewRow, row.review_id) is not None:
            raise PersistenceConflict("review already exists")
        self._session.add(row)

    def for_run(self, run_id: str) -> list[HumanReviewRow]:
        return list(
            self._session.scalars(
                select(HumanReviewRow)
                .where(HumanReviewRow.run_id == run_id)
                .order_by(HumanReviewRow.reviewed_at, HumanReviewRow.review_id)
            )
        )


class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest(self) -> EvaluationRunRow | None:
        return self._session.scalar(
            select(EvaluationRunRow).order_by(desc(EvaluationRunRow.created_at)).limit(1)
        )

    def append_if_absent(
        self, report: dict[str, object], *, created_at: datetime
    ) -> None:
        versions = report.get("versions")
        if not isinstance(versions, dict):
            raise PersistenceConflict("evaluation report has no versions object")
        dataset_sha256 = versions.get("dataset_sha256")
        schema_version = report.get("schema_version")
        case_count = report.get("case_count")
        if (
            not isinstance(dataset_sha256, str)
            or not isinstance(schema_version, str)
            or not isinstance(case_count, int)
        ):
            raise PersistenceConflict("evaluation report identity is invalid")
        self._session.execute(
            pg_insert(EvaluationRunRow)
            .values(
                evaluation_id=f"evaluation-{dataset_sha256[:24]}",
                schema_version=schema_version,
                dataset_sha256=dataset_sha256,
                case_count=case_count,
                report_payload=report,
                created_at=created_at,
            )
            .on_conflict_do_nothing(
                index_elements=["schema_version", "dataset_sha256"]
            )
        )


@dataclass(frozen=True, slots=True)
class AnalysisRepositories:
    runs: ResearchRunRepository
    artifacts: ArtifactRepository
    reviews: HumanReviewRepository
    evaluations: EvaluationRepository

    @classmethod
    def for_session(cls, session: Session) -> AnalysisRepositories:
        return cls(
            runs=ResearchRunRepository(session),
            artifacts=ArtifactRepository(session),
            reviews=HumanReviewRepository(session),
            evaluations=EvaluationRepository(session),
        )


def _jsonable(value: Any) -> dict[str, object]:
    """Convert immutable dataclass graphs to JSON without coupling them to the ORM."""

    from dataclasses import asdict

    return json.loads(json.dumps(asdict(value), default=str))


def utc_now() -> datetime:
    return datetime.now(UTC)
