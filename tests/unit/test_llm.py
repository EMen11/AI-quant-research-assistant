"""Tests for the canonical structured LLM boundary and deterministic fake."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_quant.config import Settings
from ai_quant.llm import (
    FakeLLM,
    FakeLLMClient,
    LLMAllowlistError,
    LLMEvidenceInput,
    LLMMetricInput,
    LLMProviderError,
    LLMSchemaError,
    LLMTimeoutError,
    SynthesisRequest,
    client_from_settings,
)


def test_fake_llm_is_deterministic_and_counts_legacy_calls() -> None:
    client = FakeLLM("known response")

    first = client.complete("first prompt")
    second = client.complete("second prompt")

    assert first == second
    assert first.text == "known response"
    assert first.provider == "fake"
    assert client.call_count == 2


def test_fake_llm_rejects_empty_legacy_prompt() -> None:
    client = FakeLLM()

    with pytest.raises(ValueError, match="prompt must not be empty"):
        client.complete("   ")


def test_fake_structured_success_is_deterministic_single_call_and_valid() -> None:
    first_client = FakeLLMClient()
    second_client = FakeLLMClient()

    first = first_client.synthesize(_request())
    second = second_client.synthesize(_request())

    assert first == second
    assert first_client.call_count == 1
    assert first.metadata.status == "success"
    assert first.metadata.response_origin == "deterministic_fake"
    assert first.metadata.input_tokens is None
    assert first.metadata.cost_estimate is None
    assert first.metadata.cost_unavailable_reason


def test_fake_rejects_extra_output_fields_as_schema_error() -> None:
    payload = json.loads(_valid_payload())
    payload["claims"][0]["untrusted_extra"] = True
    client = FakeLLMClient(payload_json=json.dumps(payload))

    with pytest.raises(LLMSchemaError) as caught:
        client.synthesize(_request())

    assert caught.value.metadata.status == "schema_error"
    assert caught.value.metadata.error_type == "DraftSchemaValidationError"


def test_fake_rejects_unknown_and_cross_run_output_ids() -> None:
    client = FakeLLMClient(mode="out_of_allowlist")

    with pytest.raises(LLMAllowlistError, match="outside the run allowlist") as caught:
        client.synthesize(_request())

    assert caught.value.metadata.status == "allowlist_error"
    assert caught.value.metadata.error_type == "OutputAllowlistViolation"
    assert client.call_count == 1


@pytest.mark.parametrize(
    ("mutation", "expected_error", "expected_error_type"),
    (
        ("generic_value", LLMSchemaError, "DraftContentValidationError"),
        ("formatted_return", LLMSchemaError, "DraftContentValidationError"),
        ("formatted_drawdown", LLMSchemaError, "DraftContentValidationError"),
        ("raw_metric_value", LLMSchemaError, "DraftContentValidationError"),
        ("metric_without_placeholder", LLMSchemaError, "DraftContentValidationError"),
        ("evidence_without_placeholder", LLMSchemaError, "DraftContentValidationError"),
        ("placeholder_without_reference", LLMSchemaError, "DraftContentValidationError"),
        ("unknown_placeholder", LLMAllowlistError, "OutputAllowlistViolation"),
        ("cross_run_placeholder", LLMAllowlistError, "OutputAllowlistViolation"),
        ("summary_placeholder", LLMSchemaError, "DraftContentValidationError"),
        ("limited_downside_risk", LLMSchemaError, "DraftContentValidationError"),
        ("same_period", LLMSchemaError, "DraftContentValidationError"),
        ("implicit_causality", LLMSchemaError, "DraftContentValidationError"),
        ("internal_status_tokens", LLMSchemaError, "DraftContentValidationError"),
        ("unsupported_evidence_number", LLMSchemaError, "DraftContentValidationError"),
    ),
)
def test_live_capture_regressions_are_blocked_deterministically(
    mutation: str,
    expected_error: type[Exception],
    expected_error_type: str,
) -> None:
    payload = json.loads(_live_like_payload())
    first_metric = payload["claims"][0]
    evidence_claim = payload["claims"][2]
    if mutation == "generic_value":
        first_metric["text_template"] = "The cumulative return is {value}."
    elif mutation == "formatted_return":
        first_metric["uncertainty"] = "The strategy returned 6.98%."
    elif mutation == "formatted_drawdown":
        payload["claims"][1]["uncertainty"] = "The maximum drawdown was 0.83%."
    elif mutation == "raw_metric_value":
        first_metric["uncertainty"] = "The raw return was 0.06982119406430298."
    elif mutation == "metric_without_placeholder":
        first_metric["text_template"] = "The historical cumulative return is available."
    elif mutation == "evidence_without_placeholder":
        evidence_claim["text_template"] = "The official evidence is available."
    elif mutation == "placeholder_without_reference":
        first_metric["metric_ids"] = []
        first_metric["claim_type"] = "limitation"
    elif mutation == "unknown_placeholder":
        first_metric["text_template"] = (
            "Unknown {{metric:metric-run-demo-valid-unknown}}."
        )
        first_metric["metric_ids"] = []
        first_metric["claim_type"] = "limitation"
    elif mutation == "cross_run_placeholder":
        first_metric["text_template"] = "Foreign {{metric:metric-run-foreign-return}}."
        first_metric["metric_ids"] = []
        first_metric["claim_type"] = "limitation"
    elif mutation == "summary_placeholder":
        payload["limitations"][0] = (
            "Summary {{metric:metric-run-demo-valid-cumulative-return}}."
        )
    elif mutation == "limited_downside_risk":
        payload["claims"][1]["text_template"] += " This indicates limited downside risk."
    elif mutation == "same_period":
        payload["limitations"][0] = (
            "Financial and ESG observations cover the same period."
        )
    elif mutation == "implicit_causality":
        payload["limitations"][0] = (
            "The financial result was driven by the ESG observation."
        )
    elif mutation == "internal_status_tokens":
        evidence_claim["uncertainty"] = "reported_zero and not_applicable."
    elif mutation == "unsupported_evidence_number":
        evidence_claim["text_template"] += " The source reports 999."

    client = FakeLLMClient(payload_json=json.dumps(payload))
    with pytest.raises(expected_error) as caught:
        client.synthesize(_live_like_request())

    assert caught.value.metadata.error_type == expected_error_type
    assert client.call_count == 1


@pytest.mark.parametrize("token", ("reported_zero", "not_applicable"))
@pytest.mark.parametrize(
    ("category", "expected_path"),
    (
        ("claim_text", "claims.2.text_template"),
        ("uncertainty", "claims.2.uncertainty"),
        ("limitation", "limitations.0"),
    ),
)
def test_internal_status_tokens_are_rejected_in_every_llm_owned_prose_category(
    token: str,
    category: str,
    expected_path: str,
) -> None:
    payload = json.loads(_live_like_payload())
    evidence_claim = payload["claims"][2]
    if category == "claim_text":
        evidence_claim["text_template"] += f" Internal status {token}."
    elif category == "uncertainty":
        evidence_claim["uncertainty"] = f"Internal status {token}."
    else:
        payload["limitations"][0] = f"Internal status {token}."

    client = FakeLLMClient(payload_json=json.dumps(payload))
    with pytest.raises(LLMSchemaError) as caught:
        client.synthesize(_live_like_request())

    assert caught.value.failure.content_rule_codes == ("internal_status_token",)
    assert caught.value.failure.validation_field_paths == (expected_path,)
    assert client.call_count == 1


def test_untrusted_summary_is_replaced_before_final_semantic_validation() -> None:
    payload = json.loads(_live_like_payload())
    rejected_summary = (
        "reported_zero {{metric:metric-run-demo-valid-cumulative-return}} at 6.98% was "
        "driven by the ESG observation in the same period."
    )
    payload["summary"] = rejected_summary

    result = FakeLLMClient(payload_json=json.dumps(payload)).synthesize(
        _live_like_request()
    )

    assert rejected_summary not in result.payload_json
    assert (
        json.loads(result.payload_json)["summary"]
        == "This report presents historical run metrics and a separate official evidence "
        "record. Each is reported independently, and no temporal, causal, predictive or "
        "investment relationship between them is asserted."
    )


def test_public_status_rewordings_are_accepted_in_every_prose_category() -> None:
    payload = json.loads(_live_like_payload())
    payload["summary"] = (
        "The source explicitly reports a zero value rather than missing data, while a method "
        "does not apply to one specific field."
    )
    payload["claims"][2]["text_template"] = (
        "Separately, official evidence "
        "{{evidence:evidence-run-demo-valid-retrieval-01}} states a zero value explicitly "
        "reported by the source, not missing data."
    )
    payload["claims"][2]["uncertainty"] = (
        "The method does not apply to that specific field."
    )
    payload["limitations"][0] = (
        "The source explicitly reports a zero value rather than missing data."
    )

    client = FakeLLMClient(payload_json=json.dumps(payload))
    result = client.synthesize(_live_like_request())

    public_output = result.payload_json.casefold()
    assert result.metadata.status == "success"
    assert "reported_zero" not in public_output
    assert "not_applicable" not in public_output
    assert client.call_count == 1


def test_authorized_evidence_numbers_require_attribution_and_source_support() -> None:
    payload = json.loads(_live_like_payload())
    payload["claims"][2]["text_template"] = (
        "The official evidence {{evidence:evidence-run-demo-valid-retrieval-01}} "
        "reports 0 for 2025."
    )
    client = FakeLLMClient(payload_json=json.dumps(payload))

    result = client.synthesize(_live_like_request())

    assert result.metadata.status == "success"
    assert client.call_count == 1


def test_request_rejects_input_owned_by_another_run() -> None:
    data = _request().model_dump()
    data["metrics"] = (
        LLMMetricInput(
            metric_id="metric-run-foreign-return",
            run_id="run-foreign",
            metric_name="return",
            value=0.1,
            unit="decimal return",
        ),
    )
    data["allowed_metric_ids"] = ("metric-run-foreign-return",)

    with pytest.raises(ValidationError, match="must belong to the synthesis run"):
        SynthesisRequest.model_validate(data)


@pytest.mark.parametrize("retired_version", ("trust-synthesis-v1", "trust-synthesis-v2"))
def test_synthesis_request_rejects_retired_prompt_versions(retired_version: str) -> None:
    data = _request().model_dump()
    data["prompt_version"] = retired_version

    with pytest.raises(ValidationError, match="trust-synthesis-v3"):
        SynthesisRequest.model_validate(data)


def test_official_evidence_excerpt_accepts_4000_characters_but_not_more() -> None:
    accepted = LLMEvidenceInput(
        evidence_id="evidence-run-test-boundary",
        run_id="run-test",
        excerpt="x" * 4_000,
        provenance_label="official_corpus_passage",
    )

    assert len(accepted.excerpt) == 4_000
    with pytest.raises(ValidationError, match="at most 4000 characters"):
        LLMEvidenceInput(
            evidence_id="evidence-run-test-too-long",
            run_id="run-test",
            excerpt="x" * 4_001,
            provenance_label="official_corpus_passage",
        )


@pytest.mark.parametrize(
    ("mode", "error_type", "expected_status"),
    (
        ("error", LLMProviderError, "provider_error"),
        ("timeout", LLMTimeoutError, "timeout"),
    ),
)
def test_fake_failures_are_clean_and_keep_metadata(mode, error_type, expected_status) -> None:  # type: ignore[no-untyped-def]
    client = FakeLLMClient(mode=mode)

    with pytest.raises(error_type) as caught:
        client.synthesize(_request())

    assert caught.value.metadata.status == expected_status
    assert caught.value.metadata.response_id is None
    assert caught.value.metadata.cost_estimate is None
    assert client.call_count == 1


def test_demo_factory_builds_fake_without_anthropic_initialization(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def reject_init(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("Anthropic client initialized in demo")

    monkeypatch.setattr("ai_quant.llm.anthropic.AnthropicSDKTransport.__init__", reject_init)

    assert isinstance(client_from_settings(Settings.from_env({})), FakeLLMClient)


def _request() -> SynthesisRequest:
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
        excerpt="Official test excerpt.",
        provenance_label="official_corpus_passage",
    )
    return SynthesisRequest(
        run_id="run-test",
        prompt_version="trust-synthesis-v3",
        context="Authorized context.",
        metrics=(metric,),
        evidence=(evidence,),
        allowed_metric_ids=(metric.metric_id,),
        allowed_evidence_ids=(evidence.evidence_id,),
    )


def _valid_payload() -> str:
    return json.dumps(
        {
            "summary": "Structured test draft.",
            "claims": [
                {
                    "text_template": (
                        "Return {{metric:metric-run-test-return}} supported by "
                        "{{evidence:evidence-run-test-source}}."
                    ),
                    "claim_type": "quantitative",
                    "metric_ids": ["metric-run-test-return"],
                    "evidence_ids": ["evidence-run-test-source"],
                    "uncertainty": None,
                }
            ],
            "limitations": ["Test-only output."],
        }
    )


def _live_like_request() -> SynthesisRequest:
    metrics = (
        LLMMetricInput(
            metric_id="metric-run-demo-valid-cumulative-return",
            run_id="run-demo-valid",
            metric_name="cumulative-return",
            value=0.06982119406430298,
            unit="decimal return",
        ),
        LLMMetricInput(
            metric_id="metric-run-demo-valid-maximum-drawdown",
            run_id="run-demo-valid",
            metric_name="maximum-drawdown",
            value=0.008335606281488328,
            unit="decimal loss",
        ),
    )
    evidence = LLMEvidenceInput(
        evidence_id="evidence-run-demo-valid-retrieval-01",
        run_id="run-demo-valid",
        excerpt=(
            "Official source period 2025. Coverage status reported_zero. Total renewable fuel "
            "consumption reported value 0 GJ. Scope 2 method not_applicable."
        ),
        provenance_label="official_corpus_passage",
    )
    return SynthesisRequest(
        run_id="run-demo-valid",
        context="Authorized official inputs.",
        metrics=metrics,
        evidence=(evidence,),
        allowed_metric_ids=tuple(metric.metric_id for metric in metrics),
        allowed_evidence_ids=(evidence.evidence_id,),
    )


def _live_like_payload() -> str:
    return json.dumps(
        {
            "summary": (
                "Historical financial metrics and official ESG evidence are presented "
                "as separate observations."
            ),
            "claims": [
                {
                    "text_template": (
                        "The historical cumulative return is "
                        "{{metric:metric-run-demo-valid-cumulative-return}}."
                    ),
                    "claim_type": "quantitative",
                    "metric_ids": ["metric-run-demo-valid-cumulative-return"],
                    "evidence_ids": [],
                    "uncertainty": "One historical run is descriptive, not predictive.",
                },
                {
                    "text_template": (
                        "The historical maximum drawdown is "
                        "{{metric:metric-run-demo-valid-maximum-drawdown}}."
                    ),
                    "claim_type": "quantitative",
                    "metric_ids": ["metric-run-demo-valid-maximum-drawdown"],
                    "evidence_ids": [],
                    "uncertainty": "One historical run does not establish future risk.",
                },
                {
                    "text_template": (
                        "Separately, the official evidence is "
                        "{{evidence:evidence-run-demo-valid-retrieval-01}}."
                    ),
                    "claim_type": "evidence",
                    "metric_ids": [],
                    "evidence_ids": ["evidence-run-demo-valid-retrieval-01"],
                    "uncertainty": (
                        "A source-reported zero is not missing data; a non-applicable field "
                        "describes that field only."
                    ),
                },
            ],
            "limitations": [
                "The metrics describe a single run.",
                "No out-of-sample validation is included.",
                "No live trading validation is included.",
            ],
        }
    )
