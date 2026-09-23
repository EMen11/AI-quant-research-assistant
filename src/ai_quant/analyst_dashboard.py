"""Deterministic application layer for the offline analyst dashboard.

Streamlit consumes the view models in this module but owns no validation,
approval, correction, export, or artifact-loading rule.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, MutableMapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import TypeAdapter

from ai_quant.config import AppMode, Settings
from ai_quant.evaluation.runner import load_dataset
from ai_quant.market_data import FrozenSnapshotProvider, SnapshotRun
from ai_quant.quant import QuantAnalysis, analyze_portfolio, demo_portfolio, demo_risk_free_rate
from ai_quant.retrieval.evaluation import RetrievalEvaluationArtifact
from ai_quant.sustainability import SustainabilityCorpus, load_corpus
from ai_quant.trust import (
    AutomatedAssessment,
    ClaimDraft,
    GeneratedDraft,
    HumanReview,
    RenderedDraft,
    ValidationReport,
    WorkflowResult,
    assess_draft,
    build_demo_trust_scenarios,
    create_human_review,
    render_validated_draft,
    validate_draft,
)
from ai_quant.trust.models import HumanDisposition, Identifier, Sha256

ScenarioKey = Literal["admissible", "blocked"]
ContentOrigin = Literal[
    "historical-live-provider-normalized-fixture",
    "synthetic-offline-fixture",
    "human-edited-session-revision",
]
SourceGenerationOrigin = Literal[
    "historical-live-provider-normalized-fixture",
    "synthetic-offline-fixture",
]
SCENARIO_LABELS: dict[ScenarioKey, str] = {
    "admissible": "Admissible · official evidence",
    "blocked": "Blocked · deliberately invalid synthetic draft",
}
DEMO_REVIEWER_ID = "demo-reviewer-unauthenticated"
SESSION_STATE_KEY = "block7-review-sessions"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_LIVE_PROVENANCE_LABEL = (
    "Historical live-provider call · original semantic validation failed · "
    "deterministically normalized and human-reviewed for offline demo use"
)


@dataclass(frozen=True, slots=True)
class MethodologyLink:
    """One public link backed by an existing repository path when applicable."""

    label: str
    url: str
    local_path: str | None


_COMMIT_URL = (
    "https://github.com/EMen11/AI-quant-research-assistant/blob/"
    "4eee6d637ac7d0bf0df2ee77d923f5a0337619cc"
)
METHODOLOGY_LINKS: tuple[MethodologyLink, ...] = (
    MethodologyLink(
        label="GitHub repository",
        url="https://github.com/EMen11/AI-quant-research-assistant",
        local_path=None,
    ),
    MethodologyLink(
        label="Quant methodology",
        url=f"{_COMMIT_URL}/docs/methodology/quant_methodology.md",
        local_path="docs/methodology/quant_methodology.md",
    ),
    MethodologyLink(
        label="Climate corpus methodology",
        url=f"{_COMMIT_URL}/docs/methodology/sustainability_corpus.md",
        local_path="docs/methodology/sustainability_corpus.md",
    ),
    MethodologyLink(
        label="Retrieval and LLM methodology",
        url=f"{_COMMIT_URL}/docs/methodology/retrieval_and_llm.md",
        local_path="docs/methodology/retrieval_and_llm.md",
    ),
    MethodologyLink(
        label="Block 6 evaluation artifact",
        url=f"{_COMMIT_URL}/reports/evaluation/workflow_eval.v1.json",
        local_path="reports/evaluation/workflow_eval.v1.json",
    ),
)


@dataclass(frozen=True, slots=True)
class RetrievalQuality:
    """Retrieval values loaded only from the committed evaluation artifact."""

    source_path: str
    schema_version: str
    gold_set_path: str
    gold_set_sha256: str
    question_count: int
    overall_rows: tuple[dict[str, str | int], ...]
    ranking_rows: tuple[dict[str, str | int], ...]
    observed_failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowQuality:
    """Workflow-evaluation values loaded only from the committed report and dataset."""

    source_path: str
    schema_version: str
    dataset_version: str
    dataset_sha256: str
    case_count: int
    split_counts: tuple[tuple[str, int], ...]
    confusion_matrix: tuple[tuple[str, int], ...]
    false_eligible_count: int
    false_eligible_denominator: int
    rates_by_type: tuple[tuple[str, int, int, float], ...]
    scope_statement: str


@dataclass(frozen=True, slots=True)
class QualityArtifacts:
    retrieval: RetrievalQuality
    workflow: WorkflowQuality


@dataclass(frozen=True, slots=True)
class AnalystDashboard:
    """All immutable data required to render the six analyst views."""

    analysis: QuantAnalysis
    scenarios: dict[ScenarioKey, WorkflowResult]
    climate_corpus: SustainabilityCorpus
    quality: QualityArtifacts


@dataclass(frozen=True, slots=True)
class MetricView:
    """Presentation-safe projection of an authoritative MetricRecord."""

    metric_id: str
    name: str
    value: float
    unit: str
    horizon_or_frequency: str
    formula_version: str
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class EvidenceView:
    """Traceable climate or workflow evidence row with no inferred values."""

    evidence_id: str
    issuer: str
    document: str
    period: str
    pdf_page: int | None
    printed_page: int | None
    excerpt: str | None
    source: str
    record_type: str
    coverage_status: str
    limitation: str
    scope_2_method: str


@dataclass(frozen=True, slots=True)
class DraftRevision:
    """One deterministically validated draft version in the current UI session."""

    version: int
    draft: GeneratedDraft
    validation_report: ValidationReport
    assessment: AutomatedAssessment
    rendered_draft: RenderedDraft
    content_origin: ContentOrigin
    source_generation_origin: SourceGenerationOrigin


@dataclass(frozen=True, slots=True)
class SessionReview:
    """A HumanReview bound to the exact draft version reviewed in this session."""

    run_id: str
    draft_id: str
    revision_number: int
    approved_draft_sha256: str | None
    approved_final_text_sha256: str | None
    review: HumanReview


@dataclass(frozen=True, slots=True)
class ScenarioSession:
    """In-memory review history; Streamlit stores this object in session_state only."""

    revisions: tuple[DraftRevision, ...]
    reviews: tuple[SessionReview, ...] = ()

    @property
    def current(self) -> DraftRevision:
        return self.revisions[-1]

    @property
    def current_review(self) -> SessionReview | None:
        return next(
            (
                item
                for item in reversed(self.reviews)
                if item.draft_id == self.current.draft.draft_id
                and item.revision_number == self.current.version
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class ExportDecision:
    """Result of applying the current-version export policy."""

    allowed: bool
    reason: str
    filename: str | None = None
    payload: str | None = None


class ReviewRepository(Protocol):
    """Repository boundary; Block 7 provides only the session implementation."""

    def get(self, scenario: ScenarioKey) -> ScenarioSession:
        """Return the current session state for a scenario."""

    def put(self, scenario: ScenarioKey, value: ScenarioSession) -> None:
        """Replace the current session state for a scenario."""


class SessionReviewRepository:
    """Mapping-backed repository suitable for ``st.session_state`` only."""

    def __init__(
        self,
        state: MutableMapping[str, object],
        scenarios: dict[ScenarioKey, WorkflowResult],
    ) -> None:
        self._state = state
        if SESSION_STATE_KEY not in self._state:
            self._state[SESSION_STATE_KEY] = {
                key: session_from_workflow(result) for key, result in scenarios.items()
            }

    def get(self, scenario: ScenarioKey) -> ScenarioSession:
        sessions = self._sessions()
        return sessions[scenario]

    def put(self, scenario: ScenarioKey, value: ScenarioSession) -> None:
        sessions = dict(self._sessions())
        sessions[scenario] = value
        self._state[SESSION_STATE_KEY] = sessions

    def _sessions(self) -> dict[ScenarioKey, ScenarioSession]:
        value = self._state[SESSION_STATE_KEY]
        if not isinstance(value, dict):
            raise TypeError("Dashboard session review state has an invalid shape.")
        return value  # type: ignore[return-value]


def build_analyst_dashboard(settings: Settings) -> AnalystDashboard:
    """Load every dashboard value from deterministic, versioned offline inputs."""

    if settings.app_mode is not AppMode.DEMO:
        raise ValueError("The analyst dashboard can only be built in APP_MODE=demo.")
    analysis = analyze_portfolio(
        demo_portfolio(),
        SnapshotRun(FrozenSnapshotProvider.demo()),
        demo_risk_free_rate(),
    )
    valid, blocked = build_demo_trust_scenarios(analysis)
    return AnalystDashboard(
        analysis=analysis,
        scenarios={"admissible": valid, "blocked": blocked},
        climate_corpus=load_corpus(date(2026, 3, 12)),
        quality=load_quality_artifacts(),
    )


def session_from_workflow(result: WorkflowResult) -> ScenarioSession:
    """Start a session history without creating a HumanReview."""

    call = result.draft.generation.model_call
    source_origin: SourceGenerationOrigin = (
        "historical-live-provider-normalized-fixture"
        if call is not None and call.response_origin == "live_provider"
        else "synthetic-offline-fixture"
    )
    return ScenarioSession(
        revisions=(
            DraftRevision(
                version=1,
                draft=result.draft,
                validation_report=result.validation_report,
                assessment=result.assessment,
                rendered_draft=result.rendered_draft,
                content_origin=source_origin,
                source_generation_origin=source_origin,
            ),
        )
    )


def approval_allowed(revision: DraftRevision) -> bool:
    """Return whether an explicit human approval may be recorded for this version."""

    try:
        draft, report, assessment, rendered = _revalidate_revision(revision)
        return (
            assessment.status == "eligible_for_review"
            and rendered.reliable
            and rendered.final_text is not None
            and not report.has_blocking_issues
            and draft.run_id == report.run_id == assessment.run_id == rendered.run_id
            and draft.draft_id == report.draft_id == rendered.draft_id
        )
    except Exception:
        return False


def add_human_review(
    session: ScenarioSession,
    *,
    disposition: HumanDisposition,
    comment: str,
    clock: Callable[[], datetime] | None = None,
) -> ScenarioSession:
    """Create one explicit session review for the current version."""

    if disposition == "approved" and not approval_allowed(session.current):
        raise ValueError("Approval is forbidden unless the current version is reliable and eligible.")
    selected_time = clock() if clock is not None else datetime.now(UTC)
    current = session.current
    review = create_human_review(
        run_id=current.draft.run_id,
        reviewer_id=DEMO_REVIEWER_ID,
        comment=comment.strip(),
        reviewed_at=selected_time,
        disposition=disposition,
    )
    approved_hash = (
        _final_text_sha256(current.rendered_draft.final_text)
        if disposition == "approved" and current.rendered_draft.final_text is not None
        else None
    )
    approved_draft_hash = (
        _draft_sha256(current.draft) if disposition == "approved" else None
    )
    return replace(
        session,
        reviews=(
            *session.reviews,
            SessionReview(
                run_id=current.draft.run_id,
                draft_id=current.draft.draft_id,
                revision_number=current.version,
                approved_draft_sha256=approved_draft_hash,
                approved_final_text_sha256=approved_hash,
                review=review,
            ),
        ),
    )


def create_corrected_revision(
    session: ScenarioSession,
    result: WorkflowResult,
    *,
    summary: str,
    claim_templates: Sequence[str],
    comment: str,
    clock: Callable[[], datetime] | None = None,
) -> ScenarioSession:
    """Review the old version as corrected, then validate a new current version."""

    current = session.current
    cleaned_summary = summary.strip()
    cleaned_templates = tuple(value.strip() for value in claim_templates)
    if not cleaned_summary or any(not value for value in cleaned_templates):
        raise ValueError("A corrected summary and every corrected claim must be non-empty.")
    if len(cleaned_templates) != len(current.draft.claims):
        raise ValueError("A correction must preserve the number of atomic claims.")
    if cleaned_summary == current.draft.summary and cleaned_templates == tuple(
        claim.text_template for claim in current.draft.claims
    ):
        raise ValueError("A correction must change the summary or at least one atomic claim.")

    reviewed_session = add_human_review(
        session,
        disposition="corrected",
        comment=comment,
        clock=clock,
    )
    version = current.version + 1
    claims = tuple(
        ClaimDraft(
            claim_id=f"claim-{current.draft.run_id}-v{version:02d}-{index:02d}",
            run_id=current.draft.run_id,
            text_template=template,
            claim_type=old.claim_type,
            metric_ids=old.metric_ids,
            evidence_ids=old.evidence_ids,
            uncertainty=old.uncertainty,
        )
        for index, (old, template) in enumerate(
            zip(current.draft.claims, cleaned_templates, strict=True), start=1
        )
    )
    draft = GeneratedDraft(
        draft_id=f"draft-{current.draft.run_id}-v{version:02d}",
        run_id=current.draft.run_id,
        summary=cleaned_summary,
        claims=claims,
        limitations=current.draft.limitations,
        generation=current.draft.generation,
    )
    report = validate_draft(
        run_id=result.run_id,
        draft=draft,
        metrics=result.metric_records,
        evidence=result.evidence_records,
    )
    assessment = assess_draft(report=report)
    rendered = render_validated_draft(
        draft=draft,
        report=report,
        metrics=result.metric_records,
        evidence=result.evidence_records,
    )
    revision = DraftRevision(
        version=version,
        draft=draft,
        validation_report=report,
        assessment=assessment,
        rendered_draft=rendered,
        content_origin="human-edited-session-revision",
        source_generation_origin=current.source_generation_origin,
    )
    return replace(reviewed_session, revisions=(*session.revisions, revision))


def decide_export(session: ScenarioSession) -> ExportDecision:
    """Fail closed unless one defensively revalidated review owns current content."""

    try:
        revision = session.current
        draft, report, assessment, rendered = _revalidate_revision(revision)
        if assessment.status != "eligible_for_review":
            return _blocked_export(f"automated status is {assessment.status}")
        if not rendered.reliable or rendered.final_text is None:
            return _blocked_export("no reliable deterministic rendering exists")
        if report.has_blocking_issues:
            return _blocked_export("blocking validation findings are present")
        review_binding = session.current_review
        if review_binding is None:
            return _blocked_export("the current draft version has no HumanReview")
        binding, human_review = _revalidate_session_review(review_binding)
        if human_review.disposition != "approved":
            return _blocked_export("the current HumanReview disposition is not approved")
        expected_draft_hash = _draft_sha256(draft)
        expected_final_text_hash = _final_text_sha256(rendered.final_text)
        integrity_checks = (
            binding.run_id == human_review.run_id == draft.run_id == report.run_id,
            draft.run_id == assessment.run_id == rendered.run_id,
            binding.draft_id == draft.draft_id == report.draft_id == rendered.draft_id,
            binding.revision_number == revision.version,
            binding.approved_draft_sha256 == expected_draft_hash,
            binding.approved_final_text_sha256 == expected_final_text_hash,
            bool(human_review.reviewer_id.strip()),
            human_review.reviewed_at.tzinfo is not None,
            human_review.reviewed_at.utcoffset() == timedelta(0),
        )
        if not all(integrity_checks):
            return _blocked_export("review or revision integrity checks failed")
        payload = json.dumps(
            {
                "schema_version": "analyst-approved-export.v3",
                "run_id": draft.run_id,
                "draft_id": draft.draft_id,
                "revision_number": revision.version,
                "approved_draft_sha256": expected_draft_hash,
                "approved_final_text_sha256": expected_final_text_hash,
                "human_review_status": "approved",
                "review": human_review.model_dump(mode="json"),
                "final_text": rendered.final_text,
            },
            indent=2,
            sort_keys=True,
        )
        return ExportDecision(
            True,
            "Approved export available for the current reviewed version.",
            filename=f"{draft.draft_id}-approved.json",
            payload=payload + "\n",
        )
    except Exception:
        return _blocked_export("review or revision integrity checks failed")


def _blocked_export(reason: str) -> ExportDecision:
    return ExportDecision(False, f"Export blocked: {reason}.")


def _revalidate_revision(
    revision: DraftRevision,
) -> tuple[GeneratedDraft, ValidationReport, AutomatedAssessment, RenderedDraft]:
    if type(revision.version) is not int or revision.version < 1:
        raise ValueError("Revision number must be a positive integer.")
    draft = GeneratedDraft.model_validate(revision.draft.model_dump(mode="python"))
    report = ValidationReport.model_validate(
        revision.validation_report.model_dump(mode="python")
    )
    assessment = AutomatedAssessment.model_validate(
        revision.assessment.model_dump(mode="python")
    )
    rendered = RenderedDraft.model_validate(
        revision.rendered_draft.model_dump(mode="python")
    )
    return draft, report, assessment, rendered


def _revalidate_session_review(
    binding: SessionReview,
) -> tuple[SessionReview, HumanReview]:
    TypeAdapter(Identifier).validate_python(binding.run_id)
    TypeAdapter(Identifier).validate_python(binding.draft_id)
    if type(binding.revision_number) is not int or binding.revision_number < 1:
        raise ValueError("Review revision number must be a positive integer.")
    if binding.approved_draft_sha256 is not None:
        TypeAdapter(Sha256).validate_python(binding.approved_draft_sha256)
    if binding.approved_final_text_sha256 is not None:
        TypeAdapter(Sha256).validate_python(binding.approved_final_text_sha256)
    human_review = HumanReview.model_validate(binding.review.model_dump(mode="python"))
    if human_review.disposition not in {"approved", "corrected", "rejected", "escalated"}:
        raise ValueError("Unknown human-review disposition.")
    if not human_review.reviewer_id.strip():
        raise ValueError("Reviewer ID must not be empty after normalization.")
    if (
        human_review.reviewed_at.tzinfo is None
        or human_review.reviewed_at.utcoffset() != timedelta(0)
    ):
        raise ValueError("Review timestamp must be timezone-aware UTC.")
    return binding, human_review


def _final_text_sha256(final_text: str) -> str:
    return hashlib.sha256(final_text.encode("utf-8")).hexdigest()


def _draft_sha256(draft: GeneratedDraft) -> str:
    canonical_json = json.dumps(
        draft.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def validation_issue_path(claim_id: str | None) -> str:
    """Expose the deterministic validation location without altering the report."""

    return f"claims/{claim_id}" if claim_id else "draft"


def metric_views(result: WorkflowResult) -> tuple[MetricView, ...]:
    """Project only Python-created MetricRecord fields for the Quant view."""

    return tuple(
        MetricView(
            metric_id=record.metric_id,
            name=record.metric_name,
            value=record.value,
            unit=record.unit,
            horizon_or_frequency=record.horizon_or_frequency,
            formula_version=record.formula_version,
            snapshot_id=record.snapshot_id,
        )
        for record in result.metric_records
    )


def workflow_evidence_views(
    result: WorkflowResult,
    corpus: SustainabilityCorpus,
) -> tuple[EvidenceView, ...]:
    """Project the selected run evidence without changing its provenance label."""

    observations = {item.observation_id: item for item in corpus.observations}

    def project(record: object) -> EvidenceView:
        source_record_id = record.source_record_id  # type: ignore[attr-defined]
        observation = observations.get(source_record_id)
        return EvidenceView(
            evidence_id=record.evidence_id,  # type: ignore[attr-defined]
            issuer=record.issuer_id or "not available in this evidence record",  # type: ignore[attr-defined]
            document=record.document_id,  # type: ignore[attr-defined]
            period=record.period,  # type: ignore[attr-defined]
            pdf_page=record.page,  # type: ignore[attr-defined]
            printed_page=record.printed_page,  # type: ignore[attr-defined]
            excerpt=record.excerpt,  # type: ignore[attr-defined]
            source=(
                f"{record.status} · {record.passage_id or 'no official passage'} · "  # type: ignore[attr-defined]
                f"sha256:{record.document_sha256}"  # type: ignore[attr-defined]
            ),
            record_type=record.source_record_type or "synthetic_evidence_record",  # type: ignore[attr-defined]
            coverage_status=(
                observation.coverage_status
                if observation is not None
                else "not available in this evidence record"
            ),
            limitation=(
                "Synthetic demo evidence; not an issuer disclosure."
                if record.status == "synthetic_demo_evidence"  # type: ignore[attr-defined]
                else "Issuer-reported official corpus passage; not an independently verified fact."
            ),
            scope_2_method=(
                observation.scope_2_method
                if observation is not None
                else "not available in this evidence record"
            ),
        )

    return tuple(
        project(record)
        for record in result.evidence_records
    )


def climate_evidence_groups(
    corpus: SustainabilityCorpus,
) -> dict[str, tuple[EvidenceView, ...]]:
    """Separate observed, target, zero, missing and Scope 2 method categories."""

    documents = {document.document_id: document for document in corpus.documents}

    def observation_view(record: object) -> EvidenceView:
        return EvidenceView(
            evidence_id=record.observation_id,  # type: ignore[attr-defined]
            issuer=record.issuer_id,  # type: ignore[attr-defined]
            document=record.document_title,  # type: ignore[attr-defined]
            period=(
                f"{record.period_start.isoformat()} / "  # type: ignore[attr-defined]
                f"{record.period_end.isoformat()}"  # type: ignore[attr-defined]
            ),
            pdf_page=record.pdf_page,  # type: ignore[attr-defined]
            printed_page=record.printed_page,  # type: ignore[attr-defined]
            excerpt=record.short_exact_excerpt,  # type: ignore[attr-defined]
            source=(
                f"{record.provenance} · sha256:{record.document_sha256}"  # type: ignore[attr-defined]
            ),
            record_type="sustainability_observation",
            coverage_status=record.coverage_status,  # type: ignore[attr-defined]
            limitation=(
                f"{record.methodology_or_standard} Assurance: "  # type: ignore[attr-defined]
                f"{record.assurance_status}. {record.restatement}"  # type: ignore[attr-defined]
            ),
            scope_2_method=record.scope_2_method,  # type: ignore[attr-defined]
        )

    non_zero = tuple(
        item for item in corpus.observations if item.coverage_status == "reported_value"
    )
    location = tuple(
        observation_view(item)
        for item in non_zero
        if item.scope_2_method == "location_based"
    )
    market = tuple(
        observation_view(item)
        for item in non_zero
        if item.scope_2_method == "market_based"
    )
    other = tuple(
        observation_view(item)
        for item in non_zero
        if item.scope_2_method == "not_applicable"
    )
    reported_zero = tuple(
        observation_view(item)
        for item in corpus.observations
        if item.coverage_status == "reported_zero"
    )
    targets = tuple(
        EvidenceView(
            evidence_id=item.target_id,
            issuer=item.issuer_id,
            document=documents[item.document_id].title,
            period=f"base year {item.base_year} / target year {item.target_year}",
            pdf_page=item.pdf_page,
            printed_page=item.printed_page,
            excerpt=item.short_exact_excerpt,
            source=f"{item.provenance} · sha256:{item.document_sha256}",
            record_type="climate_target",
            coverage_status="not available in this evidence record",
            limitation=(
                f"Target, not an observed result. Validation: {item.validation_status}; "
                f"assurance: {item.assurance_status}."
            ),
            scope_2_method="not available in this evidence record",
        )
        for item in corpus.targets
    )
    missing = tuple(
        EvidenceView(
            evidence_id=item.finding_id,
            issuer=item.issuer_id,
            document=", ".join(item.searched_document_ids),
            period=f"{item.period_start.isoformat()} / {item.period_end.isoformat()}",
            pdf_page=item.pdf_page,
            printed_page=item.printed_page,
            excerpt=item.short_exact_excerpt,
            source="bounded_corpus_coverage_search",
            record_type="coverage_finding",
            coverage_status=item.status,
            limitation=item.notes,
            scope_2_method="not available in this evidence record",
        )
        for item in corpus.coverage_report.findings
    )
    return {
        "observed_scope2_location": location,
        "observed_scope2_market": market,
        "observed_other_method_not_applicable": other,
        "explicitly_reported_zero": reported_zero,
        "climate_targets": targets,
        "missing_or_ambiguous": missing,
    }


def load_quality_artifacts(root: Path = PROJECT_ROOT) -> QualityArtifacts:
    """Strictly load the two committed quality artifacts used by the UI."""

    retrieval_path = root / "reports/evaluation/retrieval_baselines.v1.json"
    retrieval_artifact = RetrievalEvaluationArtifact.model_validate_json(
        retrieval_path.read_text(encoding="utf-8")
    )
    overall_rows = tuple(_retrieval_row(item) for item in retrieval_artifact.aggregates)
    ranking_rows = tuple(
        _retrieval_row(item) for item in retrieval_artifact.ranking_aggregates
    )
    retrieval = RetrievalQuality(
        source_path=retrieval_path.relative_to(root).as_posix(),
        schema_version=retrieval_artifact.schema_version,
        gold_set_path=retrieval_artifact.gold_set_path,
        gold_set_sha256=retrieval_artifact.gold_set_sha256,
        question_count=retrieval_artifact.case_type_counts.total,
        overall_rows=overall_rows,
        ranking_rows=ranking_rows,
        observed_failures=retrieval_artifact.observed_failures,
    )

    workflow_path = root / "reports/evaluation/workflow_eval.v1.json"
    workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    dataset_path = root / "tests/evaluation/workflow_eval.v1.jsonl"
    cases = load_dataset(dataset_path)
    _require_workflow_report_shape(workflow_payload, case_count=len(cases))
    false_eligible = workflow_payload["false_eligible_for_review"]
    workflow = WorkflowQuality(
        source_path=workflow_path.relative_to(root).as_posix(),
        schema_version=workflow_payload["schema_version"],
        dataset_version=workflow_payload["versions"]["dataset"],
        dataset_sha256=workflow_payload["versions"]["dataset_sha256"],
        case_count=workflow_payload["case_count"],
        split_counts=tuple(sorted(workflow_payload["split_counts"].items())),
        confusion_matrix=tuple(sorted(workflow_payload["confusion_matrix"].items())),
        false_eligible_count=false_eligible["count"],
        false_eligible_denominator=false_eligible["critical_case_count"],
        rates_by_type=tuple(
            (
                name,
                values["detected"],
                values["total"],
                values["rate"],
            )
            for name, values in sorted(
                workflow_payload["detection_rate_by_error_type"].items()
            )
        ),
        scope_statement=workflow_payload["scope_statement"],
    )
    return QualityArtifacts(retrieval=retrieval, workflow=workflow)


def methodology_links_are_backed_by_files(root: Path = PROJECT_ROOT) -> bool:
    """Check that every repository-file methodology link has a local target."""

    return all(
        link.local_path is None or (root / link.local_path).is_file()
        for link in METHODOLOGY_LINKS
    )


def _retrieval_row(aggregate: object) -> dict[str, str | int]:
    return {
        "Baseline": aggregate.baseline,  # type: ignore[attr-defined]
        "Questions": aggregate.question_count,  # type: ignore[attr-defined]
        "Recall@1": f"{aggregate.recall_at_1:.0%}",  # type: ignore[attr-defined]
        "Recall@3": f"{aggregate.recall_at_3:.0%}",  # type: ignore[attr-defined]
    }


def _require_workflow_report_shape(payload: object, *, case_count: int) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Workflow quality artifact must be a JSON object.")
    required = {
        "case_count",
        "confusion_matrix",
        "detection_rate_by_error_type",
        "false_eligible_for_review",
        "schema_version",
        "scope_statement",
        "split_counts",
        "versions",
    }
    if set(payload) < required or payload["case_count"] != case_count:
        raise ValueError("Workflow quality artifact does not match its versioned dataset.")
    if payload["schema_version"] != "workflow-evaluation-report.v2":
        raise ValueError("Unsupported workflow quality artifact schema.")
