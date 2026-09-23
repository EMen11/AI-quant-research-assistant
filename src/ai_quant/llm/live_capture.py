"""Explicit one-call capture path for a future authorized Anthropic run."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from ai_quant.config import AppMode, Settings
from ai_quant.content_rules import (
    CANONICAL_SUMMARY_METRICS_AND_EVIDENCE,
    CANONICAL_SUMMARY_VERSION,
    CanonicalSummaryVersion,
    normalize_proposal_summary,
)
from ai_quant.llm.anthropic import AnthropicLLMClient
from ai_quant.llm.base import (
    ContentRuleCode,
    LLMClientError,
    PublicLLMFailure,
    SafeDiagnostic,
    SynthesisLimits,
    SynthesisRequest,
    proposal_content_rule_diagnostics,
    validated_synthesis_result,
)
from ai_quant.model_calls import ModelCallMetadata
from ai_quant.trust.models import (
    DraftProposal,
    EvidenceRecord,
    GenerationMetadata,
    GenerationParameter,
    Identifier,
    MetricRecord,
    NonEmptyText,
    RenderedDraft,
    Sha256,
    StrictModel,
    ValidationReport,
)
from ai_quant.trust.records import materialize_generated_draft
from ai_quant.trust.validation import render_validated_draft, validate_draft
from ai_quant.trust.workflow import build_synthesis_request


class ValidatedRunInput(StrictModel):
    """Versioned, already-validated local inputs authorized for one synthesis."""

    schema_version: Literal["validated-run-input.v1"] = "validated-run-input.v1"
    validation_status: Literal["validated"]
    run_id: Identifier
    prompt_version: Literal["trust-synthesis-v3"]
    context: str = Field(min_length=1, max_length=50_000)
    metrics: Annotated[tuple[MetricRecord, ...], Field(min_length=1)]
    evidence: Annotated[tuple[EvidenceRecord, ...], Field(min_length=1)]
    limits: SynthesisLimits = SynthesisLimits()

    @model_validator(mode="after")
    def inputs_are_current_run_official_records(self) -> ValidatedRunInput:
        if any(record.run_id != self.run_id for record in self.metrics):
            raise ValueError("Every metric must belong to the validated run.")
        if any(record.run_id != self.run_id for record in self.evidence):
            raise ValueError("Every evidence record must belong to the validated run.")
        if any(record.status != "official_corpus_passage" for record in self.evidence):
            raise ValueError("Live capture accepts only official corpus evidence.")
        metric_ids = tuple(record.metric_id for record in self.metrics)
        evidence_ids = tuple(record.evidence_id for record in self.evidence)
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("Validated run metric IDs must be unique.")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Validated run evidence IDs must be unique.")
        return self


class LiveCaptureRequestSummary(StrictModel):
    """Prompt-free dry-run summary."""

    run_id: Identifier
    prompt_version: Identifier
    model_id: NonEmptyText
    metric_count: int = Field(ge=1)
    evidence_count: int = Field(ge=1)
    allowlisted_metric_id_count: int = Field(ge=1)
    allowlisted_evidence_id_count: int = Field(ge=1)
    estimated_input_tokens: None = None
    max_output_tokens: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)


class LiveCapturePlan(StrictModel):
    """Safe dry-run result; contains no prompt, key or provider response."""

    schema_version: Literal["live-capture-plan.v1"] = "live-capture-plan.v1"
    status: Literal["dry_run_validated"] = "dry_run_validated"
    execution_mode: Literal["dry_run"] = "dry_run"
    network_call_count: Literal[0] = 0
    live_capture_created: Literal[False] = False
    eligible_as_demo_fixture: Literal[False] = False
    output_path: NonEmptyText
    overwrite: bool
    request: LiveCaptureRequestSummary


class LiveCaptureOutput(StrictModel):
    """Clean capture awaiting human review and ineligible as a demo fixture."""

    schema_version: Literal["live-capture.v1"] = "live-capture.v1"
    status: Literal["pending_human_review"] = "pending_human_review"
    capture_kind: Literal["unvalidated_live_capture"] = "unvalidated_live_capture"
    eligible_as_demo_fixture: Literal[False] = False
    run_id: Identifier
    proposal: DraftProposal
    model_call: ModelCallMetadata


class RejectedLiveCapture(StrictModel):
    """Pydantic-valid proposal quarantined after deterministic semantic rejection."""

    schema_version: Literal["rejected-live-capture.v1"] = "rejected-live-capture.v1"
    artifact_type: Literal["rejected_live_capture"] = "rejected_live_capture"
    status: Literal["semantic_validation_failed"] = "semantic_validation_failed"
    demo_eligible: Literal[False] = False
    promotion_policy: Literal["automatic_demo_fixture_promotion_forbidden"] = (
        "automatic_demo_fixture_promotion_forbidden"
    )
    error_code: Literal["structured_output_invalid"] = "structured_output_invalid"
    reason_code: Literal["semantic_content_rule_failed"] = (
        "semantic_content_rule_failed"
    )
    run_id: Identifier
    provider: Identifier
    model_id: NonEmptyText
    prompt_version: Identifier
    proposal: DraftProposal
    rule_codes: Annotated[tuple[ContentRuleCode, ...], Field(min_length=1)]
    field_paths: Annotated[tuple[SafeDiagnostic, ...], Field(min_length=1)]
    model_call: ModelCallMetadata

    @model_validator(mode="after")
    def diagnostics_and_metadata_are_consistent(self) -> RejectedLiveCapture:
        if self.rule_codes != tuple(sorted(set(self.rule_codes))):
            raise ValueError("Rejected capture rule codes must be sorted and unique.")
        if self.field_paths != tuple(sorted(set(self.field_paths))):
            raise ValueError("Rejected capture field paths must be sorted and unique.")
        if self.model_call.status != "schema_error":
            raise ValueError("Rejected capture requires schema_error call metadata.")
        if (
            self.provider != self.model_call.provider
            or self.model_id != self.model_call.model_id
            or self.prompt_version != self.model_call.prompt_version
        ):
            raise ValueError("Rejected capture identity must match call metadata.")
        return self


class InitialSemanticValidation(StrictModel):
    """Immutable record of the source capture's historical rejection."""

    status: Literal["semantic_validation_failed"] = "semantic_validation_failed"
    error_code: Literal["structured_output_invalid"] = "structured_output_invalid"
    reason_code: Literal["semantic_content_rule_failed"] = (
        "semantic_content_rule_failed"
    )
    rule_codes: tuple[ContentRuleCode, ...]
    field_paths: tuple[SafeDiagnostic, ...]

    @model_validator(mode="after")
    def only_summary_relation_is_eligible(self) -> InitialSemanticValidation:
        if self.rule_codes != ("implicit_cross_domain_relation",):
            raise ValueError("Initial validation must contain the sole eligible rule.")
        if self.field_paths != ("summary",):
            raise ValueError("Initial validation must concern only the summary.")
        return self


class PostNormalizationValidation(StrictModel):
    """Closed successful result after deterministic summary normalization."""

    status: Literal["validated"] = "validated"
    rule_codes: tuple[ContentRuleCode, ...] = ()
    field_paths: tuple[SafeDiagnostic, ...] = ()
    reliable_render: Literal[True] = True

    @model_validator(mode="after")
    def diagnostics_are_empty(self) -> PostNormalizationValidation:
        if self.rule_codes or self.field_paths:
            raise ValueError("Post-normalization validation cannot retain diagnostics.")
        return self


class SanitizedLiveCaptureCandidate(StrictModel):
    """Live-derived candidate awaiting human review after Python-only normalization."""

    schema_version: Literal["sanitized-live-capture-candidate.v1"] = (
        "sanitized-live-capture-candidate.v1"
    )
    artifact_type: Literal["sanitized_live_capture_candidate"] = (
        "sanitized_live_capture_candidate"
    )
    status: Literal["pending_human_review"] = "pending_human_review"
    demo_eligible: Literal[False] = False
    promotion_policy: Literal["human_review_required_before_fixture_promotion"] = (
        "human_review_required_before_fixture_promotion"
    )
    response_origin: Literal["live_provider"] = "live_provider"
    fixture_derivation: Literal["live_derived_deterministically_normalized"] = (
        "live_derived_deterministically_normalized"
    )
    normalization_version: CanonicalSummaryVersion
    normalized_fields: tuple[Literal["summary"], ...] = ("summary",)
    raw_provider_response_persisted: Literal[False] = False
    source_artifact_type: Literal["rejected_live_capture"] = "rejected_live_capture"
    source_artifact_sha256: Sha256
    source_response_id: NonEmptyText
    source_request_id: NonEmptyText
    source_prompt_version: Literal["trust-synthesis-v3"]
    validated_input_schema_version: Literal["validated-run-input.v1"]
    run_id: Identifier
    provider: Identifier
    model_id: NonEmptyText
    proposal: DraftProposal
    initial_validation: InitialSemanticValidation
    post_normalization_validation: PostNormalizationValidation
    validation_report: ValidationReport
    rendered_draft: RenderedDraft
    model_call: ModelCallMetadata

    @model_validator(mode="after")
    def provenance_and_results_are_consistent(self) -> SanitizedLiveCaptureCandidate:
        if self.normalization_version != CANONICAL_SUMMARY_VERSION:
            raise ValueError("Candidate normalization version is not current.")
        if self.normalized_fields != ("summary",):
            raise ValueError("Only the summary may be normalized.")
        if self.model_call.response_origin != self.response_origin:
            raise ValueError("Candidate response origin must match call metadata.")
        if self.model_call.status != "schema_error":
            raise ValueError("Historical source call status must remain schema_error.")
        if self.model_call.response_id != self.source_response_id:
            raise ValueError("Candidate response ID must match source call metadata.")
        if self.model_call.provider_request_id != self.source_request_id:
            raise ValueError("Candidate request ID must match source call metadata.")
        if self.model_call.prompt_version != self.source_prompt_version:
            raise ValueError("Candidate prompt version must match source call metadata.")
        if self.model_call.provider != self.provider or self.model_call.model_id != self.model_id:
            raise ValueError("Candidate provider identity must match call metadata.")
        if self.proposal.summary != CANONICAL_SUMMARY_METRICS_AND_EVIDENCE:
            raise ValueError("Candidate summary must be the server-owned canonical text.")
        if self.validation_report.run_id != self.run_id:
            raise ValueError("Validation report must belong to the candidate run.")
        if self.validation_report.issues:
            raise ValueError("Candidate validation report must contain no issues.")
        if self.rendered_draft.run_id != self.run_id or not self.rendered_draft.reliable:
            raise ValueError("Candidate requires a reliable same-run rendering.")
        if self.validation_report.draft_id != self.rendered_draft.draft_id:
            raise ValueError("Validation and rendering must identify the same draft.")
        return self


class SanitizedCandidateError(RuntimeError):
    """Clean deterministic failure from rejected-capture normalization."""

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


RejectedOutputErrorCode = Literal[
    "rejected-output-exists",
    "rejected-output-write-error",
]
RejectedOutputStatus = Literal["not_requested", "written", "write_failed"]


class LiveCaptureError(RuntimeError):
    """Stable, sanitized failure from capture preparation or execution."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        model_call: ModelCallMetadata | None = None,
        failure: PublicLLMFailure | None = None,
        rejected_output_status: RejectedOutputStatus = "not_requested",
        rejected_output_error_code: RejectedOutputErrorCode | None = None,
    ) -> None:
        super().__init__(message)
        if error_code is None and failure is None:
            raise ValueError("LiveCaptureError requires an error code or public failure.")
        self.failure = failure
        self.error_code = failure.error_code if failure is not None else error_code
        self.reason_code = None if failure is None else failure.reason_code
        self.http_status = None if failure is None else failure.http_status
        self.request_id = None if failure is None else failure.request_id
        self.model_call = model_call
        self.status = "capture_failed" if model_call is None else model_call.status
        self.rejected_output_status = rejected_output_status
        self.rejected_output_error_code = rejected_output_error_code


def prepare_live_capture(
    input_path: Path,
    output_path: Path,
    *,
    model: str,
    overwrite: bool = False,
) -> LiveCapturePlan:
    """Validate input, allowlists and output path without initializing Anthropic."""

    _, request, plan = _prepare(
        input_path,
        output_path,
        model=model,
        overwrite=overwrite,
    )
    # Building this strict request performs run-membership and exact-allowlist validation.
    assert request.allowed_evidence_ids
    return plan


def capture_live_once(
    input_path: Path,
    output_path: Path,
    *,
    settings: Settings,
    confirm_paid_call: bool,
    overwrite: bool = False,
    rejected_output_path: Path | None = None,
    client: AnthropicLLMClient | None = None,
) -> LiveCaptureOutput:
    """Perform exactly one explicitly authorized call and write only cleaned output."""

    if not confirm_paid_call:
        raise LiveCaptureError(
            "Live capture requires explicit paid-call confirmation.",
            error_code="live-confirmation-required",
        ) from None
    if settings.app_mode is not AppMode.LIVE:
        raise LiveCaptureError(
            "Live capture requires APP_MODE=live.",
            error_code="live-mode-required",
        ) from None
    if settings.anthropic_api_key is None:
        raise LiveCaptureError(
            "Live capture requires an Anthropic API key.",
            error_code="live-key-required",
        ) from None
    if settings.anthropic_model is None:
        raise LiveCaptureError(
            "Live capture requires an Anthropic model.",
            error_code="live-model-required",
        ) from None
    validated_run, request, _ = _prepare(
        input_path,
        output_path,
        model=settings.anthropic_model,
        overwrite=overwrite,
    )
    if client is not None and client.model != settings.anthropic_model:
        raise LiveCaptureError(
            "Injected Anthropic client does not match ANTHROPIC_MODEL.",
            error_code="live-model-mismatch",
        ) from None

    selected_client = client or AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )
    public_error: LiveCaptureError | None = None
    result = None
    try:
        result = selected_client.synthesize(request)
    except LLMClientError as exc:
        rejected_output_status: RejectedOutputStatus = "not_requested"
        rejected_output_error_code: RejectedOutputErrorCode | None = None
        if rejected_output_path is not None and _is_semantic_rejection(exc):
            proposal = getattr(exc, "_rejected_proposal", None)
            if isinstance(proposal, DraftProposal):
                artifact_write_failed = False
                try:
                    artifact = RejectedLiveCapture(
                        run_id=validated_run.run_id,
                        provider=exc.metadata.provider,
                        model_id=exc.metadata.model_id,
                        prompt_version=exc.metadata.prompt_version,
                        proposal=proposal,
                        rule_codes=exc.failure.content_rule_codes,
                        field_paths=exc.failure.validation_field_paths,
                        model_call=exc.metadata,
                    )
                    rejected_output_error_code = _write_rejected_capture(
                        artifact,
                        rejected_output_path,
                    )
                except Exception:
                    artifact_write_failed = True
                if artifact_write_failed:
                    rejected_output_error_code = "rejected-output-write-error"
                rejected_output_status = (
                    "written"
                    if rejected_output_error_code is None
                    else "write_failed"
                )
        public_error = LiveCaptureError(
            "Anthropic capture synthesis failed.",
            model_call=exc.metadata,
            failure=exc.failure,
            rejected_output_status=rejected_output_status,
            rejected_output_error_code=rejected_output_error_code,
        )
    except Exception:
        public_error = LiveCaptureError(
            "Anthropic capture synthesis failed.",
            failure=PublicLLMFailure(error_code="unknown_provider_error"),
        )
    if public_error is not None:
        raise public_error from None
    assert result is not None

    post_validation_error: LiveCaptureError | None = None
    proposal: DraftProposal | None = None
    try:
        revalidated = validated_synthesis_result(
            result.payload_json,
            request,
            result.metadata,
        )
        proposal = DraftProposal.model_validate_json(revalidated.payload_json)
    except LLMClientError as exc:
        post_validation_error = LiveCaptureError(
            "Captured response failed post-call validation.",
            model_call=exc.metadata,
            failure=exc.failure,
        )
    except ValidationError:
        post_validation_error = LiveCaptureError(
            "Captured response failed post-call validation.",
            error_code="live-post-validation-error",
            model_call=result.metadata,
        )
    if post_validation_error is not None:
        raise post_validation_error from None
    assert proposal is not None

    capture = LiveCaptureOutput(
        run_id=validated_run.run_id,
        proposal=proposal,
        model_call=result.metadata,
    )
    _write_capture(capture, output_path, overwrite=overwrite)
    return capture


def sanitize_rejected_live_capture(
    rejected_path: Path,
    validated_input_path: Path,
    output_path: Path,
) -> SanitizedLiveCaptureCandidate:
    """Create one human-review candidate without any provider or network call."""

    if output_path.exists():
        raise SanitizedCandidateError(
            "Sanitized candidate output already exists.",
            error_code="sanitized-output-exists",
        ) from None
    if not output_path.parent.is_dir():
        raise SanitizedCandidateError(
            "Sanitized candidate output directory does not exist.",
            error_code="sanitized-output-directory-invalid",
        ) from None

    try:
        rejected_bytes = rejected_path.read_bytes()
        rejected_json = rejected_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise SanitizedCandidateError(
            "Rejected capture is missing or invalid.",
            error_code="sanitized-source-invalid",
        ) from None

    try:
        rejected = RejectedLiveCapture.model_validate_json(rejected_json)
    except ValidationError:
        try:
            SanitizedLiveCaptureCandidate.model_validate_json(rejected_json)
        except ValidationError:
            error_code = "sanitized-source-invalid"
        else:
            error_code = "sanitized-source-already-normalized"
        raise SanitizedCandidateError(
            "Source is not an eligible rejected live capture.",
            error_code=error_code,
        ) from None

    try:
        validated_run = ValidatedRunInput.model_validate_json(
            validated_input_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError):
        raise SanitizedCandidateError(
            "Validated run input is missing or invalid.",
            error_code="sanitized-run-input-invalid",
        ) from None

    if (
        rejected.rule_codes != ("implicit_cross_domain_relation",)
        or rejected.field_paths != ("summary",)
        or rejected.run_id != validated_run.run_id
        or rejected.prompt_version != validated_run.prompt_version
        or rejected.model_call.response_origin != "live_provider"
        or rejected.model_call.response_id is None
        or rejected.model_call.provider_request_id is None
    ):
        raise SanitizedCandidateError(
            "Rejected capture is outside the narrow normalization eligibility gate.",
            error_code="sanitized-source-ineligible",
        ) from None

    request = build_synthesis_request(
        run_id=validated_run.run_id,
        metrics=validated_run.metrics,
        evidence=validated_run.evidence,
        limits=validated_run.limits,
        context=validated_run.context,
        prompt_version=validated_run.prompt_version,
    )
    source_diagnostics = proposal_content_rule_diagnostics(
        rejected.proposal,
        request,
    )
    if source_diagnostics != (("summary", "implicit_cross_domain_relation"),):
        raise SanitizedCandidateError(
            "Rejected proposal no longer reproduces its sole recorded violation.",
            error_code="sanitized-source-diagnostics-mismatch",
        ) from None

    normalized = normalize_proposal_summary(
        rejected.proposal,
        has_metrics=bool(request.metrics),
        has_evidence=bool(request.evidence),
    )
    if (
        normalized.claims != rejected.proposal.claims
        or normalized.limitations != rejected.proposal.limitations
    ):
        raise SanitizedCandidateError(
            "Normalization attempted to modify a non-summary field.",
            error_code="sanitized-normalization-scope-error",
        ) from None

    try:
        validated_result = validated_synthesis_result(
            normalized.model_dump_json(),
            request,
            rejected.model_call,
        )
        validated_proposal = DraftProposal.model_validate_json(
            validated_result.payload_json
        )
    except (LLMClientError, ValidationError):
        raise SanitizedCandidateError(
            "Normalized proposal failed deterministic boundary validation.",
            error_code="sanitized-post-validation-failed",
        ) from None

    generated_at = (
        datetime.combine(rejected.model_call.pricing_valid_on, time.min, tzinfo=UTC)
        if rejected.model_call.pricing_valid_on is not None
        else datetime(1970, 1, 1, tzinfo=UTC)
    )
    generation = GenerationMetadata(
        provider=rejected.provider,
        model_id=rejected.model_id,
        parameters=(
            GenerationParameter(
                name="max-output-tokens",
                value=validated_run.limits.max_output_tokens,
            ),
            GenerationParameter(
                name="normalization-version",
                value=CANONICAL_SUMMARY_VERSION,
            ),
        ),
        prompt_version=rejected.prompt_version,
        response_id=rejected.model_call.response_id,
        generated_at=generated_at,
        model_call=rejected.model_call,
    )
    draft = materialize_generated_draft(
        validated_run.run_id,
        validated_proposal,
        generation,
    )
    report = validate_draft(
        run_id=validated_run.run_id,
        draft=draft,
        metrics=validated_run.metrics,
        evidence=validated_run.evidence,
    )
    rendered = render_validated_draft(
        draft=draft,
        report=report,
        metrics=validated_run.metrics,
        evidence=validated_run.evidence,
    )
    if report.issues or not rendered.reliable:
        raise SanitizedCandidateError(
            "Normalized proposal failed trusted validation or rendering.",
            error_code="sanitized-render-failed",
        ) from None

    candidate = SanitizedLiveCaptureCandidate(
        normalization_version=CANONICAL_SUMMARY_VERSION,
        source_artifact_sha256=hashlib.sha256(rejected_bytes).hexdigest(),
        source_response_id=rejected.model_call.response_id,
        source_request_id=rejected.model_call.provider_request_id,
        source_prompt_version=rejected.prompt_version,
        validated_input_schema_version=validated_run.schema_version,
        run_id=validated_run.run_id,
        provider=rejected.provider,
        model_id=rejected.model_id,
        proposal=validated_proposal,
        initial_validation=InitialSemanticValidation(
            rule_codes=rejected.rule_codes,
            field_paths=rejected.field_paths,
        ),
        post_normalization_validation=PostNormalizationValidation(),
        validation_report=report,
        rendered_draft=rendered,
        model_call=rejected.model_call,
    )
    write_result = _atomic_write_new(
        candidate.model_dump_json(indent=2) + "\n",
        output_path,
    )
    if write_result is not None:
        raise SanitizedCandidateError(
            "Sanitized candidate output could not be written.",
            error_code=(
                "sanitized-output-exists"
                if write_result == "rejected-output-exists"
                else "sanitized-output-write-error"
            ),
        ) from None
    return candidate


def _prepare(
    input_path: Path,
    output_path: Path,
    *,
    model: str,
    overwrite: bool,
) -> tuple[ValidatedRunInput, SynthesisRequest, LiveCapturePlan]:
    if not model.strip():
        raise LiveCaptureError(
            "Dry-run requires ANTHROPIC_MODEL.",
            error_code="live-model-required",
        ) from None
    invalid_input = False
    try:
        validated_run = ValidatedRunInput.model_validate_json(
            input_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError):
        invalid_input = True
    if invalid_input:
        raise LiveCaptureError(
            "Live capture input is missing or invalid.",
            error_code="live-input-invalid",
        ) from None
    assert validated_run is not None

    if output_path.exists() and not overwrite:
        raise LiveCaptureError(
            "Live capture output already exists; explicit overwrite is required.",
            error_code="live-output-exists",
        ) from None
    if not output_path.parent.is_dir():
        raise LiveCaptureError(
            "Live capture output directory does not exist.",
            error_code="live-output-directory-invalid",
        ) from None

    request = build_synthesis_request(
        run_id=validated_run.run_id,
        metrics=validated_run.metrics,
        evidence=validated_run.evidence,
        limits=validated_run.limits,
        context=validated_run.context,
        prompt_version=validated_run.prompt_version,
    )
    plan = LiveCapturePlan(
        output_path=output_path.as_posix(),
        overwrite=overwrite,
        request=LiveCaptureRequestSummary(
            run_id=request.run_id,
            prompt_version=request.prompt_version,
            model_id=model,
            metric_count=len(request.metrics),
            evidence_count=len(request.evidence),
            allowlisted_metric_id_count=len(request.allowed_metric_ids),
            allowlisted_evidence_id_count=len(request.allowed_evidence_ids),
            max_output_tokens=request.limits.max_output_tokens,
            timeout_seconds=request.limits.timeout_seconds,
        ),
    )
    return validated_run, request, plan


def write_live_capture_plan(
    plan: LiveCapturePlan,
    output_path: Path,
    *,
    overwrite: bool,
) -> None:
    """Write only the prompt-free dry-run plan to the requested temporary path."""

    _write_json(
        plan.model_dump_json(indent=2) + "\n",
        output_path,
        overwrite=overwrite,
        model_call=None,
    )


def _write_capture(
    capture: LiveCaptureOutput,
    output_path: Path,
    *,
    overwrite: bool,
) -> None:
    payload = capture.model_dump_json(indent=2) + "\n"
    _write_json(
        payload,
        output_path,
        overwrite=overwrite,
        model_call=capture.model_call,
    )


def _is_semantic_rejection(error: LLMClientError) -> bool:
    return (
        error.error_code == "structured_output_invalid"
        and error.reason_code == "semantic_content_rule_failed"
        and error.metadata.response_id is not None
        and bool(error.failure.content_rule_codes)
        and bool(error.failure.validation_field_paths)
    )


def _write_rejected_capture(
    capture: RejectedLiveCapture,
    output_path: Path,
) -> RejectedOutputErrorCode | None:
    payload = capture.model_dump_json(indent=2) + "\n"
    return _atomic_write_new(payload, output_path)


def _atomic_write_new(
    payload: str,
    output_path: Path,
) -> RejectedOutputErrorCode | None:
    if output_path.exists():
        return "rejected-output-exists"
    if not output_path.parent.is_dir():
        return "rejected-output-write-error"

    temporary_path: Path | None = None
    result: RejectedOutputErrorCode | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as destination:
            temporary_path = Path(destination.name)
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        try:
            os.link(temporary_path, output_path)
        except FileExistsError:
            result = "rejected-output-exists"
        except OSError:
            result = "rejected-output-write-error"
    except OSError:
        result = "rejected-output-write-error"
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return result


def _write_json(
    payload: str,
    output_path: Path,
    *,
    overwrite: bool,
    model_call: ModelCallMetadata | None,
) -> None:
    write_failed = False
    try:
        if overwrite:
            output_path.write_text(payload, encoding="utf-8")
        else:
            with output_path.open("x", encoding="utf-8") as destination:
                destination.write(payload)
    except OSError:
        write_failed = True
    if write_failed:
        raise LiveCaptureError(
            "Live capture output could not be written.",
            error_code="live-output-write-error",
            model_call=model_call,
        ) from None
