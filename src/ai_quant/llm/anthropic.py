"""Anthropic structured client behind an injectable, testable transport."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel

from ai_quant.llm.base import (
    InvalidRequestReasonCode,
    LLMClientError,
    LLMProviderError,
    LLMSchemaError,
    LLMTimeoutError,
    PublicLLMErrorCode,
    PublicLLMFailure,
    StructuredOutputReasonCode,
    SynthesisRequest,
    SynthesisResult,
    validated_synthesis_result,
)
from ai_quant.llm.pricing import estimate_standard_token_cost
from ai_quant.model_calls import ModelCallMetadata, failed_model_call

_HTTP_ERROR_CODES: dict[int, PublicLLMErrorCode] = {
    400: "invalid_request_error",
    401: "authentication_error",
    402: "billing_error",
    403: "permission_error",
    404: "not_found_error",
    429: "rate_limit_error",
    500: "provider_api_error",
    504: "timeout_error",
    529: "overloaded_error",
}
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
ProviderStopReason = Literal[
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
    "pause_turn",
    "refusal",
    "model_context_window_exceeded",
]
_SAFE_STOP_REASONS: set[str] = {
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
    "pause_turn",
    "refusal",
    "model_context_window_exceeded",
}


@dataclass(frozen=True, slots=True)
class AnthropicTransportRequest:
    """Transport inputs; deliberately has no tools field."""

    model: str
    system_prompt: str = field(repr=False)
    user_prompt: str = field(repr=False)
    output_format: type[BaseModel]
    max_output_tokens: int
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class AnthropicTransportResponse:
    """Minimal provider response needed by the provider-neutral client."""

    payload_json: str | None
    response_id: str
    provider_request_id: str | None = None
    stop_reason: ProviderStopReason | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_count: int | None = None


class AnthropicTransport(Protocol):
    """Injectable transport used to keep tests offline."""

    def send(self, request: AnthropicTransportRequest) -> AnthropicTransportResponse:
        """Send one structured request."""


class AnthropicSDKTransport:
    """Thin adapter over the locked Anthropic SDK; construction performs no request."""

    def __init__(self, api_key: str) -> None:
        from anthropic import Anthropic, APITimeoutError, transform_schema

        self._client = Anthropic(api_key=api_key, max_retries=0)
        self._timeout_error_type = APITimeoutError
        self._transform_schema = transform_schema

    def send(self, request: AnthropicTransportRequest) -> AnthropicTransportResponse:
        timed_out = False
        try:
            response = self._client.messages.create(
                model=request.model,
                max_tokens=request.max_output_tokens,
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.user_prompt}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": self._transform_schema(
                            request.output_format.model_json_schema()
                        ),
                    }
                },
                timeout=request.timeout_seconds,
            )
        except self._timeout_error_type:
            timed_out = True
        if timed_out:
            raise TimeoutError("Anthropic transport timed out.") from None
        text_blocks = tuple(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
            and isinstance(getattr(block, "text", None), str)
        )
        payload_json = text_blocks[0] if len(text_blocks) == 1 else None
        return AnthropicTransportResponse(
            payload_json=payload_json,
            response_id=response.id,
            provider_request_id=_safe_request_id_value(
                getattr(response, "_request_id", None)
            ),
            stop_reason=_safe_stop_reason(getattr(response, "stop_reason", None)),
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
            retry_count=None,
        )


@dataclass(slots=True)
class AnthropicLLMClient:
    """One-call Anthropic implementation with strict output validation."""

    api_key: str = field(repr=False)
    model: str
    transport: AnthropicTransport | None = field(default=None, repr=False)
    response_origin: str = "live_provider"
    clock: Callable[[], float] = field(default=time.monotonic, repr=False)

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("Anthropic API key is required for the live client.")
        if not self.model.strip():
            raise ValueError("Anthropic model is required for the live client.")
        if self.response_origin not in {"mocked_provider", "live_provider"}:
            raise ValueError("Anthropic response_origin must be mocked_provider or live_provider.")
        if self.transport is None:
            self.transport = AnthropicSDKTransport(self.api_key)

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Send one no-tools request and validate the returned proposal and allowlists."""

        from ai_quant.trust.models import DraftProposal

        transport_request = AnthropicTransportRequest(
            model=self.model,
            system_prompt=_system_prompt(request),
            user_prompt=json.dumps(request.model_dump(mode="json"), sort_keys=True),
            output_format=DraftProposal,
            max_output_tokens=request.limits.max_output_tokens,
            timeout_seconds=request.limits.timeout_seconds,
        )
        started = self.clock()
        failure_fields: (
            tuple[
                PublicLLMErrorCode,
                InvalidRequestReasonCode | None,
                int | None,
                str | None,
            ]
            | None
        ) = None
        try:
            assert self.transport is not None
            response = self.transport.send(transport_request)
        except TimeoutError as exc:
            failure_fields = _safe_failure_fields(exc, force_timeout=True)
        except Exception as exc:
            failure_fields = _safe_failure_fields(exc)
        if failure_fields is not None:
            error_code, reason_code, http_status, request_id = failure_fields
            failure = PublicLLMFailure(
                error_code=error_code,
                reason_code=reason_code,
                http_status=http_status,
                request_id=request_id,
            )
            is_timeout = error_code == "timeout_error"
            metadata = self._metadata(
                request=request,
                status="timeout" if is_timeout else "provider_error",
                latency_ms=_elapsed_ms(started, self.clock()),
                error_type=error_code,
                http_status=http_status,
                provider_request_id=request_id,
            )
            if is_timeout:
                public_error: LLMProviderError | LLMTimeoutError = LLMTimeoutError(
                    "Anthropic structured synthesis timed out.",
                    metadata,
                    failure,
                )
            else:
                public_error = LLMProviderError(
                    "Anthropic structured synthesis failed.",
                    metadata,
                    failure,
                )
            raise public_error from None

        metadata = self._metadata(
            request=request,
            status="success",
            latency_ms=_elapsed_ms(started, self.clock()),
            response=response,
        )
        structured_reason = _response_failure_reason(response)
        if structured_reason is not None:
            failed = _failed_structured_metadata(metadata, structured_reason)
            failure = PublicLLMFailure(
                error_code="structured_output_invalid",
                reason_code=structured_reason,
                request_id=response.provider_request_id,
            )
            raise LLMSchemaError(
                "Anthropic structured synthesis returned no valid draft.",
                failed,
                failure,
            ) from None

        assert response.payload_json is not None
        unknown_structured_error = False
        try:
            return validated_synthesis_result(response.payload_json, request, metadata)
        except LLMClientError:
            raise
        except Exception:
            unknown_structured_error = True
        if unknown_structured_error:
            failed = _failed_structured_metadata(
                metadata, "unknown_structured_output_error"
            )
            failure = PublicLLMFailure(
                error_code="structured_output_invalid",
                reason_code="unknown_structured_output_error",
                request_id=response.provider_request_id,
            )
            raise LLMSchemaError(
                "Anthropic structured synthesis failed local validation.",
                failed,
                failure,
            ) from None
        raise AssertionError("Unreachable structured-output state.")

    def _metadata(
        self,
        *,
        request: SynthesisRequest,
        status: str,
        latency_ms: float,
        response: AnthropicTransportResponse | None = None,
        error_type: str | None = None,
        http_status: int | None = None,
        provider_request_id: str | None = None,
    ) -> ModelCallMetadata:
        pricing = estimate_standard_token_cost(
            model_id=self.model,
            input_tokens=None if response is None else response.input_tokens,
            output_tokens=None if response is None else response.output_tokens,
            call_succeeded=response is not None,
        )
        return ModelCallMetadata(
            provider="anthropic",
            model_id=self.model,
            prompt_version=request.prompt_version,
            status=status,
            latency_ms=latency_ms,
            response_id=(
                None
                if response is None
                else _safe_request_id_value(response.response_id)
            ),
            provider_request_id=(
                provider_request_id
                if provider_request_id is not None
                else None if response is None else response.provider_request_id
            ),
            http_status=http_status,
            input_tokens=None if response is None else response.input_tokens,
            output_tokens=None if response is None else response.output_tokens,
            total_tokens=(
                None
                if response is None
                or response.input_tokens is None
                or response.output_tokens is None
                else response.input_tokens + response.output_tokens
            ),
            stop_reason=None if response is None else response.stop_reason,
            retry_count=(
                0
                if response is None or response.retry_count is None
                else response.retry_count
            ),
            error_type=error_type,
            cost_estimate=pricing.cost_estimate,
            currency=pricing.currency,
            pricing_source_url=pricing.pricing_source_url,
            pricing_valid_on=pricing.pricing_consulted_on,
            pricing_snapshot_id=pricing.pricing_snapshot_id,
            cost_unavailable_reason=pricing.cost_unavailable_reason,
            response_origin=self.response_origin,  # type: ignore[arg-type]
        )


def _system_prompt(request: SynthesisRequest) -> str:
    rules = [
        "Return only the requested DraftProposal structure.",
        "Never create server IDs, validation results, assessments, official evidence, computed "
        "metrics, investment decisions or human decisions.",
        "Use exclusively the metric_ids and evidence_ids in this run's allowlists, and copy "
        "every referenced ID exactly.",
        "Never write a metric value directly in any LLM-authored field.",
        "Every declared metric_id must appear in text_template exactly as "
        "{{metric:<the exact allowlisted metric_id>}}.",
        "Every declared evidence_id must appear in text_template exactly as "
        "{{evidence:<the exact allowlisted evidence_id>}}.",
        "The generic placeholders {value}, {metric}, [value], [metric], {evidence} and "
        "[evidence] are forbidden.",
        "The summary must be qualitative and neutral, with no financial number, percentage or "
        "metric value in plain text and no placeholder.",
        "A historical metric cannot establish that risk is limited, low, safe or equivalent.",
        "Never state that two inputs cover the same period unless their explicit dates are equal "
        "in the supplied inputs.",
        "Present financial metrics and ESG evidence as separate observations without implying "
        "causality, correlation or analytical linkage.",
        "Never copy the literal internal status strings 'reported_zero' or 'not_applicable' "
        "into any generated field, even when those strings appear in authorized inputs.",
        "This literal-string ban applies to the summary, every claim text_template, every "
        "uncertainty and every limitation.",
        "When an authorized source explicitly reports a zero value, describe it as 'a zero "
        "value explicitly reported by the source, not missing data' or equivalent public "
        "language; never copy its internal status token.",
        "When an authorized source says a method does not apply to one field, describe it as "
        "'the method does not apply to that specific field' or equivalent public language; "
        "never copy its internal status token.",
    ]
    examples = [
        (
            'Valid metric claim example: {"text_template":"Historical metric '
            f'{{{{metric:{metric_id}}}}}.",'
            '"claim_type":"quantitative","metric_ids":['
            f'"{metric_id}"],"evidence_ids":[]}}'
        )
        for metric_id in request.allowed_metric_ids
    ]
    examples.extend(
        (
            'Valid evidence claim example: {"text_template":"Separately, official evidence '
            f'{{{{evidence:{evidence_id}}}}}.",'
            '"claim_type":"evidence","metric_ids":[],"evidence_ids":['
            f'"{evidence_id}"]}}'
        )
        for evidence_id in request.allowed_evidence_ids
    )
    for evidence in request.evidence:
        normalized_excerpt = evidence.excerpt.casefold()
        if "reported_zero" in normalized_excerpt:
            examples.append(
                'Valid public-status example: {"text_template":"Separately, official '
                f'evidence {{{{evidence:{evidence.evidence_id}}}}} states a zero value '
                'explicitly reported by the source, not missing data.","claim_type":"evidence",'
                f'"metric_ids":[],"evidence_ids":["{evidence.evidence_id}"]}}'
            )
        if "not_applicable" in normalized_excerpt:
            examples.append(
                'Valid public-status example: {"text_template":"For official evidence '
                f'{{{{evidence:{evidence.evidence_id}}}}}, the method does not apply to that '
                'specific field.","claim_type":"evidence","metric_ids":[],"evidence_ids":['
                f'"{evidence.evidence_id}"]}}'
            )
    if not examples:
        examples.append("This run has no allowlisted IDs; do not emit any reference placeholder.")
    return "\n".join((*rules, *examples))


def _elapsed_ms(started: float, ended: float) -> float:
    return max(0.0, (ended - started) * 1_000)


def _response_failure_reason(
    response: AnthropicTransportResponse,
) -> StructuredOutputReasonCode | None:
    if response.stop_reason == "max_tokens":
        return "max_tokens_exhausted"
    if response.stop_reason == "refusal":
        return "provider_refusal"
    if response.payload_json is None:
        return "missing_parsed_output"
    return None


def _failed_structured_metadata(
    metadata: ModelCallMetadata,
    reason_code: StructuredOutputReasonCode,
) -> ModelCallMetadata:
    return failed_model_call(
        metadata,
        status="schema_error",
        error_type=reason_code,
    )


def _safe_stop_reason(value: object) -> ProviderStopReason | None:
    if isinstance(value, str) and value in _SAFE_STOP_REASONS:
        return value  # type: ignore[return-value]
    return None


def _safe_request_id_value(value: object) -> str | None:
    if isinstance(value, str) and _SAFE_REQUEST_ID.fullmatch(value):
        return value
    return None


def _safe_failure_fields(
    error: Exception,
    *,
    force_timeout: bool = False,
) -> tuple[
    PublicLLMErrorCode,
    InvalidRequestReasonCode | None,
    int | None,
    str | None,
]:
    """Extract only allowlisted primitive diagnostics from a raw provider error."""

    status = _safe_http_status(error)
    request_id = _safe_request_id(error)
    class_name = type(error).__name__.lower()
    if force_timeout or "timeout" in class_name:
        return "timeout_error", None, status, request_id
    if status == 400:
        return "invalid_request_error", _safe_invalid_request_reason(error), status, request_id
    if status in _HTTP_ERROR_CODES:
        return _HTTP_ERROR_CODES[status], None, status, request_id
    if status is not None and 500 <= status <= 599:
        return "provider_api_error", None, status, request_id
    if isinstance(error, ConnectionError) or "connectionerror" in class_name:
        return "connection_error", None, status, request_id
    return "unknown_provider_error", None, status, request_id


def _safe_invalid_request_reason(error: Exception) -> InvalidRequestReasonCode:
    """Classify a raw 400 briefly, retaining only one allowlisted reason code."""

    message = _raw_provider_message(error).casefold()
    invalid_markers = (
        "invalid",
        "unsupported",
        "not supported",
        "not allowed",
        "not permitted",
        "cannot",
        "must not",
        "may only",
        "unknown",
        "unrecognized",
        "extra inputs",
        "field required",
        "missing",
    )

    def rejected(*parameter_names: str) -> bool:
        return any(name in message for name in parameter_names) and any(
            marker in message for marker in invalid_markers
        )

    if rejected("temperature", "top_p", "top-p", "top_k", "top-k"):
        return "unsupported_sampling_parameter"
    if rejected("thinking", "budget_tokens", "budget tokens"):
        return "unsupported_thinking_configuration"
    schema_is_mentioned = any(
        name in message
        for name in (
            "output schema",
            "json schema",
            "output_config",
            "structured output",
            "schema",
        )
    )
    if schema_is_mentioned and any(
        marker in message
        for marker in ("too complex", "complexity", "exceeds the maximum", "too many")
    ):
        return "schema_too_complex"
    if schema_is_mentioned and any(marker in message for marker in invalid_markers):
        return "invalid_output_schema"
    if rejected("max_tokens", "max tokens"):
        return "invalid_max_tokens"
    if rejected("messages parameter", "messages"):
        return "invalid_messages_parameter"
    if rejected("system parameter", "system"):
        return "invalid_system_parameter"
    if rejected("model parameter", "model"):
        return "invalid_model_parameter"
    return "other_invalid_request"


def _raw_provider_message(error: Exception) -> str:
    """Read raw provider text transiently without returning or retaining its source object."""

    fragments: list[str] = []
    try:
        fragments.extend(argument for argument in error.args if isinstance(argument, str))
    except Exception:
        pass
    try:
        message = getattr(error, "message", None)
    except Exception:
        message = None
    if isinstance(message, str):
        fragments.append(message)
    try:
        body = getattr(error, "body", None)
    except Exception:
        body = None
    fragments.extend(_provider_message_values(body))
    return " ".join(fragments)


def _provider_message_values(value: object, *, depth: int = 0) -> list[str]:
    if depth > 4 or not isinstance(value, dict):
        return []
    messages: list[str] = []
    for key, child in value.items():
        if key == "message" and isinstance(child, str):
            messages.append(child)
        elif key in {"error", "details"}:
            messages.extend(_provider_message_values(child, depth=depth + 1))
    return messages


def _safe_http_status(error: Exception) -> int | None:
    try:
        value = getattr(error, "status_code", None)
    except Exception:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
        return value
    return None


def _safe_request_id(error: Exception) -> str | None:
    try:
        value = getattr(error, "request_id", None)
    except Exception:
        return None
    if isinstance(value, str) and _SAFE_REQUEST_ID.fullmatch(value):
        return value
    return None
