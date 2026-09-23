"""Offline transport tests for the Anthropic structured client."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from ai_quant.llm import (
    AnthropicLLMClient,
    AnthropicSDKTransport,
    AnthropicTransportRequest,
    AnthropicTransportResponse,
    LLMAllowlistError,
    LLMClientError,
    LLMEvidenceInput,
    LLMMetricInput,
    LLMProviderError,
    LLMSchemaError,
    LLMTimeoutError,
    SynthesisLimits,
    SynthesisRequest,
)
from ai_quant.trust.models import DraftProposal


@dataclass
class MockTransport:
    response: AnthropicTransportResponse | None = None
    error: Exception | None = None
    request: AnthropicTransportRequest | None = None
    calls: int = 0

    def send(self, request: AnthropicTransportRequest) -> AnthropicTransportResponse:
        self.calls += 1
        self.request = request
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def test_anthropic_mock_transport_receives_timeout_no_tools_and_returns_metadata() -> None:
    transport = MockTransport(
        response=AnthropicTransportResponse(
            payload_json=_payload(),
            response_id="msg_mock_1",
            input_tokens=120,
            output_tokens=45,
            retry_count=1,
        )
    )
    ticks = iter((10.0, 10.125))
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="placeholder-model-id",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: next(ticks),
    )

    result = client.synthesize(
        _request(
            evidence_excerpt=(
                "Coverage status reported_zero. Scope 2 method not_applicable."
            )
        )
    )

    assert transport.calls == 1
    assert transport.request is not None
    assert transport.request.timeout_seconds == 7.5
    assert not hasattr(transport.request, "tools")
    prompt = transport.request.system_prompt
    assert set(re.findall(r"(?:metric|evidence)-[a-z0-9-]+", prompt)) == {
        "metric-run-test-return",
        "evidence-run-test-source",
    }
    assert "{{metric:metric-run-test-return}}" in prompt
    assert "{{evidence:evidence-run-test-source}}" in prompt
    assert "{value}" in prompt and "[value]" in prompt
    assert "qualitative and neutral" in prompt
    assert "limited, low, safe" in prompt
    assert "same period" in prompt
    assert "separate observations" in prompt
    assert (
        "Never copy the literal internal status strings 'reported_zero' or "
        "'not_applicable' into any generated field"
    ) in prompt
    assert (
        "This literal-string ban applies to the summary, every claim text_template, every "
        "uncertainty and every limitation."
    ) in prompt
    assert "a zero value explicitly reported by the source, not missing data" in prompt
    assert "the method does not apply to that specific field" in prompt
    assert prompt.count("Valid public-status example:") == 2
    assert result.metadata.status == "success"
    assert result.metadata.prompt_version == "trust-synthesis-v3"
    assert result.metadata.response_origin == "mocked_provider"
    assert result.metadata.input_tokens == 120
    assert result.metadata.output_tokens == 45
    assert result.metadata.retry_count == 1
    assert result.metadata.latency_ms == pytest.approx(125)
    assert result.metadata.cost_estimate is None
    assert result.metadata.cost_unavailable_reason == "pricing_unavailable_for_model"
    assert transport.calls == 1
    assert json.loads(result.payload_json)["summary"] == (
        "This report presents historical run metrics and a separate official evidence record. "
        "Each is reported independently, and no temporal, causal, predictive or investment "
        "relationship between them is asserted."
    )
    assert "placeholder-test-key" not in repr(client)


def test_sdk_transport_disables_automatic_network_retries(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    construction: dict[str, object] = {}

    def fake_anthropic(**kwargs):  # type: ignore[no-untyped-def]
        construction.update(kwargs)
        return object()

    monkeypatch.setattr("anthropic.Anthropic", fake_anthropic)

    AnthropicSDKTransport("placeholder-test-key")

    assert construction["api_key"] == "placeholder-test-key"
    assert construction["max_retries"] == 0


def test_sdk_transport_sonnet_5_uses_adaptive_defaults_offline(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import httpx
    from anthropic import Anthropic as RealAnthropic

    captured: dict[str, Any] = {}
    construction: dict[str, object] = {}
    http_calls = 0

    def record_request(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        captured["body"] = json.loads(request.content)
        captured["header_names"] = {name.lower() for name in request.headers}
        captured["timeout"] = request.extensions["timeout"]
        return httpx.Response(
            200,
            request=request,
            headers={"request-id": "req_local_mock"},
            json={
                "id": "msg_local_mock",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5",
                "content": [{"type": "text", "text": _payload()}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 120, "output_tokens": 45},
            },
        )

    def fake_anthropic(**kwargs):  # type: ignore[no-untyped-def]
        construction.update(kwargs)
        return RealAnthropic(
            api_key=str(kwargs["api_key"]),
            max_retries=int(kwargs["max_retries"]),
            http_client=httpx.Client(transport=httpx.MockTransport(record_request)),
        )

    monkeypatch.setattr("anthropic.Anthropic", fake_anthropic)
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="claude-sonnet-5",
        transport=AnthropicSDKTransport("placeholder-test-key"),
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    result = client.synthesize(_request())

    body = captured["body"]
    legacy_body = {**body, "temperature": 0}
    assert "temperature" in legacy_body
    assert set(body) == {"max_tokens", "messages", "model", "output_config", "system"}
    assert body["model"] == "claude-sonnet-5"
    assert body["max_tokens"] == 1200
    assert "temperature" not in body
    assert "top_p" not in body
    assert "top_k" not in body
    assert "thinking" not in body
    assert "tools" not in body
    assert "citations" not in body
    assert "output_config" in body
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert "anthropic-beta" not in captured["header_names"]
    assert captured["timeout"]["read"] == 7.5
    assert construction["max_retries"] == 0
    assert http_calls == 1
    assert result.metadata.provider_request_id == "req_local_mock"
    assert result.metadata.stop_reason == "end_turn"
    assert result.metadata.total_tokens == 165
    assert json.loads(result.payload_json)["claims"][0]["metric_ids"] == [
        "metric-run-test-return"
    ]


def test_sdk_parse_raises_before_returning_billable_response_metadata() -> None:
    import httpx
    from anthropic import Anthropic

    http_calls = 0

    def invalid_structured_response(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        return httpx.Response(
            200,
            request=request,
            headers={"request-id": "req_parse_metadata_lost"},
            json={
                "id": "msg_parse_metadata_lost",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5",
                "content": [{"type": "text", "text": '{"summary":"truncated"'}],
                "stop_reason": "max_tokens",
                "stop_sequence": None,
                "usage": {"input_tokens": 123, "output_tokens": 1200},
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(invalid_structured_response)
    ) as http_client:
        client = Anthropic(
            api_key="placeholder-test-key",
            max_retries=0,
            http_client=http_client,
        )
        with pytest.raises(ValidationError) as caught:
            client.messages.parse(
                model="claude-sonnet-5",
                max_tokens=1_200,
                system="redacted",
                messages=[{"role": "user", "content": "redacted"}],
                output_format=DraftProposal,
                timeout=7.5,
            )

    assert http_calls == 1
    assert not hasattr(caught.value, "stop_reason")
    assert not hasattr(caught.value, "usage")
    assert not hasattr(caught.value, "request_id")


@pytest.mark.parametrize(
    ("stop_reason", "content", "expected_reason"),
    (
        (
            "max_tokens",
            [{"type": "text", "text": '{"summary":"truncated"'}],
            "max_tokens_exhausted",
        ),
        ("refusal", [], "provider_refusal"),
    ),
)
def test_sdk_create_retains_metadata_for_structured_failures(
    monkeypatch,
    stop_reason: str,
    content: list[dict[str, str]],
    expected_reason: str,
) -> None:  # type: ignore[no-untyped-def]
    import httpx
    from anthropic import Anthropic as RealAnthropic

    http_calls = 0

    def structured_failure(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        return httpx.Response(
            200,
            request=request,
            headers={"request-id": "req_sdk_structured_failure"},
            json={
                "id": "msg_sdk_structured_failure",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5",
                "content": content,
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 123, "output_tokens": 1200},
            },
        )

    def fake_anthropic(**kwargs):  # type: ignore[no-untyped-def]
        return RealAnthropic(
            api_key=str(kwargs["api_key"]),
            max_retries=int(kwargs["max_retries"]),
            http_client=httpx.Client(transport=httpx.MockTransport(structured_failure)),
        )

    monkeypatch.setattr("anthropic.Anthropic", fake_anthropic)
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="claude-sonnet-5",
        transport=AnthropicSDKTransport("placeholder-test-key"),
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    with pytest.raises(LLMSchemaError) as caught:
        client.synthesize(_request())

    error = caught.value
    assert error.reason_code == expected_reason
    assert error.request_id == "req_sdk_structured_failure"
    assert error.metadata.provider_request_id == "req_sdk_structured_failure"
    assert error.metadata.stop_reason == stop_reason
    assert error.metadata.input_tokens == 123
    assert error.metadata.output_tokens == 1200
    assert error.metadata.total_tokens == 1323
    assert error.metadata.cost_estimate == Decimal("0.012246")
    assert error.metadata.retry_count == 0
    assert error.__cause__ is None
    assert error.__context__ is None
    assert http_calls == 1


def test_anthropic_missing_tokens_are_preserved_as_unknown() -> None:
    transport = MockTransport(
        response=AnthropicTransportResponse(
            payload_json=_payload(),
            response_id="msg_mock_2",
        )
    )
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="placeholder-model-id",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    metadata = client.synthesize(_request()).metadata

    assert metadata.input_tokens is None
    assert metadata.output_tokens is None
    assert metadata.retry_count == 0
    assert metadata.cost_estimate is None
    assert metadata.cost_unavailable_reason == "pricing_unavailable_for_model"


def test_anthropic_mock_transport_retains_pydantic_and_allowlist_validation() -> None:
    payload = json.loads(_payload())
    payload["claims"][0]["metric_ids"] = ["metric-outside-run"]
    transport = MockTransport(
        response=AnthropicTransportResponse(
            payload_json=json.dumps(payload),
            response_id="msg_outside_allowlist",
        )
    )
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    with pytest.raises(LLMAllowlistError, match="outside the run allowlist"):
        client.synthesize(_request())

    assert transport.calls == 1


def test_known_model_records_exact_cost_and_pricing_provenance() -> None:
    transport = MockTransport(
        response=AnthropicTransportResponse(
            payload_json=_payload(),
            response_id="msg_priced",
            input_tokens=120,
            output_tokens=45,
            retry_count=0,
        )
    )
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    metadata = client.synthesize(_request()).metadata

    assert metadata.cost_estimate == Decimal("0.000690")
    assert metadata.currency == "USD"
    assert metadata.pricing_snapshot_id == (
        "anthropic-standard-token-pricing-2026-09-23-v1"
    )
    assert metadata.pricing_source_url == (
        "https://platform.claude.com/docs/en/models/overview"
    )
    assert metadata.pricing_valid_on == date(2026, 9, 23)
    assert metadata.cost_unavailable_reason is None


def test_known_model_without_tokens_uses_stable_reason() -> None:
    transport = MockTransport(
        response=AnthropicTransportResponse(
            payload_json=_payload(),
            response_id="msg_no_usage",
        )
    )
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    metadata = client.synthesize(_request()).metadata

    assert metadata.cost_estimate is None
    assert metadata.cost_unavailable_reason == "token_usage_unavailable"
    assert metadata.pricing_valid_on == date(2026, 9, 23)


@pytest.mark.parametrize(
    ("transport_error", "expected_error", "status"),
    (
        (TimeoutError("secret provider detail"), LLMTimeoutError, "timeout"),
        (RuntimeError("secret provider detail"), LLMProviderError, "provider_error"),
    ),
)
def test_anthropic_errors_are_clean_and_retain_metadata(
    transport_error,
    expected_error,
    status,
) -> None:  # type: ignore[no-untyped-def]
    transport = MockTransport(error=transport_error)
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="placeholder-model-id",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    with pytest.raises(expected_error) as caught:
        client.synthesize(_request())

    assert str(caught.value) in {
        "Anthropic structured synthesis timed out.",
        "Anthropic structured synthesis failed.",
    }
    assert "secret provider detail" not in str(caught.value)
    assert caught.value.metadata.status == status
    assert caught.value.metadata.response_id is None
    assert caught.value.metadata.cost_estimate is None
    assert caught.value.metadata.cost_unavailable_reason == "model_call_failed"
    assert caught.value.metadata.retry_count == 0
    assert caught.value.error_code in {"timeout_error", "unknown_provider_error"}
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_public_errors_detach_raw_provider_output_prompt_key_and_logs(caplog) -> None:  # type: ignore[no-untyped-def]
    markers = {
        "RAW_PROVIDER_SECRET_7f21",
        "RAW_OUTPUT_SECRET_9a42",
        "PROMPT_SECRET_3d88",
        "KEY_SECRET_5c10",
    }
    request = _request(context="Authorized PROMPT_SECRET_3d88 context.")
    failures = (
        (
            MockTransport(error=RuntimeError("RAW_PROVIDER_SECRET_7f21")),
            LLMProviderError,
            "unknown_provider_error",
        ),
        (
            MockTransport(
                response=AnthropicTransportResponse(
                    payload_json=(
                        '{"summary":"RAW_OUTPUT_SECRET_9a42","claims":[],'
                        '"limitations":[],"unexpected":"RAW_OUTPUT_SECRET_9a42"}'
                    ),
                    response_id="msg_invalid",
                )
            ),
            LLMSchemaError,
            "structured_output_invalid",
        ),
    )

    for transport, expected_error, expected_code in failures:
        client = AnthropicLLMClient(
            api_key="KEY_SECRET_5c10",
            model="placeholder-model-id",
            transport=transport,
            response_origin="mocked_provider",
            clock=lambda: 1.0,
        )
        with pytest.raises(expected_error) as caught:
            client.synthesize(request)
        exposed = _public_exception_values(caught.value)
        assert caught.value.error_code == expected_code
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        for marker in markers:
            assert marker not in exposed
            assert marker not in caplog.text


@pytest.mark.parametrize(
    ("http_status", "expected_code"),
    (
        (400, "invalid_request_error"),
        (401, "authentication_error"),
        (402, "billing_error"),
        (403, "permission_error"),
        (404, "not_found_error"),
        (429, "rate_limit_error"),
        (500, "provider_api_error"),
        (504, "timeout_error"),
        (529, "overloaded_error"),
    ),
)
def test_anthropic_http_failures_expose_only_safe_classification(
    http_status: int,
    expected_code: str,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    request_id = f"req_safe_{http_status}"
    raw_error = MockProviderHTTPError(http_status=http_status, request_id=request_id)
    client = AnthropicLLMClient(
        api_key="KEY_SECRET_HTTP_4f10",
        model="claude-sonnet-5",
        transport=MockTransport(error=raw_error),
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    with pytest.raises(LLMClientError) as caught:
        client.synthesize(_request(context="PROMPT_SECRET_HTTP_6a22"))

    error = caught.value
    exposed = _public_exception_values(error)
    assert error.error_code == expected_code
    assert error.http_status == http_status
    assert error.request_id == request_id
    assert error.failure.status == "failed"
    assert error.metadata.http_status == http_status
    assert error.metadata.provider_request_id == request_id
    assert error.metadata.error_type == expected_code
    assert error.metadata.retry_count == 0
    assert error.reason_code == ("other_invalid_request" if http_status == 400 else None)
    assert error.__cause__ is None
    assert error.__context__ is None
    for marker in (
        "RAW_PROVIDER_MESSAGE_1a11",
        "RAW_HTTP_BODY_2b22",
        "RAW_HEADER_SECRET_3c33",
        "PROMPT_SECRET_HTTP_6a22",
        "KEY_SECRET_HTTP_4f10",
    ):
        assert marker not in exposed
        assert marker not in caplog.text


@pytest.mark.parametrize(
    ("provider_message", "expected_reason"),
    (
        (
            "The temperature parameter is not supported for this model.",
            "unsupported_sampling_parameter",
        ),
        (
            "thinking with budget_tokens is not permitted.",
            "unsupported_thinking_configuration",
        ),
        (
            "output_config JSON schema is invalid.",
            "invalid_output_schema",
        ),
        (
            "The output schema is too complex.",
            "schema_too_complex",
        ),
        ("max_tokens is invalid.", "invalid_max_tokens"),
        ("The model parameter is invalid.", "invalid_model_parameter"),
        ("The messages parameter is invalid.", "invalid_messages_parameter"),
        ("The system parameter is invalid.", "invalid_system_parameter"),
        ("The request cannot be processed.", "other_invalid_request"),
    ),
)
def test_anthropic_http_400_reason_is_allowlisted_and_raw_message_is_detached(
    provider_message: str,
    expected_reason: str,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    sensitive_marker = f"RAW_REASON_SECRET_{expected_reason}"
    raw_error = MockProviderHTTPError(
        http_status=400,
        request_id="req_safe_reason_400",
        message=f"{provider_message} {sensitive_marker}",
    )
    transport = MockTransport(error=raw_error)
    client = AnthropicLLMClient(
        api_key="KEY_SECRET_REASON_4c20",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    with pytest.raises(LLMProviderError) as caught:
        client.synthesize(_request(context="PROMPT_SECRET_REASON_5d30"))

    error = caught.value
    exposed = _public_exception_values(error)
    assert error.error_code == "invalid_request_error"
    assert error.reason_code == expected_reason
    assert error.failure.reason_code == expected_reason
    assert error.metadata.error_type == "invalid_request_error"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert transport.calls == 1
    assert sensitive_marker not in exposed
    assert sensitive_marker not in caplog.text
    assert "PROMPT_SECRET_REASON_5d30" not in exposed
    assert "KEY_SECRET_REASON_4c20" not in exposed


def test_anthropic_connection_failure_has_no_fabricated_http_fields(caplog) -> None:  # type: ignore[no-untyped-def]
    client = AnthropicLLMClient(
        api_key="KEY_SECRET_CONNECTION_7d44",
        model="claude-sonnet-5",
        transport=MockTransport(error=ConnectionError("RAW_CONNECTION_MESSAGE_8e55")),
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    with pytest.raises(LLMProviderError) as caught:
        client.synthesize(_request(context="PROMPT_SECRET_CONNECTION_9f66"))

    error = caught.value
    exposed = _public_exception_values(error)
    assert error.error_code == "connection_error"
    assert error.http_status is None
    assert error.request_id is None
    assert error.metadata.retry_count == 0
    assert error.__cause__ is None
    assert error.__context__ is None
    for marker in (
        "RAW_CONNECTION_MESSAGE_8e55",
        "PROMPT_SECRET_CONNECTION_9f66",
        "KEY_SECRET_CONNECTION_7d44",
    ):
        assert marker not in exposed
        assert marker not in caplog.text


def test_anthropic_client_requires_explicit_key_and_model() -> None:
    with pytest.raises(ValueError, match="API key is required"):
        AnthropicLLMClient(api_key=" ", model="placeholder", transport=MockTransport())
    with pytest.raises(ValueError, match="model is required"):
        AnthropicLLMClient(
            api_key="placeholder-test-key",
            model=" ",
            transport=MockTransport(),
        )


def _request(
    *,
    context: str = "Authorized context.",
    evidence_excerpt: str = "Official test excerpt.",
) -> SynthesisRequest:
    metric = LLMMetricInput(
        metric_id="metric-run-test-return",
        run_id="run-test",
        metric_name="return",
        value=0.1,
        unit="decimal return",
    )
    evidence = LLMEvidenceInput(
        evidence_id="evidence-run-test-source",
        run_id="run-test",
        excerpt=evidence_excerpt,
        provenance_label="official_corpus_passage",
    )
    return SynthesisRequest(
        run_id="run-test",
        prompt_version="trust-synthesis-v3",
        context=context,
        metrics=(metric,),
        evidence=(evidence,),
        allowed_metric_ids=(metric.metric_id,),
        allowed_evidence_ids=(evidence.evidence_id,),
        limits=SynthesisLimits(timeout_seconds=7.5),
    )


class MockProviderHTTPError(Exception):
    """Raw provider-shaped error carrying deliberately sensitive test attributes."""

    def __init__(
        self,
        *,
        http_status: int,
        request_id: str,
        message: str = "RAW_PROVIDER_MESSAGE_1a11",
    ) -> None:
        super().__init__(message)
        self.status_code = http_status
        self.request_id = request_id
        self.body = "RAW_HTTP_BODY_2b22"
        self.headers = {"authorization": "RAW_HEADER_SECRET_3c33"}


def _payload() -> str:
    return json.dumps(
        {
            "summary": "Mocked provider proposal.",
            "claims": [
                {
                    "text_template": "Return {{metric:metric-run-test-return}}.",
                    "claim_type": "quantitative",
                    "metric_ids": ["metric-run-test-return"],
                    "evidence_ids": [],
                    "uncertainty": None,
                }
            ],
            "limitations": ["Mocked transport only."],
        }
    )


def _public_exception_values(error: BaseException) -> str:
    """Traverse only public exception links, args and exposed metadata."""

    seen: set[int] = set()
    values: list[str] = []

    def visit(value: Any) -> None:
        if value is None or id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, BaseException):
            values.append(type(value).__name__)
            for argument in value.args:
                visit(argument)
            visit(value.__cause__)
            visit(value.__context__)
            for name, public_value in vars(value).items():
                if not name.startswith("_"):
                    visit(public_value)
        elif isinstance(value, BaseModel):
            visit(value.model_dump())
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(key)
                visit(item)
        elif isinstance(value, (tuple, list, set, frozenset)):
            for item in value:
                visit(item)
        else:
            values.append(str(value))

    visit(error)
    return "\n".join(values)
