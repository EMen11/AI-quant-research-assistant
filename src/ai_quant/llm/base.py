"""One structured LLM boundary with a deterministic offline implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ai_quant.content_rules import (
    contains_metric_value,
    evidence_placeholder_ids,
    evidence_supports_numeric_text,
    has_any_placeholder,
    has_generic_placeholder,
    has_implicit_cross_domain_relation,
    has_internal_status_token,
    has_prohibited_risk_language,
    has_unknown_placeholder_kind,
    has_unsupported_period_alignment,
    metric_placeholder_ids,
    normalize_proposal_summary,
    numeric_literals,
)
from ai_quant.model_calls import ModelCallMetadata, failed_model_call

Identifier = Annotated[
    str,
    Field(min_length=3, max_length=160, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
]
PublicLLMErrorCode = Literal[
    "invalid_request_error",
    "authentication_error",
    "billing_error",
    "permission_error",
    "not_found_error",
    "rate_limit_error",
    "provider_api_error",
    "timeout_error",
    "overloaded_error",
    "connection_error",
    "structured_output_invalid",
    "unknown_provider_error",
    "llm-allowlist-error",
]
InvalidRequestReasonCode = Literal[
    "unsupported_sampling_parameter",
    "unsupported_thinking_configuration",
    "invalid_output_schema",
    "schema_too_complex",
    "invalid_max_tokens",
    "invalid_model_parameter",
    "invalid_messages_parameter",
    "invalid_system_parameter",
    "other_invalid_request",
]
StructuredOutputReasonCode = Literal[
    "max_tokens_exhausted",
    "provider_refusal",
    "missing_parsed_output",
    "pydantic_structure_invalid",
    "semantic_content_rule_failed",
    "response_json_invalid",
    "unknown_structured_output_error",
]
ContentRuleCode = Literal[
    "claim_limit_exceeded",
    "evidence_numeric_literal_unverified",
    "evidence_reference_mismatch",
    "free_numeric_literal",
    "generic_placeholder",
    "implicit_cross_domain_relation",
    "internal_status_token",
    "metric_placeholder_mismatch",
    "metric_value_literal",
    "summary_placeholder",
    "unsupported_period_alignment",
    "unsupported_risk_statement",
    "unresolved_placeholder",
]
PublicLLMReasonCode = InvalidRequestReasonCode | StructuredOutputReasonCode
SafeDiagnostic = Annotated[
    str,
    Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.$\[\]-]+$"),
]

_INVALID_REQUEST_REASON_CODES = {
    "unsupported_sampling_parameter",
    "unsupported_thinking_configuration",
    "invalid_output_schema",
    "schema_too_complex",
    "invalid_max_tokens",
    "invalid_model_parameter",
    "invalid_messages_parameter",
    "invalid_system_parameter",
    "other_invalid_request",
}
_STRUCTURED_OUTPUT_REASON_CODES = {
    "max_tokens_exhausted",
    "provider_refusal",
    "missing_parsed_output",
    "pydantic_structure_invalid",
    "semantic_content_rule_failed",
    "response_json_invalid",
    "unknown_structured_output_error",
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class LLMMetricInput(_StrictModel):
    """Authorized Python-computed metric projection supplied to synthesis."""

    metric_id: Identifier
    run_id: Identifier
    metric_name: Identifier
    value: float
    unit: str = Field(min_length=1, max_length=200)


class LLMEvidenceInput(_StrictModel):
    """Authorized server-owned evidence projection supplied to synthesis."""

    evidence_id: Identifier
    run_id: Identifier
    excerpt: str = Field(min_length=1, max_length=4_000)
    provenance_label: Literal["synthetic_demo_evidence", "official_corpus_passage"]


class SynthesisLimits(_StrictModel):
    """Explicit output and transport limits for one synthesis attempt."""

    max_output_tokens: int = Field(default=1_200, ge=1, le=8_192)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    max_claims: int = Field(default=12, ge=1, le=12)


class SynthesisRequest(_StrictModel):
    """Closed request containing only current-run authorized material."""

    schema_version: Literal["synthesis-request.v1"] = "synthesis-request.v1"
    run_id: Identifier
    prompt_version: Literal["trust-synthesis-v3"] = "trust-synthesis-v3"
    context: str = Field(min_length=1, max_length=50_000)
    metrics: tuple[LLMMetricInput, ...]
    evidence: tuple[LLMEvidenceInput, ...]
    allowed_metric_ids: tuple[Identifier, ...]
    allowed_evidence_ids: tuple[Identifier, ...]
    limits: SynthesisLimits = SynthesisLimits()

    @model_validator(mode="after")
    def inputs_match_run_and_allowlists(self) -> SynthesisRequest:
        if not self.metrics and not self.evidence:
            raise ValueError(
                "Synthesis requires at least one metric or evidence record."
            )
        if any(metric.run_id != self.run_id for metric in self.metrics):
            raise ValueError("Every metric input must belong to the synthesis run.")
        if any(record.run_id != self.run_id for record in self.evidence):
            raise ValueError("Every evidence input must belong to the synthesis run.")
        metric_ids = tuple(metric.metric_id for metric in self.metrics)
        evidence_ids = tuple(record.evidence_id for record in self.evidence)
        if len(set(metric_ids)) != len(metric_ids) or len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Synthesis inputs must have unique IDs.")
        if metric_ids != self.allowed_metric_ids:
            raise ValueError("Metric allowlist must exactly match the supplied metric inputs.")
        if evidence_ids != self.allowed_evidence_ids:
            raise ValueError("Evidence allowlist must exactly match the supplied evidence inputs.")
        return self


class PublicLLMFailure(_StrictModel):
    """Sanitized public diagnosis detached from every raw provider object."""

    error_code: PublicLLMErrorCode
    reason_code: PublicLLMReasonCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    validation_field_paths: tuple[SafeDiagnostic, ...] = ()
    validation_error_types: tuple[SafeDiagnostic, ...] = ()
    content_rule_codes: tuple[ContentRuleCode, ...] = ()
    status: Literal["failed"] = "failed"

    @model_validator(mode="after")
    def reason_matches_error_family(self) -> PublicLLMFailure:
        if self.reason_code in _INVALID_REQUEST_REASON_CODES:
            if self.error_code != "invalid_request_error":
                raise ValueError("Invalid-request reasons require invalid_request_error.")
        elif self.reason_code in _STRUCTURED_OUTPUT_REASON_CODES:
            if self.error_code != "structured_output_invalid":
                raise ValueError(
                    "Structured-output reasons require structured_output_invalid."
                )
        elif self.reason_code is not None:
            raise ValueError("Unknown public LLM reason code.")
        has_diagnostics = bool(
            self.validation_field_paths
            or self.validation_error_types
            or self.content_rule_codes
        )
        if has_diagnostics and self.error_code != "structured_output_invalid":
            raise ValueError("Validation diagnostics require structured_output_invalid.")
        return self


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Legacy deterministic text response retained for the minimal demo page."""

    text: str
    provider: str


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    """Validated proposal JSON plus secret-free call metadata."""

    payload_json: str
    metadata: ModelCallMetadata


class LLMClient(Protocol):
    """Canonical interface for one typed structured synthesis call."""

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Return one validated structured proposal."""


class TextLLMClient(Protocol):
    """Compatibility interface used only by the original text-only demo caption."""

    def complete(self, prompt: str) -> LLMResponse:
        """Return a deterministic text response."""


class LLMClientError(RuntimeError):
    """Clean business exception retaining available call metadata."""

    default_error_code: PublicLLMErrorCode = "unknown_provider_error"

    def __init__(
        self,
        message: str,
        metadata: ModelCallMetadata,
        failure: PublicLLMFailure | None = None,
        *,
        rejected_proposal: BaseModel | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = metadata
        self.status = metadata.status
        self.failure = failure or PublicLLMFailure(error_code=self.default_error_code)
        self.error_code = self.failure.error_code
        self.reason_code = self.failure.reason_code
        self.http_status = self.failure.http_status
        self.request_id = self.failure.request_id
        self._rejected_proposal = rejected_proposal


class LLMProviderError(LLMClientError):
    """Provider or transport failure."""

    default_error_code: PublicLLMErrorCode = "unknown_provider_error"


class LLMTimeoutError(LLMClientError):
    """Transport timeout."""

    default_error_code: PublicLLMErrorCode = "timeout_error"


class LLMSchemaError(LLMClientError):
    """Provider output violates the strict proposal schema."""

    default_error_code: PublicLLMErrorCode = "structured_output_invalid"


class LLMAllowlistError(LLMClientError):
    """Provider output references an ID outside the exact run allowlist."""

    default_error_code: PublicLLMErrorCode = "llm-allowlist-error"


FakeMode = Literal["success", "invalid_schema", "out_of_allowlist", "error", "timeout"]


class FakeLLMClient:
    """Configurable deterministic fake; it never initializes a network client."""

    def __init__(
        self,
        response_text: str = "Offline demo ready.",
        *,
        payload_json: str | None = None,
        mode: FakeMode = "success",
    ) -> None:
        self._response_text = response_text
        self._payload_json = payload_json
        self._mode = mode
        self.call_count = 0
        self.last_request: SynthesisRequest | None = None

    def complete(self, prompt: str) -> LLMResponse:
        """Return fixed text for the pre-existing demo without network access."""

        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        self.call_count += 1
        return LLMResponse(text=self._response_text, provider="fake")

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Perform exactly one deterministic structured fake call."""

        self.call_count += 1
        self.last_request = request
        if self._mode == "error":
            metadata = _fake_metadata(request, "provider_error", "FakeProviderError")
            raise LLMProviderError("Structured synthesis provider failed.", metadata)
        if self._mode == "timeout":
            metadata = _fake_metadata(request, "timeout", "FakeTimeout")
            raise LLMTimeoutError("Structured synthesis timed out.", metadata)

        payload = self._payload_json or _default_payload(request)
        if self._mode == "invalid_schema":
            payload = '{"summary":"invalid","claims":[],"limitations":[],"extra":true}'
        elif self._mode == "out_of_allowlist":
            payload = _out_of_allowlist_payload()

        metadata = _fake_metadata(request, "success", None)
        return _validated_result(payload, request, metadata)


FakeLLM = FakeLLMClient


def validated_synthesis_result(
    payload_json: str,
    request: SynthesisRequest,
    metadata: ModelCallMetadata,
) -> SynthesisResult:
    """Validate provider JSON and exact output allowlists at the client boundary."""

    return _validated_result(payload_json, request, metadata)


def _validated_result(
    payload_json: str,
    request: SynthesisRequest,
    metadata: ModelCallMetadata,
) -> SynthesisResult:
    from ai_quant.trust.models import DraftProposal

    validation_diagnostics: tuple[tuple[str, ...], tuple[str, ...]] | None = None
    proposal = None
    try:
        proposal = DraftProposal.model_validate_json(payload_json)
    except ValidationError as error:
        validation_diagnostics = _safe_pydantic_diagnostics(error)

    if validation_diagnostics is not None:
        field_paths, error_types = validation_diagnostics
        reason_code: StructuredOutputReasonCode = (
            "response_json_invalid"
            if "json_invalid" in error_types
            else "pydantic_structure_invalid"
        )
        failed = failed_model_call(
            metadata,
            status="schema_error",
            error_type="DraftSchemaValidationError",
        )
        failure = PublicLLMFailure(
            error_code="structured_output_invalid",
            reason_code=reason_code,
            request_id=metadata.provider_request_id,
            validation_field_paths=field_paths,
            validation_error_types=error_types,
        )
        raise LLMSchemaError(
            "Structured synthesis response failed validation.", failed, failure
        ) from None

    assert proposal is not None
    proposal = normalize_proposal_summary(
        proposal,
        has_metrics=bool(request.metrics),
        has_evidence=bool(request.evidence),
    )

    if len(proposal.claims) > request.limits.max_claims:
        failed = failed_model_call(
            metadata,
            status="schema_error",
            error_type="OutputLimitViolation",
        )
        failure = PublicLLMFailure(
            error_code="structured_output_invalid",
            reason_code="semantic_content_rule_failed",
            request_id=metadata.provider_request_id,
            validation_field_paths=("claims",),
            content_rule_codes=("claim_limit_exceeded",),
        )
        raise LLMSchemaError(
            "Structured synthesis exceeded the claim limit.",
            failed,
            failure,
            rejected_proposal=proposal,
        ) from None

    metric_ids = {metric_id for claim in proposal.claims for metric_id in claim.metric_ids}
    evidence_ids = {evidence_id for claim in proposal.claims for evidence_id in claim.evidence_ids}
    placeholder_metric_ids = {
        metric_id
        for claim in proposal.claims
        for metric_id in metric_placeholder_ids(claim.text_template)
    }
    placeholder_evidence_ids = {
        evidence_id
        for claim in proposal.claims
        for evidence_id in evidence_placeholder_ids(claim.text_template)
    }
    unknown_metrics = (metric_ids | placeholder_metric_ids) - set(
        request.allowed_metric_ids
    )
    unknown_evidence = (evidence_ids | placeholder_evidence_ids) - set(
        request.allowed_evidence_ids
    )
    if unknown_metrics or unknown_evidence:
        failed = failed_model_call(
            metadata,
            status="allowlist_error",
            error_type="OutputAllowlistViolation",
        )
        failure = PublicLLMFailure(
            error_code="llm-allowlist-error",
            request_id=metadata.provider_request_id,
        )
        raise LLMAllowlistError(
            "Structured synthesis returned a reference outside the run allowlist.",
            failed,
            failure,
        ) from None
    content_violations = _proposal_content_rule_violations(proposal, request)
    if content_violations:
        failed = failed_model_call(
            metadata,
            status="schema_error",
            error_type="DraftContentValidationError",
        )
        failure = PublicLLMFailure(
            error_code="structured_output_invalid",
            reason_code="semantic_content_rule_failed",
            request_id=metadata.provider_request_id,
            validation_field_paths=_unique(
                violation.field_path for violation in content_violations
            ),
            content_rule_codes=_unique(
                violation.rule_code for violation in content_violations
            ),
        )
        raise LLMSchemaError(
            "Structured synthesis response violated deterministic content rules.",
            failed,
            failure,
            rejected_proposal=proposal,
        ) from None
    return SynthesisResult(payload_json=proposal.model_dump_json(), metadata=metadata)


def _default_payload(request: SynthesisRequest) -> str:
    claims: list[dict[str, object]] = []
    for metric in request.metrics:
        claims.append(
            {
                "text_template": (
                    f"The historical {metric.metric_name} observation is "
                    f"{{{{metric:{metric.metric_id}}}}}."
                ),
                "claim_type": "quantitative",
                "metric_ids": [metric.metric_id],
                "evidence_ids": [],
                "uncertainty": "Historical metrics are descriptive and not forecasts.",
            }
        )
    for evidence in request.evidence:
        claims.append(
            {
                "text_template": (
                    "Separately, the authorized evidence reference is "
                    f"{{{{evidence:{evidence.evidence_id}}}}}."
                ),
                "claim_type": "evidence",
                "metric_ids": [],
                "evidence_ids": [evidence.evidence_id],
                "uncertainty": "The source passage remains subject to human review.",
            }
        )
    if not claims:
        claims.append(
            {
                "text_template": "No authorized metric or evidence was supplied.",
                "claim_type": "limitation",
                "metric_ids": [],
                "evidence_ids": [],
                "uncertainty": "Synthesis is intentionally limited.",
            }
        )
    return json.dumps(
        {
            "summary": (
                "Historical financial metrics and authorized evidence are "
                "presented as separate observations."
            ),
            "claims": claims[: request.limits.max_claims],
            "limitations": [
                "The metrics describe a single run.",
                "No out-of-sample validation is included.",
                "No live trading validation or investment recommendation is provided.",
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class _ContentRuleViolation:
    field_path: str
    rule_code: ContentRuleCode


def _proposal_content_rule_violations(  # type: ignore[no-untyped-def]
    proposal,
    request: SynthesisRequest,
) -> tuple[_ContentRuleViolation, ...]:
    evidence_by_id = {record.evidence_id: record for record in request.evidence}
    violations: list[_ContentRuleViolation] = []
    prose_fields = [("summary", proposal.summary)]
    prose_fields.extend(
        (f"limitations.{index}", text)
        for index, text in enumerate(proposal.limitations)
    )
    if has_any_placeholder(proposal.summary):
        violations.append(_ContentRuleViolation("summary", "summary_placeholder"))
    violations.extend(
        _ContentRuleViolation(path, "unresolved_placeholder")
        for path, text in prose_fields[1:]
        if has_any_placeholder(text)
    )

    for index, claim in enumerate(proposal.claims):
        template_path = f"claims.{index}.text_template"
        metric_placeholders = set(metric_placeholder_ids(claim.text_template))
        evidence_placeholders = set(evidence_placeholder_ids(claim.text_template))
        if metric_placeholders != set(claim.metric_ids):
            violations.append(
                _ContentRuleViolation(template_path, "metric_placeholder_mismatch")
            )
        if evidence_placeholders != set(claim.evidence_ids):
            violations.append(
                _ContentRuleViolation(template_path, "evidence_reference_mismatch")
            )
        if has_generic_placeholder(claim.text_template):
            violations.append(_ContentRuleViolation(template_path, "generic_placeholder"))
        if has_unknown_placeholder_kind(claim.text_template):
            violations.append(
                _ContentRuleViolation(template_path, "unresolved_placeholder")
            )
        claim_fields = [(template_path, claim.text_template)]
        if claim.uncertainty is not None:
            claim_fields.append((f"claims.{index}.uncertainty", claim.uncertainty))
        prose_fields.extend(claim_fields)
        if claim.claim_type == "quantitative" and numeric_literals(claim.text_template):
            violations.append(_ContentRuleViolation(template_path, "free_numeric_literal"))
        if claim.claim_type == "evidence":
            excerpts = tuple(
                evidence_by_id[evidence_id].excerpt
                for evidence_id in claim.evidence_ids
                if evidence_id in evidence_by_id
            )
            violations.extend(
                _ContentRuleViolation(path, "evidence_numeric_literal_unverified")
                for path, text in claim_fields
                if numeric_literals(text)
                and not evidence_supports_numeric_text(text, excerpts)
            )

    for path, text in prose_fields:
        if any(contains_metric_value(text, metric.value) for metric in request.metrics):
            violations.append(_ContentRuleViolation(path, "metric_value_literal"))
        if has_prohibited_risk_language(text):
            violations.append(
                _ContentRuleViolation(path, "unsupported_risk_statement")
            )
        if has_internal_status_token(text):
            violations.append(_ContentRuleViolation(path, "internal_status_token"))
        if has_implicit_cross_domain_relation(text):
            violations.append(
                _ContentRuleViolation(path, "implicit_cross_domain_relation")
            )
        if (
            request.metrics
            and request.evidence
            and has_unsupported_period_alignment(text)
        ):
            violations.append(
                _ContentRuleViolation(path, "unsupported_period_alignment")
            )
    if any(token.endswith("%") for token in numeric_literals(proposal.summary)):
        violations.append(_ContentRuleViolation("summary", "free_numeric_literal"))
    return tuple(violations)


def proposal_content_rule_diagnostics(
    proposal,  # type: ignore[no-untyped-def]
    request: SynthesisRequest,
) -> tuple[tuple[SafeDiagnostic, ContentRuleCode], ...]:
    """Return the complete deterministic semantic diagnostics for one proposal."""

    return tuple(
        (violation.field_path, violation.rule_code)
        for violation in _proposal_content_rule_violations(proposal, request)
    )


def _safe_pydantic_diagnostics(
    error: ValidationError,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    field_paths: list[str] = []
    error_types: list[str] = []
    for detail in error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        location = detail.get("loc", ())
        field_paths.append(_safe_field_path(location if isinstance(location, tuple) else ()))
        raw_type = detail.get("type")
        error_types.append(_safe_diagnostic_token(raw_type, fallback="validation_error"))
    return _unique(field_paths) or ("$",), _unique(error_types) or ("validation_error",)


def _safe_field_path(location: tuple[object, ...]) -> str:
    if not location:
        return "$"
    parts = [_safe_diagnostic_token(part, fallback="field") for part in location]
    return ".".join(parts)


def _safe_diagnostic_token(value: object, *, fallback: str) -> str:
    text = str(value)
    cleaned = "".join(
        character
        for character in text
        if character.isalnum() or character in "_.$[]-"
    )
    return cleaned[:200] or fallback


def _unique(values) -> tuple:  # type: ignore[no-untyped-def]
    return tuple(sorted(set(values)))


def _out_of_allowlist_payload() -> str:
    return json.dumps(
        {
            "summary": "Intentionally invalid allowlist fixture.",
            "claims": [
                {
                    "text_template": "Unknown {{metric:metric-run-foreign-return}}.",
                    "claim_type": "quantitative",
                    "metric_ids": ["metric-run-foreign-return"],
                    "evidence_ids": [],
                    "uncertainty": None,
                }
            ],
            "limitations": ["Expected to fail before rendering."],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _fake_metadata(
    request: SynthesisRequest,
    status: Literal["success", "provider_error", "timeout"],
    error_type: str | None,
) -> ModelCallMetadata:
    return ModelCallMetadata(
        provider="fake",
        model_id="structured-fake-v1",
        prompt_version=request.prompt_version,
        status=status,
        latency_ms=0.0,
        response_id="response-fake-synthesis-v1" if status == "success" else None,
        input_tokens=None,
        output_tokens=None,
        retry_count=0,
        error_type=error_type,
        cost_estimate=None,
        currency=None,
        pricing_source_url=None,
        pricing_valid_on=None,
        cost_unavailable_reason="Deterministic fake has no provider billing.",
        response_origin="deterministic_fake",
    )
