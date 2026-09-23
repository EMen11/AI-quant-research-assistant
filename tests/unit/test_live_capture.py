"""Offline tests for the explicitly authorized one-call capture path."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from ai_quant.config import AppMode, Settings
from ai_quant.llm import (
    AnthropicLLMClient,
    AnthropicTransportRequest,
    AnthropicTransportResponse,
)
from ai_quant.llm.cli import main as live_capture_cli
from ai_quant.llm.live_capture import (
    LiveCaptureError,
    LiveCaptureOutput,
    LiveCapturePlan,
    RejectedLiveCapture,
    SanitizedCandidateError,
    SanitizedLiveCaptureCandidate,
    ValidatedRunInput,
    capture_live_once,
    prepare_live_capture,
    sanitize_rejected_live_capture,
)
from ai_quant.market_data import FrozenSnapshotProvider, SnapshotRun
from ai_quant.model_calls import ModelCallMetadata
from ai_quant.quant import analyze_portfolio, demo_portfolio, demo_risk_free_rate
from ai_quant.retrieval import build_retrieval_passages
from ai_quant.trust import (
    DraftProposal,
    DraftSchemaError,
    EvidenceRecord,
    FixtureDraftGenerator,
    GenerationBudget,
    GenerationController,
    MetricRecord,
)
from ai_quant.trust.records import create_metric_records


@dataclass
class MockTransport:
    payload_json: str | None
    error: Exception | None = None
    stop_reason: str | None = None
    input_tokens: int = 123
    output_tokens: int = 45
    request_id: str = "req_mock_live_capture"
    calls: int = 0
    last_request: AnthropicTransportRequest | None = None

    def send(self, request: AnthropicTransportRequest) -> AnthropicTransportResponse:
        self.calls += 1
        self.last_request = request
        if self.error is not None:
            raise self.error
        return AnthropicTransportResponse(
            payload_json=self.payload_json,
            response_id="msg_mock_live_capture",
            provider_request_id=self.request_id,
            stop_reason=self.stop_reason,  # type: ignore[arg-type]
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            retry_count=0,
        )


def _structured_failure_payload(case: str) -> str | None:
    if case == "missing":
        return None
    if case == "json":
        return '{"summary":"SENSITIVEJSON",'

    payload = json.loads(_valid_payload())
    payload["limitations"] = ["SENSITIVEPAYLOAD"]
    if case == "pydantic":
        payload["unexpected"] = "SENSITIVEPYDANTIC"
    elif case == "placeholder":
        payload["claims"][0]["text_template"] = "Return {value}."
    elif case == "metric_value":
        payload["claims"][0]["text_template"] = (
            "Return {{metric:metric-run-live-test-return}} at 0.1 with "
            "{{evidence:evidence-run-live-test-source}}."
        )
    elif case == "period":
        payload["claims"][0]["text_template"] = (
            "In the same period, {{metric:metric-run-live-test-return}} and "
            "{{evidence:evidence-run-live-test-source}} are separate observations."
        )
    return json.dumps(payload)


def _multi_violation_payload() -> str:
    payload = json.loads(_valid_payload())
    payload["summary"] = "Separate historical observations requiring human review."
    payload["claims"] = [
        {
            "text_template": (
                "In the same period, {value} at 0.1 indicates limited downside risk."
            ),
            "claim_type": "quantitative",
            "metric_ids": ["metric-run-live-test-return"],
            "evidence_ids": ["evidence-run-live-test-source"],
            "uncertainty": "Human review remains required.",
        },
        {
            "text_template": "A second {value} at 0.1 remains historical.",
            "claim_type": "quantitative",
            "metric_ids": ["metric-run-live-test-return"],
            "evidence_ids": [],
            "uncertainty": None,
        },
    ]
    payload["limitations"] = ["No investment conclusion is provided."]
    return json.dumps(payload)


def test_dry_run_validates_without_anthropic_initialization_or_output(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "capture.json"

    def reject_init(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("Anthropic transport initialized during dry-run")

    monkeypatch.setattr("ai_quant.llm.anthropic.AnthropicSDKTransport.__init__", reject_init)

    plan = prepare_live_capture(
        input_path,
        output_path,
        model="claude-sonnet-5",
    )

    assert plan.status == "dry_run_validated"
    assert plan.execution_mode == "dry_run"
    assert plan.network_call_count == 0
    assert plan.live_capture_created is False
    assert plan.request.model_id == "claude-sonnet-5"
    assert plan.request.prompt_version == "trust-synthesis-v3"
    assert plan.request.metric_count == 1
    assert plan.request.evidence_count == 1
    assert plan.request.allowlisted_metric_id_count == 1
    assert plan.request.allowlisted_evidence_id_count == 1
    assert plan.request.estimated_input_tokens is None
    assert not output_path.exists()
    assert "PROMPT_CAPTURE_SECRET" not in plan.model_dump_json()


def test_cli_dry_run_writes_only_safe_plan_without_key_or_transport(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "dry-run-plan.json"

    def reject_init(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("Anthropic transport initialized during CLI dry-run")

    monkeypatch.setattr("ai_quant.llm.anthropic.AnthropicSDKTransport.__init__", reject_init)

    exit_code = live_capture_cli(
        (
            "capture",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--dry-run",
        ),
        environ={"APP_MODE": "demo", "ANTHROPIC_MODEL": "claude-sonnet-5"},
    )

    serialized = output_path.read_text(encoding="utf-8")
    plan = LiveCapturePlan.model_validate_json(serialized)
    assert exit_code == 0
    assert plan.status == "dry_run_validated"
    assert plan.network_call_count == 0
    assert plan.live_capture_created is False
    assert "PROMPT_CAPTURE_SECRET" not in serialized
    assert "KEY_CAPTURE_SECRET" not in serialized


def test_cli_failure_prints_only_safe_diagnostic_and_writes_no_capture(
    tmp_path: Path,
    capsys,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "failed-live-capture.json"
    raw_error = MockCLIProviderError()
    transport = MockTransport(_valid_payload(), error=raw_error)
    client = _client(transport)

    exit_code = live_capture_cli(
        (
            "capture",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--confirm-paid-call",
        ),
        environ={
            "APP_MODE": "live",
            "ANTHROPIC_API_KEY": "KEY_SECRET_CLI_1d10",
            "ANTHROPIC_MODEL": "placeholder-model-id",
        },
        client=client,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.startswith(
        "Anthropic capture failed: error_code=billing_error "
        "http_status=402 request_id=req_safe_cli_402 "
    )
    assert "rule_codes=none field_paths=none" in captured.err
    assert "retry_count=0" in captured.err
    assert "rejected_output_status=not_requested" in captured.err
    assert transport.calls == 1
    assert not output_path.exists()
    for marker in (
        "RAW_PROVIDER_MESSAGE_CLI_2e20",
        "RAW_HTTP_BODY_CLI_3f30",
        "RAW_HEADER_SECRET_CLI_4a40",
        "PROMPT_CAPTURE_SECRET",
        "KEY_SECRET_CLI_1d10",
    ):
        assert marker not in captured.err
        assert marker not in caplog.text


def test_cli_http_400_prints_only_allowlisted_reason_code(
    tmp_path: Path,
    capsys,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "failed-schema-capture.json"
    sensitive_marker = "RAW_SCHEMA_REASON_SECRET_CLI_5b50"
    raw_error = MockCLIProviderError(
        http_status=400,
        request_id="req_safe_cli_400",
        message=f"output_config.format.schema is invalid. {sensitive_marker}",
    )
    transport = MockTransport(_valid_payload(), error=raw_error)

    exit_code = live_capture_cli(
        (
            "capture",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--confirm-paid-call",
        ),
        environ={
            "APP_MODE": "live",
            "ANTHROPIC_API_KEY": "KEY_SECRET_CLI_SCHEMA_6c60",
            "ANTHROPIC_MODEL": "placeholder-model-id",
        },
        client=_client(transport),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.startswith(
        "Anthropic capture failed: error_code=invalid_request_error "
        "reason_code=invalid_output_schema http_status=400 "
        "request_id=req_safe_cli_400 "
    )
    assert "rule_codes=none field_paths=none" in captured.err
    assert "rejected_output_status=not_requested" in captured.err
    assert transport.calls == 1
    assert not output_path.exists()
    assert sensitive_marker not in captured.err
    assert sensitive_marker not in caplog.text
    assert "KEY_SECRET_CLI_SCHEMA_6c60" not in captured.err


def test_capture_failure_exposes_only_detached_safe_fields(
    tmp_path: Path,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "failed-public-capture.json"
    rejected_output_path = tmp_path / "failed-public-rejected.json"
    transport = MockTransport(_valid_payload(), error=MockCLIProviderError())

    with pytest.raises(LiveCaptureError) as caught:
        capture_live_once(
            input_path,
            output_path,
            settings=_live_settings(),
            confirm_paid_call=True,
            rejected_output_path=rejected_output_path,
            client=_client(transport),
        )

    error = caught.value
    exposed = _public_exception_values(error)
    assert error.error_code == "billing_error"
    assert error.http_status == 402
    assert error.request_id == "req_safe_cli_402"
    assert error.model_call is not None
    assert error.model_call.retry_count == 0
    assert error.__cause__ is None
    assert error.__context__ is None
    assert transport.calls == 1
    assert not output_path.exists()
    assert not rejected_output_path.exists()
    for marker in (
        "RAW_PROVIDER_MESSAGE_CLI_2e20",
        "RAW_HTTP_BODY_CLI_3f30",
        "RAW_HEADER_SECRET_CLI_4a40",
        "PROMPT_CAPTURE_SECRET",
        "KEY_CAPTURE_SECRET",
    ):
        assert marker not in exposed
        assert marker not in caplog.text


@pytest.mark.parametrize(
    (
        "case",
        "reason_code",
        "stop_reason",
        "expected_rule_codes",
        "expected_error_types",
        "expected_field_paths",
    ),
    (
        ("max_tokens", "max_tokens_exhausted", "max_tokens", (), (), ()),
        ("refusal", "provider_refusal", "refusal", (), (), ()),
        ("missing", "missing_parsed_output", "end_turn", (), (), ()),
        (
            "json",
            "response_json_invalid",
            "end_turn",
            (),
            ("json_invalid",),
            ("$",),
        ),
        (
            "pydantic",
            "pydantic_structure_invalid",
            "end_turn",
            (),
            ("extra_forbidden",),
            ("unexpected",),
        ),
        (
            "placeholder",
            "semantic_content_rule_failed",
            "end_turn",
            ("generic_placeholder", "metric_placeholder_mismatch"),
            (),
            ("claims.0.text_template",),
        ),
        (
            "metric_value",
            "semantic_content_rule_failed",
            "end_turn",
            ("free_numeric_literal", "metric_value_literal"),
            (),
            ("claims.0.text_template",),
        ),
        (
            "period",
            "semantic_content_rule_failed",
            "end_turn",
            ("unsupported_period_alignment",),
            (),
            ("claims.0.text_template",),
        ),
        (
            "unknown",
            "unknown_structured_output_error",
            "end_turn",
            (),
            (),
            (),
        ),
    ),
)
def test_structured_failures_preserve_only_safe_billable_metadata(
    tmp_path: Path,
    monkeypatch,
    capsys,
    caplog,
    case: str,
    reason_code: str,
    stop_reason: str,
    expected_rule_codes: tuple[str, ...],
    expected_error_types: tuple[str, ...],
    expected_field_paths: tuple[str, ...],
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / f"failed-{case}.json"
    rejected_output_path = tmp_path / f"rejected-{case}.json"
    payload = _structured_failure_payload(case)
    transport = MockTransport(payload, stop_reason=stop_reason)
    client = AnthropicLLMClient(
        api_key="KEY_CAPTURE_SECRET",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    if case == "unknown":

        def fail_unknown(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            raise RuntimeError("SENSITIVEUNKNOWN")

        monkeypatch.setattr(
            "ai_quant.llm.anthropic.validated_synthesis_result",
            fail_unknown,
        )

    settings = Settings(
        app_mode=AppMode.LIVE,
        anthropic_api_key="KEY_CAPTURE_SECRET",
        anthropic_model="claude-sonnet-5",
    )
    with pytest.raises(LiveCaptureError) as caught:
        capture_live_once(
            input_path,
            output_path,
            settings=settings,
            confirm_paid_call=True,
            rejected_output_path=(
                None
                if reason_code == "semantic_content_rule_failed"
                else rejected_output_path
            ),
            client=client,
        )

    error = caught.value
    captured = capsys.readouterr()
    exposed = _public_exception_values(error)
    assert error.error_code == "structured_output_invalid"
    assert error.reason_code == reason_code
    assert error.request_id == "req_mock_live_capture"
    assert error.failure is not None
    assert error.failure.status == "failed"
    assert set(expected_rule_codes) <= set(error.failure.content_rule_codes)
    assert set(expected_error_types) <= set(error.failure.validation_error_types)
    assert set(expected_field_paths) <= set(error.failure.validation_field_paths)
    assert error.model_call is not None
    assert error.model_call.status == "schema_error"
    assert error.model_call.model_id == "claude-sonnet-5"
    assert error.model_call.prompt_version == "trust-synthesis-v3"
    assert error.model_call.provider_request_id == "req_mock_live_capture"
    assert error.model_call.response_id == "msg_mock_live_capture"
    assert error.model_call.stop_reason == stop_reason
    assert error.model_call.input_tokens == 123
    assert error.model_call.output_tokens == 45
    assert error.model_call.total_tokens == 168
    assert error.model_call.cost_estimate == Decimal("0.000696")
    assert error.model_call.currency == "USD"
    assert error.model_call.retry_count == 0
    assert error.__cause__ is None
    assert error.__context__ is None
    assert transport.calls == 1
    assert transport.last_request is not None
    assert not hasattr(transport.last_request, "tools")
    assert not output_path.exists()
    assert not rejected_output_path.exists()
    assert captured.out == ""
    assert captured.err == ""
    for marker in (
        "SENSITIVEJSON",
        "SENSITIVEPAYLOAD",
        "SENSITIVEPYDANTIC",
        "SENSITIVEUNKNOWN",
        "PROMPT_CAPTURE_SECRET",
        "KEY_CAPTURE_SECRET",
    ):
        assert marker not in exposed
        assert marker not in caplog.text
        assert marker not in captured.out
        assert marker not in captured.err


def test_semantic_rejection_writes_atomic_strict_quarantine_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "capture.json"
    rejected_output_path = tmp_path / "rejected.json"
    payload = _multi_violation_payload()
    pydantic_valid_proposal = DraftProposal.model_validate_json(payload)
    transport = MockTransport(payload, stop_reason="end_turn")
    client = AnthropicLLMClient(
        api_key="KEY_QUARANTINE_SECRET",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )
    settings = Settings(
        app_mode=AppMode.LIVE,
        anthropic_api_key="KEY_QUARANTINE_SECRET",
        anthropic_model="claude-sonnet-5",
    )
    original_link = os.link
    link_calls = 0

    def checked_atomic_link(source, destination):  # type: ignore[no-untyped-def]
        nonlocal link_calls
        link_calls += 1
        source_path = Path(source)
        destination_path = Path(destination)
        assert destination_path == rejected_output_path
        assert not destination_path.exists()
        RejectedLiveCapture.model_validate_json(source_path.read_text(encoding="utf-8"))
        original_link(source, destination)

    monkeypatch.setattr("ai_quant.llm.live_capture.os.link", checked_atomic_link)

    with pytest.raises(LiveCaptureError) as caught:
        capture_live_once(
            input_path,
            output_path,
            settings=settings,
            confirm_paid_call=True,
            rejected_output_path=rejected_output_path,
            client=client,
        )

    error = caught.value
    captured = capsys.readouterr()
    serialized = rejected_output_path.read_text(encoding="utf-8")
    artifact = RejectedLiveCapture.model_validate_json(serialized)
    raw_artifact = json.loads(serialized)
    assert set(raw_artifact) == {
        "schema_version",
        "artifact_type",
        "status",
        "demo_eligible",
        "promotion_policy",
        "error_code",
        "reason_code",
        "run_id",
        "provider",
        "model_id",
        "prompt_version",
        "proposal",
        "rule_codes",
        "field_paths",
        "model_call",
    }
    assert artifact.artifact_type == "rejected_live_capture"
    assert artifact.status == "semantic_validation_failed"
    assert artifact.demo_eligible is False
    assert artifact.promotion_policy == "automatic_demo_fixture_promotion_forbidden"
    assert artifact.proposal.claims == pydantic_valid_proposal.claims
    assert artifact.proposal.limitations == pydantic_valid_proposal.limitations
    assert artifact.proposal.summary != pydantic_valid_proposal.summary
    assert artifact.rule_codes == tuple(sorted(set(artifact.rule_codes)))
    assert artifact.field_paths == tuple(sorted(set(artifact.field_paths)))
    assert {
        "free_numeric_literal",
        "generic_placeholder",
        "metric_placeholder_mismatch",
        "metric_value_literal",
        "unsupported_period_alignment",
        "unsupported_risk_statement",
    } <= set(artifact.rule_codes)
    assert artifact.field_paths == (
        "claims.0.text_template",
        "claims.1.text_template",
    )
    assert artifact.model_call.provider_request_id == "req_mock_live_capture"
    assert artifact.model_call.stop_reason == "end_turn"
    assert artifact.model_call.total_tokens == 168
    assert artifact.model_call.retry_count == 0
    assert artifact.model_call.cost_estimate == Decimal("0.000696")
    assert error.error_code == "structured_output_invalid"
    assert error.reason_code == "semantic_content_rule_failed"
    assert error.rejected_output_status == "written"
    assert error.rejected_output_error_code is None
    assert error.__cause__ is None
    assert error.__context__ is None
    assert transport.calls == 1
    assert link_calls == 1
    assert not output_path.exists()
    assert not tuple(tmp_path.glob(".rejected.json.*.tmp"))
    assert captured.out == ""
    assert captured.err == ""
    with pytest.raises(ValidationError):
        RejectedLiveCapture.model_validate({**raw_artifact, "unexpected": True})
    with pytest.raises(ValidationError):
        RejectedLiveCapture.model_validate(
            {**raw_artifact, "rule_codes": ["provider_free_text"]}
        )
    exposed = _public_exception_values(error)
    for marker in (
        "KEY_QUARANTINE_SECRET",
        "PROMPT_CAPTURE_SECRET",
        "system_prompt",
        "user_prompt",
        "headers",
        "response_json",
    ):
        assert marker not in exposed
        assert marker not in caplog.text
        assert marker not in captured.out
        assert marker not in captured.err
        assert marker not in serialized


def test_cli_semantic_rejection_reports_safe_complete_diagnostic(
    tmp_path: Path,
    capsys,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "capture.json"
    rejected_output_path = tmp_path / "rejected.json"
    transport = MockTransport(_multi_violation_payload(), stop_reason="end_turn")
    client = AnthropicLLMClient(
        api_key="KEY_CLI_QUARANTINE_SECRET",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )

    exit_code = live_capture_cli(
        (
            "capture",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--rejected-output",
            str(rejected_output_path),
            "--confirm-paid-call",
        ),
        environ={
            "APP_MODE": "live",
            "ANTHROPIC_API_KEY": "KEY_CLI_QUARANTINE_SECRET",
            "ANTHROPIC_MODEL": "claude-sonnet-5",
        },
        client=client,
    )

    captured = capsys.readouterr()
    artifact = RejectedLiveCapture.model_validate_json(
        rejected_output_path.read_text(encoding="utf-8")
    )
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.startswith(
        "Anthropic capture failed: error_code=structured_output_invalid "
        "reason_code=semantic_content_rule_failed http_status=none "
        "request_id=req_mock_live_capture "
    )
    assert f"rule_codes={','.join(artifact.rule_codes)}" in captured.err
    assert f"field_paths={','.join(artifact.field_paths)}" in captured.err
    assert "response_id=msg_mock_live_capture" in captured.err
    assert "stop_reason=end_turn" in captured.err
    assert "provider=anthropic" in captured.err
    assert "model=claude-sonnet-5" in captured.err
    assert "prompt_version=trust-synthesis-v3" in captured.err
    assert "status=schema_error" in captured.err
    assert "input_tokens=123" in captured.err
    assert "output_tokens=45" in captured.err
    assert "total_tokens=168" in captured.err
    assert "retry_count=0" in captured.err
    assert "cost_estimate=0.000696" in captured.err
    assert "currency=USD" in captured.err
    assert "pricing_snapshot_id=anthropic-standard-token-pricing-2026-09-23-v1" in (
        captured.err
    )
    assert "rejected_output_status=written" in captured.err
    assert transport.calls == 1
    assert not output_path.exists()
    for marker in (
        "KEY_CLI_QUARANTINE_SECRET",
        "PROMPT_CAPTURE_SECRET",
        "system_prompt",
        "user_prompt",
        "headers",
        "response_json",
    ):
        assert marker not in captured.err
        assert marker not in caplog.text


def test_rejected_artifact_refuses_overwrite_and_preserves_original_error(
    tmp_path: Path,
) -> None:
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "capture.json"
    rejected_output_path = tmp_path / "rejected.json"
    rejected_output_path.write_text("DO_NOT_REPLACE", encoding="utf-8")
    transport = MockTransport(_multi_violation_payload(), stop_reason="end_turn")
    client = AnthropicLLMClient(
        api_key="KEY_CAPTURE_SECRET",
        model="claude-sonnet-5",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )
    settings = Settings(
        app_mode=AppMode.LIVE,
        anthropic_api_key="KEY_CAPTURE_SECRET",
        anthropic_model="claude-sonnet-5",
    )

    with pytest.raises(LiveCaptureError) as caught:
        capture_live_once(
            input_path,
            output_path,
            settings=settings,
            confirm_paid_call=True,
            overwrite=True,
            rejected_output_path=rejected_output_path,
            client=client,
        )

    error = caught.value
    assert error.error_code == "structured_output_invalid"
    assert error.reason_code == "semantic_content_rule_failed"
    assert error.rejected_output_status == "write_failed"
    assert error.rejected_output_error_code == "rejected-output-exists"
    assert error.model_call is not None
    assert error.model_call.total_tokens == 168
    assert error.__cause__ is None
    assert error.__context__ is None
    assert rejected_output_path.read_text(encoding="utf-8") == "DO_NOT_REPLACE"
    assert not output_path.exists()
    assert transport.calls == 1


def test_committed_live_preflight_input_is_valid_and_official() -> None:
    fixture = Path("src/ai_quant/fixtures/validated_run_official_v1.json")

    validated_run = ValidatedRunInput.model_validate_json(
        fixture.read_text(encoding="utf-8")
    )

    assert validated_run.run_id == "run-demo-valid"
    assert validated_run.prompt_version == "trust-synthesis-v3"
    assert len(validated_run.metrics) == 2
    assert len(validated_run.evidence) == 1
    assert all(record.status == "official_corpus_passage" for record in validated_run.evidence)

    portfolio = demo_portfolio()
    snapshot_run = SnapshotRun(FrozenSnapshotProvider.demo())
    snapshot_run.snapshot_for(portfolio)
    analysis = analyze_portfolio(portfolio, snapshot_run, demo_risk_free_rate())
    assert validated_run.metrics == create_metric_records("run-demo-valid", analysis)

    passage = next(
        passage
        for passage in build_retrieval_passages(date(2026, 3, 12))
        if passage.passage_id == "passage-observation-bachem-2025-renewable-fuel"
    )
    evidence = validated_run.evidence[0]
    assert evidence.excerpt == passage.text
    assert evidence.document_sha256 == passage.document_sha256
    assert evidence.page == passage.pdf_page


def test_demo_and_missing_confirmation_refuse_before_anthropic_initialization(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    input_path = _write_input(tmp_path)

    def reject_init(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("Anthropic transport initialized before authorization")

    monkeypatch.setattr("ai_quant.llm.anthropic.AnthropicSDKTransport.__init__", reject_init)

    with pytest.raises(LiveCaptureError) as unconfirmed:
        capture_live_once(
            input_path,
            tmp_path / "unconfirmed.json",
            settings=_live_settings(),
            confirm_paid_call=False,
        )
    with pytest.raises(LiveCaptureError) as demo:
        capture_live_once(
            input_path,
            tmp_path / "demo.json",
            settings=Settings(app_mode=AppMode.DEMO),
            confirm_paid_call=True,
        )

    assert unconfirmed.value.error_code == "live-confirmation-required"
    assert demo.value.error_code == "live-mode-required"


@pytest.mark.parametrize(
    ("settings", "error_code"),
    (
        (Settings(app_mode=AppMode.LIVE, anthropic_model="placeholder-model"), "live-key-required"),
        (
            Settings(app_mode=AppMode.LIVE, anthropic_api_key="KEY_CAPTURE_SECRET"),
            "live-model-required",
        ),
    ),
)
def test_missing_live_credentials_are_rejected_without_values(
    tmp_path: Path,
    settings: Settings,
    error_code: str,
) -> None:
    input_path = _write_input(tmp_path)

    with pytest.raises(LiveCaptureError) as caught:
        capture_live_once(
            input_path,
            tmp_path / f"{error_code}.json",
            settings=settings,
            confirm_paid_call=True,
        )

    assert caught.value.error_code == error_code
    assert "KEY_CAPTURE_SECRET" not in str(caught.value)


def test_injected_client_must_use_the_configured_model(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path)
    transport = MockTransport(_valid_payload())
    mismatched_client = AnthropicLLMClient(
        api_key="KEY_CAPTURE_SECRET",
        model="different-placeholder-model",
        transport=transport,
        response_origin="mocked_provider",
    )

    with pytest.raises(LiveCaptureError) as caught:
        capture_live_once(
            input_path,
            tmp_path / "mismatch.json",
            settings=_live_settings(),
            confirm_paid_call=True,
            client=mismatched_client,
        )

    assert caught.value.error_code == "live-model-mismatch"
    assert transport.calls == 0


def test_mocked_authorized_capture_calls_once_and_exports_only_clean_pending_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from ai_quant.llm.base import validated_synthesis_result as validate_result

    input_path = _write_input(tmp_path)
    output_path = tmp_path / "capture.json"
    rejected_output_path = tmp_path / "should-not-exist-rejected.json"
    transport = MockTransport(_valid_payload())
    client = _client(transport)
    post_validation_calls = 0

    def track_post_validation(payload_json, request, metadata):  # type: ignore[no-untyped-def]
        nonlocal post_validation_calls
        post_validation_calls += 1
        return validate_result(payload_json, request, metadata)

    monkeypatch.setattr(
        "ai_quant.llm.live_capture.validated_synthesis_result",
        track_post_validation,
    )

    capture = capture_live_once(
        input_path,
        output_path,
        settings=_live_settings(),
        confirm_paid_call=True,
        rejected_output_path=rejected_output_path,
        client=client,
    )

    serialized = output_path.read_text(encoding="utf-8")
    loaded = LiveCaptureOutput.model_validate_json(serialized)
    assert transport.calls == 1
    assert post_validation_calls == 1
    assert not rejected_output_path.exists()
    assert transport.last_request is not None
    assert not hasattr(transport.last_request, "tools")
    assert capture == loaded
    assert loaded.status == "pending_human_review"
    assert loaded.capture_kind == "unvalidated_live_capture"
    assert loaded.eligible_as_demo_fixture is False
    assert loaded.model_call.provider == "anthropic"
    assert loaded.model_call.input_tokens == 123
    assert loaded.model_call.cost_estimate is None
    assert loaded.model_call.cost_unavailable_reason
    for forbidden in (
        "KEY_CAPTURE_SECRET",
        "PROMPT_CAPTURE_SECRET",
        "system_prompt",
        "user_prompt",
        "headers",
    ):
        assert forbidden not in serialized

    with pytest.raises(DraftSchemaError):
        GenerationController(
            FixtureDraftGenerator(output_path, response_id="capture-not-a-fixture"),
            GenerationBudget(),
        ).generate(allowed_metric_ids=(), allowed_evidence_ids=())


def test_validation_runs_before_and_after_the_single_mocked_call(tmp_path: Path) -> None:
    invalid_input = json.loads(_validated_input().model_dump_json())
    invalid_input["evidence"][0]["run_id"] = "run-foreign"
    invalid_input_path = tmp_path / "invalid-input.json"
    invalid_input_path.write_text(json.dumps(invalid_input), encoding="utf-8")
    pre_transport = MockTransport(_valid_payload())

    with pytest.raises(LiveCaptureError) as before:
        capture_live_once(
            invalid_input_path,
            tmp_path / "before.json",
            settings=_live_settings(),
            confirm_paid_call=True,
            client=_client(pre_transport),
        )

    assert before.value.error_code == "live-input-invalid"
    assert pre_transport.calls == 0

    input_path = _write_input(tmp_path)
    post_transport = MockTransport(
        json.dumps(
            {
                "summary": "Invalid out-of-allowlist response.",
                "claims": [
                    {
                        "text_template": "Unknown {{metric:metric-run-foreign-return}}.",
                        "claim_type": "quantitative",
                        "metric_ids": ["metric-run-foreign-return"],
                        "evidence_ids": [],
                        "uncertainty": None,
                    }
                ],
                "limitations": ["Must fail after the call."],
            }
        )
    )
    output_path = tmp_path / "after.json"

    with pytest.raises(LiveCaptureError) as after:
        capture_live_once(
            input_path,
            output_path,
            settings=_live_settings(),
            confirm_paid_call=True,
            client=_client(post_transport),
        )

    assert after.value.error_code == "llm-allowlist-error"
    assert after.value.model_call is not None
    assert after.value.model_call.status == "allowlist_error"
    assert after.value.__cause__ is None
    assert after.value.__context__ is None
    assert post_transport.calls == 1
    assert not output_path.exists()


def test_existing_output_is_rejected_before_call_unless_overwrite_is_explicit(
    tmp_path: Path,
) -> None:
    input_path = _write_input(tmp_path)
    output_path = tmp_path / "capture.json"
    output_path.write_text("existing", encoding="utf-8")
    transport = MockTransport(_valid_payload())

    with pytest.raises(LiveCaptureError) as caught:
        capture_live_once(
            input_path,
            output_path,
            settings=_live_settings(),
            confirm_paid_call=True,
            client=_client(transport),
        )

    assert caught.value.error_code == "live-output-exists"
    assert transport.calls == 0
    assert output_path.read_text(encoding="utf-8") == "existing"


def test_rejected_summary_is_normalized_offline_into_strict_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    source = _eligible_rejected_capture()
    source_path = tmp_path / "rejected.json"
    source_path.write_text(source.model_dump_json(indent=2) + "\n", encoding="utf-8")
    run_input_path = _write_input(tmp_path)
    output_path = tmp_path / "candidate.json"
    protected_before = _protected_proposal_bytes(source.proposal)

    def reject_transport(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("Anthropic transport initialized during offline normalization")

    monkeypatch.setattr("ai_quant.llm.anthropic.AnthropicSDKTransport.__init__", reject_transport)

    candidate = sanitize_rejected_live_capture(
        source_path,
        run_input_path,
        output_path,
    )
    serialized = output_path.read_text(encoding="utf-8")
    loaded = SanitizedLiveCaptureCandidate.model_validate_json(serialized)

    assert candidate == loaded
    assert candidate.status == "pending_human_review"
    assert candidate.demo_eligible is False
    assert candidate.fixture_derivation == "live_derived_deterministically_normalized"
    assert candidate.normalization_version == "canonical-summary-v1"
    assert candidate.normalized_fields == ("summary",)
    assert candidate.raw_provider_response_persisted is False
    assert candidate.source_artifact_type == "rejected_live_capture"
    assert candidate.source_artifact_sha256 == hashlib.sha256(
        source_path.read_bytes()
    ).hexdigest()
    assert candidate.proposal.summary == (
        "This report presents historical run metrics and a separate official evidence record. "
        "Each is reported independently, and no temporal, causal, predictive or investment "
        "relationship between them is asserted."
    )
    assert source.proposal.summary not in serialized
    assert _protected_proposal_bytes(candidate.proposal) == protected_before
    assert candidate.initial_validation.rule_codes == (
        "implicit_cross_domain_relation",
    )
    assert candidate.initial_validation.field_paths == ("summary",)
    assert candidate.post_normalization_validation.status == "validated"
    assert candidate.post_normalization_validation.rule_codes == ()
    assert candidate.validation_report.issues == ()
    assert candidate.rendered_draft.reliable
    assert candidate.rendered_draft.final_text is not None
    assert "{{" not in candidate.rendered_draft.final_text
    assert "}}" not in candidate.rendered_draft.final_text
    assert candidate.model_call == source.model_call
    assert candidate.model_call.status == "schema_error"
    assert candidate.model_call.cost_estimate == Decimal("0.000696")
    assert candidate.source_response_id == source.model_call.response_id
    assert candidate.source_request_id == source.model_call.provider_request_id
    for forbidden in (
        '"raw_provider_response":',
        '"payload_json":',
        '"system_prompt":',
        '"user_prompt":',
        '"headers":',
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("rule_codes", "field_paths"),
    (
        (("internal_status_token",), ("summary",)),
        (("implicit_cross_domain_relation",), ("claims.0.text_template",)),
        (
            ("implicit_cross_domain_relation", "internal_status_token"),
            ("summary",),
        ),
        (
            ("implicit_cross_domain_relation",),
            ("limitations.0", "summary"),
        ),
    ),
)
def test_rejected_normalization_refuses_other_or_multiple_diagnostics(
    tmp_path: Path,
    rule_codes: tuple[str, ...],
    field_paths: tuple[str, ...],
) -> None:
    source = _eligible_rejected_capture()
    source = RejectedLiveCapture.model_validate(
        {
            **source.model_dump(),
            "rule_codes": tuple(sorted(rule_codes)),
            "field_paths": tuple(sorted(field_paths)),
        }
    )
    source_path = tmp_path / "rejected.json"
    source_path.write_text(source.model_dump_json(), encoding="utf-8")

    with pytest.raises(SanitizedCandidateError) as caught:
        sanitize_rejected_live_capture(
            source_path,
            _write_input(tmp_path),
            tmp_path / "candidate.json",
        )

    assert caught.value.error_code == "sanitized-source-ineligible"
    assert not (tmp_path / "candidate.json").exists()


@pytest.mark.parametrize(
    "mutation",
    ("internal_status", "unknown_reference", "placeholder_mismatch", "metric_value"),
)
def test_rejected_normalization_replays_all_non_summary_rules(
    tmp_path: Path,
    mutation: str,
) -> None:
    source = _eligible_rejected_capture()
    proposal = source.proposal.model_dump(mode="json")
    if mutation == "internal_status":
        proposal["limitations"][0] = "Internal status reported_zero."
    elif mutation == "unknown_reference":
        proposal["claims"][0]["text_template"] = (
            "Unknown {{metric:metric-run-foreign-return}}."
        )
        proposal["claims"][0]["metric_ids"] = ["metric-run-foreign-return"]
    elif mutation == "placeholder_mismatch":
        proposal["claims"][0]["text_template"] = "Historical return is available."
    else:
        proposal["claims"][0]["uncertainty"] = "The historical return was 0.1."
    mutated_proposal = DraftProposal.model_validate_json(json.dumps(proposal))
    source = source.model_copy(update={"proposal": mutated_proposal})
    source_path = tmp_path / "rejected.json"
    source_path.write_text(source.model_dump_json(), encoding="utf-8")

    with pytest.raises(SanitizedCandidateError) as caught:
        sanitize_rejected_live_capture(
            source_path,
            _write_input(tmp_path),
            tmp_path / "candidate.json",
        )

    assert caught.value.error_code in {
        "sanitized-source-diagnostics-mismatch",
        "sanitized-post-validation-failed",
    }


def test_rejected_normalization_refuses_existing_output_and_normalized_source(
    tmp_path: Path,
) -> None:
    source = _eligible_rejected_capture()
    source_path = tmp_path / "rejected.json"
    source_path.write_text(source.model_dump_json(), encoding="utf-8")
    run_input_path = _write_input(tmp_path)
    output_path = tmp_path / "candidate.json"
    candidate = sanitize_rejected_live_capture(source_path, run_input_path, output_path)
    preserved = output_path.read_bytes()

    with pytest.raises(SanitizedCandidateError) as existing:
        sanitize_rejected_live_capture(source_path, run_input_path, output_path)
    with pytest.raises(SanitizedCandidateError) as normalized:
        sanitize_rejected_live_capture(
            output_path,
            run_input_path,
            tmp_path / "second-candidate.json",
        )

    assert existing.value.error_code == "sanitized-output-exists"
    assert normalized.value.error_code == "sanitized-source-already-normalized"
    assert output_path.read_bytes() == preserved
    assert candidate.status == "pending_human_review"
    assert not (tmp_path / "second-candidate.json").exists()


@pytest.mark.parametrize("mismatch", ("run", "prompt"))
def test_rejected_normalization_refuses_run_or_prompt_mismatch(
    tmp_path: Path,
    mismatch: str,
) -> None:
    source = _eligible_rejected_capture()
    updates: dict[str, object]
    if mismatch == "prompt":
        updates = {
            "prompt_version": "trust-synthesis-v2",
            "model_call": source.model_call.model_copy(
                update={"prompt_version": "trust-synthesis-v2"}
            ),
        }
    else:
        updates = {"run_id": "run-live-foreign"}
    mismatched_source = RejectedLiveCapture.model_validate(
        {**source.model_dump(), **updates}
    )
    source_path = tmp_path / "rejected.json"
    source_path.write_text(mismatched_source.model_dump_json(), encoding="utf-8")

    with pytest.raises(SanitizedCandidateError) as caught:
        sanitize_rejected_live_capture(
            source_path,
            _write_input(tmp_path),
            tmp_path / "candidate.json",
        )

    assert caught.value.error_code == "sanitized-source-ineligible"


def test_cli_sanitizes_rejected_capture_without_live_configuration(
    tmp_path: Path,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    source = _eligible_rejected_capture()
    source_path = tmp_path / "rejected.json"
    source_path.write_text(source.model_dump_json(), encoding="utf-8")
    output_path = tmp_path / "candidate.json"

    exit_code = live_capture_cli(
        (
            "sanitize-rejected",
            "--input",
            str(source_path),
            "--run-input",
            str(_write_input(tmp_path)),
            "--output",
            str(output_path),
        ),
        environ={},
    )

    captured = capsys.readouterr()
    candidate = SanitizedLiveCaptureCandidate.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )
    assert exit_code == 0
    assert captured.err == ""
    assert "candidate_status=pending_human_review" in captured.out
    assert "normalization_version=canonical-summary-v1" in captured.out
    assert candidate.status == "pending_human_review"


def _write_input(tmp_path: Path) -> Path:
    path = tmp_path / "validated-run.json"
    path.write_text(_validated_input().model_dump_json(indent=2), encoding="utf-8")
    return path


def _validated_input() -> ValidatedRunInput:
    return ValidatedRunInput(
        validation_status="validated",
        run_id="run-live-test",
        prompt_version="trust-synthesis-v3",
        context="Official context with PROMPT_CAPTURE_SECRET marker.",
        metrics=(
            MetricRecord(
                metric_id="metric-run-live-test-return",
                run_id="run-live-test",
                metric_name="cumulative-return",
                value=0.1,
                unit="decimal return",
                horizon_or_frequency="daily",
                formula_version="formula-v1",
                snapshot_id="snapshot-live-test",
            ),
        ),
        evidence=(
            EvidenceRecord(
                evidence_id="evidence-run-live-test-source",
                run_id="run-live-test",
                document_id="document-live-test",
                document_sha256="0" * 64,
                page=33,
                excerpt="Official issuer passage.",
                period="2025",
                unit="GJ",
                status="official_corpus_passage",
                passage_id="passage-live-test",
                source_record_type="sustainability_observation",
                source_record_id="observation-live-test",
                issuer_id="issuer-live-test",
                publication_date=date(2026, 3, 12),
                printed_page=31,
            ),
        ),
    )


def _live_settings() -> Settings:
    return Settings(
        app_mode=AppMode.LIVE,
        anthropic_api_key="KEY_CAPTURE_SECRET",
        anthropic_model="placeholder-model-id",
    )


def _client(transport: MockTransport) -> AnthropicLLMClient:
    return AnthropicLLMClient(
        api_key="KEY_CAPTURE_SECRET",
        model="placeholder-model-id",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 1.0,
    )


def _valid_payload() -> str:
    return json.dumps(
        {
            "summary": "Mocked capture proposal.",
            "claims": [
                {
                    "text_template": (
                        "Return {{metric:metric-run-live-test-return}} with "
                        "{{evidence:evidence-run-live-test-source}}."
                    ),
                    "claim_type": "quantitative",
                    "metric_ids": ["metric-run-live-test-return"],
                    "evidence_ids": ["evidence-run-live-test-source"],
                    "uncertainty": "Human review remains required.",
                }
            ],
            "limitations": ["Mocked transport; not a validated public fixture."],
        }
    )


def _eligible_rejected_capture() -> RejectedLiveCapture:
    proposal = DraftProposal.model_validate_json(_valid_payload()).model_copy(
        update={
            "summary": (
                "The financial metric is associated with the ESG evidence, although human "
                "review remains required."
            )
        }
    )
    model_call = ModelCallMetadata(
        provider="anthropic",
        model_id="claude-sonnet-5",
        prompt_version="trust-synthesis-v3",
        status="schema_error",
        latency_ms=125.0,
        response_id="msg_mock_sanitized_source",
        provider_request_id="req_mock_sanitized_source",
        input_tokens=123,
        output_tokens=45,
        total_tokens=168,
        stop_reason="end_turn",
        retry_count=0,
        error_type="DraftContentValidationError",
        cost_estimate=Decimal("0.000696"),
        currency="USD",
        pricing_source_url="https://platform.claude.com/docs/en/models/overview",
        pricing_valid_on=date(2026, 9, 23),
        pricing_snapshot_id="anthropic-standard-token-pricing-2026-09-23-v1",
        cost_unavailable_reason=None,
        response_origin="live_provider",
    )
    return RejectedLiveCapture(
        run_id="run-live-test",
        provider="anthropic",
        model_id="claude-sonnet-5",
        prompt_version="trust-synthesis-v3",
        proposal=proposal,
        rule_codes=("implicit_cross_domain_relation",),
        field_paths=("summary",),
        model_call=model_call,
    )


def _protected_proposal_bytes(proposal: DraftProposal) -> bytes:
    return json.dumps(
        {
            "claims": [claim.model_dump(mode="json") for claim in proposal.claims],
            "limitations": proposal.limitations,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


class MockCLIProviderError(Exception):
    def __init__(
        self,
        *,
        http_status: int = 402,
        request_id: str = "req_safe_cli_402",
        message: str = "RAW_PROVIDER_MESSAGE_CLI_2e20",
    ) -> None:
        super().__init__(message)
        self.status_code = http_status
        self.request_id = request_id
        self.body = "RAW_HTTP_BODY_CLI_3f30"
        self.headers = {"authorization": "RAW_HEADER_SECRET_CLI_4a40"}


def _public_exception_values(error: BaseException) -> str:
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
