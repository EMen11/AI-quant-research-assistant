"""Transactional application service for the synchronous Block 8 MVP."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ai_quant.api.schemas import (
    AnalysisCreate,
    AnalysisResponse,
    ClaimReferenceAuditResponse,
    EvaluationResponse,
    EvidenceResponse,
    FindingResponse,
    ReviewCreate,
    ReviewResponse,
)
from ai_quant.persistence.orm import HumanReviewRow, ResearchRunRow
from ai_quant.persistence.repositories import (
    AnalysisRepositories,
    IdempotencyConflict,
    PersistenceConflict,
    canonical_sha256,
)
from ai_quant.trust import InMemoryTrustWorkflow


class ResourceNotFound(RuntimeError):
    pass


class BusinessConflict(RuntimeError):
    pass


class CorrectionUnrepresentable(BusinessConflict):
    """The requested correction cannot map atomically to the versioned claim set."""


class AnalysisService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        workflow: InMemoryTrustWorkflow | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._workflow = workflow or InMemoryTrustWorkflow()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._evaluation_report = _load_evaluation_report()

    def create_analysis(
        self, request: AnalysisCreate, idempotency_key: str
    ) -> tuple[AnalysisResponse, bool]:
        payload = request.model_dump(mode="json")
        request_hash = canonical_sha256(payload)
        with self._sessions() as session, session.begin():
            repositories = AnalysisRepositories.for_session(session)
            repositories.runs.lock_idempotency_key(idempotency_key)
            existing = repositories.runs.by_idempotency_key(idempotency_key)
            if existing is not None:
                if existing.request_sha256 != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key is already bound to a different request"
                    )
                return _analysis_response(existing.response_payload), False

            created_at = self._clock()
            _require_utc(created_at)
            run_id = f"run-local-{uuid.uuid4().hex}"
            result = self._workflow.run(request.scenario, run_id=run_id)
            allowed_metric_ids = frozenset(
                record.metric_id for record in result.metric_records
            )
            allowed_evidence_ids = frozenset(
                record.evidence_id for record in result.evidence_records
            )
            response = AnalysisResponse(
                analysis_id=run_id,
                state=result.state,
                scenario=request.scenario,
                data_origin="frozen_offline_fixture",
                draft_id=result.draft.draft_id,
                draft_version=1,
                summary=result.draft.summary,
                claims=tuple(claim.text_template for claim in result.draft.claims),
                claim_references=tuple(
                    _claim_reference_response(
                        claim_id=claim.claim_id,
                        declared_metric_ids=claim.metric_ids,
                        declared_evidence_ids=claim.evidence_ids,
                        accepted_metric_ids=tuple(
                            item for item in claim.metric_ids if item in allowed_metric_ids
                        ),
                        accepted_evidence_ids=tuple(
                            item for item in claim.evidence_ids if item in allowed_evidence_ids
                        ),
                    )
                    for claim in result.draft.claims
                ),
                automated_status=result.assessment.status,
                reliable=result.rendered_draft.reliable,
                final_text=result.rendered_draft.final_text,
                findings=tuple(
                    FindingResponse(**issue.model_dump())
                    for issue in result.validation_report.issues
                ),
                created_at=created_at,
            )
            repositories.runs.add(
                ResearchRunRow(
                    run_id=run_id,
                    idempotency_key=idempotency_key,
                    request_sha256=request_hash,
                    scenario=request.scenario,
                    state=result.state,
                    data_origin="frozen_offline_fixture",
                    response_payload=response.model_dump(mode="json"),
                    created_at=created_at,
                )
            )
            session.flush()
            repositories.artifacts.append_workflow(result, created_at=created_at)
            repositories.evaluations.append_if_absent(
                self._evaluation_report, created_at=created_at
            )
            return response, True

    def get_analysis(self, run_id: str) -> AnalysisResponse:
        with self._sessions() as session:
            repositories = AnalysisRepositories.for_session(session)
            row = repositories.runs.get(run_id)
            if row is None:
                raise ResourceNotFound("analysis not found")
            response = _analysis_response(row.response_payload)
            draft = repositories.artifacts.current_draft(run_id)
            if draft is None or draft.version == response.draft_version:
                return response
            assessment = repositories.artifacts.domain_assessment(draft.draft_id)
            if assessment is None:
                raise PersistenceConflict("current draft has no assessment")
            report = repositories.artifacts.validation_report(draft)
            rendered = repositories.artifacts.rendered_draft(draft)
            return response.model_copy(
                update={
                    "draft_id": draft.draft_id,
                    "draft_version": draft.version,
                    "summary": draft.summary,
                    "claims": tuple(
                        claim.text_template
                        for claim in repositories.artifacts.claims(draft.draft_id)
                    ),
                    "claim_references": tuple(
                        _claim_reference_response(
                            claim_id=audit.claim_id,
                            declared_metric_ids=audit.declared_metric_ids,
                            declared_evidence_ids=audit.declared_evidence_ids,
                            accepted_metric_ids=audit.accepted_metric_ids,
                            accepted_evidence_ids=audit.accepted_evidence_ids,
                        )
                        for audit in repositories.artifacts.claim_reference_audits(
                            draft.draft_id
                        )
                    ),
                    "automated_status": assessment.status,
                    "reliable": rendered.reliable,
                    "final_text": rendered.final_text,
                    "findings": tuple(
                        FindingResponse(
                            code=issue.code,
                            severity=issue.severity,
                            claim_id=issue.claim_id,
                            message=issue.message,
                        )
                        for issue in report.issues
                    ),
                }
            )

    def get_evidence(self, run_id: str) -> tuple[EvidenceResponse, ...]:
        with self._sessions() as session:
            repositories = AnalysisRepositories.for_session(session)
            if repositories.runs.get(run_id) is None:
                raise ResourceNotFound("analysis not found")
            return tuple(
                EvidenceResponse(
                    evidence_id=row.evidence_id,
                    document_id=row.document_id,
                    document_sha256=row.document_sha256,
                    status=row.status,
                    payload=row.payload,
                )
                for row in repositories.artifacts.evidence(run_id)
            )

    def create_review(self, run_id: str, request: ReviewCreate) -> ReviewResponse:
        try:
            with self._sessions() as session, session.begin():
                repositories = AnalysisRepositories.for_session(session)
                run = repositories.runs.get_for_update(run_id)
                if run is None:
                    raise ResourceNotFound("analysis not found")
                draft = repositories.artifacts.current_draft(run_id)
                if draft is None:
                    raise PersistenceConflict("analysis has no current draft")
                if request.draft_id != draft.draft_id or request.draft_version != draft.version:
                    raise BusinessConflict("review does not target the current draft version")
                assessment = repositories.artifacts.domain_assessment(draft.draft_id)
                if assessment is None:
                    raise PersistenceConflict("current draft has no assessment")
                if (
                    request.disposition == "approved"
                    and assessment.status != "eligible_for_review"
                ):
                    raise BusinessConflict("approval requires an eligible current draft")
                if request.disposition == "corrected":
                    if request.corrected_summary is None or request.corrected_claims is None:
                        raise BusinessConflict(
                            "a corrected review requires corrected_summary and corrected_claims"
                        )
                    if (
                        request.corrected_references is not None
                        and len(request.corrected_references)
                        != len(request.corrected_claims)
                    ):
                        raise CorrectionUnrepresentable(
                            "corrected_references must contain exactly one entry per claim"
                        )
                elif any(
                    value is not None
                    for value in (
                        request.corrected_summary,
                        request.corrected_claims,
                        request.corrected_references,
                    )
                ):
                    raise BusinessConflict("correction content requires disposition corrected")

                reviewed_at = self._clock()
                _require_utc(reviewed_at)
                row = HumanReviewRow(
                    review_id=f"review-{uuid.uuid4().hex}",
                    run_id=run_id,
                    draft_id=draft.draft_id,
                    draft_version=draft.version,
                    reviewer_entered=request.reviewer,
                    disposition=request.disposition,
                    comment=request.comment,
                    reviewed_at=reviewed_at,
                )
                repositories.reviews.append(row)
                corrected = None
                if request.disposition == "corrected":
                    assert request.corrected_summary is not None
                    assert request.corrected_claims is not None
                    corrected = repositories.artifacts.append_correction(
                        draft,
                        summary=request.corrected_summary,
                        claim_templates=tuple(request.corrected_claims),
                        declared_metric_ids=(
                            tuple(
                                tuple(item.declared_metric_ids)
                                for item in request.corrected_references
                            )
                            if request.corrected_references is not None
                            else None
                        ),
                        declared_evidence_ids=(
                            tuple(
                                tuple(item.declared_evidence_ids)
                                for item in request.corrected_references
                            )
                            if request.corrected_references is not None
                            else None
                        ),
                        created_at=reviewed_at,
                    )
                return _review_response(
                    row,
                    resulting_draft=(corrected.draft if corrected else None),
                )
        except IntegrityError:
            raise BusinessConflict("concurrent persistent state conflict") from None

    def latest_evaluation(self) -> EvaluationResponse:
        with self._sessions() as session:
            row = AnalysisRepositories.for_session(session).evaluations.latest()
            if row is None:
                raise ResourceNotFound("evaluation not found")
            return EvaluationResponse(
                evaluation_id=row.evaluation_id,
                schema_version=row.schema_version,
                dataset_sha256=row.dataset_sha256,
                case_count=row.case_count,
                report=row.report_payload,
                created_at=row.created_at,
            )

    def health(self) -> None:
        with self._sessions() as session:
            session.execute(text("SELECT 1"))


def _review_response(
    row: HumanReviewRow, *, resulting_draft=None  # type: ignore[no-untyped-def]
) -> ReviewResponse:
    return ReviewResponse(
        review_id=row.review_id,
        analysis_id=row.run_id,
        draft_id=row.draft_id,
        draft_version=row.draft_version,
        reviewer_entered=row.reviewer_entered,
        reviewer_identity="entered_unverified_unauthenticated",
        disposition=row.disposition,
        comment=row.comment,
        reviewed_at=row.reviewed_at,
        resulting_draft_id=(resulting_draft.draft_id if resulting_draft else None),
        resulting_draft_version=(resulting_draft.version if resulting_draft else None),
    )


def _analysis_response(payload: dict[str, object]) -> AnalysisResponse:
    return AnalysisResponse.model_validate_json(json.dumps(payload))


def _claim_reference_response(
    *,
    claim_id: str,
    declared_metric_ids: tuple[str, ...],
    declared_evidence_ids: tuple[str, ...],
    accepted_metric_ids: tuple[str, ...],
    accepted_evidence_ids: tuple[str, ...],
) -> ClaimReferenceAuditResponse:
    accepted = (
        declared_metric_ids == accepted_metric_ids
        and declared_evidence_ids == accepted_evidence_ids
    )
    return ClaimReferenceAuditResponse(
        claim_id=claim_id,
        declared_metric_ids=declared_metric_ids,
        declared_evidence_ids=declared_evidence_ids,
        accepted_metric_ids=accepted_metric_ids,
        accepted_evidence_ids=accepted_evidence_ids,
        reference_status="accepted" if accepted else "declared_untrusted",
    )


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("application timestamps must be timezone-aware UTC")


def _load_evaluation_report() -> dict[str, object]:
    relative = Path("reports/evaluation/workflow_eval.v1.json")
    candidates = (Path.cwd() / relative, Path(__file__).resolve().parents[3] / relative)
    path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("committed evaluation report must be a JSON object")
    return payload
