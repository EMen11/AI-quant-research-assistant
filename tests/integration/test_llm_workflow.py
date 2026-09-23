"""Workflow integration for retrieval evidence and structured LLM failures."""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ai_quant.llm import (
    AnthropicLLMClient,
    AnthropicTransportRequest,
    AnthropicTransportResponse,
    FakeLLMClient,
    SynthesisLimits,
)
from ai_quant.llm.live_capture import ValidatedRunInput
from ai_quant.retrieval import BM25Retriever, PassageFilter, build_retrieval_passages
from ai_quant.trust import (
    DraftProposal,
    GenerationBudget,
    GenerationMetadata,
    InMemoryTrustWorkflow,
    WorkflowGenerationError,
    build_synthesis_request,
    render_validated_draft,
    validate_draft,
)
from ai_quant.trust.records import materialize_generated_draft


def test_public_demo_fixture_is_live_derived_and_still_offline() -> None:
    result = InMemoryTrustWorkflow().run("valid")

    assert result.draft.generation.model_call is not None
    assert result.draft.generation.model_call.response_origin == "live_provider"
    assert result.draft.generation.model_call.status == "schema_error"
    assert result.draft.generation.model_call.cost_estimate == Decimal("0.015574")
    assert all(record.status == "official_corpus_passage" for record in result.evidence_records)
    assert result.human_review is None


def test_workflow_injects_retrieved_passages_as_official_server_evidence() -> None:
    retriever = BM25Retriever(build_retrieval_passages(date(2026, 3, 12)))
    client = FakeLLMClient()

    result = InMemoryTrustWorkflow().run(
        "valid",
        retriever=retriever,
        retrieval_query="Bachem Scope 1 emissions 2025",
        retrieval_filters=PassageFilter(issuer_ids=("bachem-holding-ag",)),
        llm_client=client,
    )

    assert result.generation_calls == 1
    assert client.call_count == 1
    assert result.rendered_draft.reliable
    assert result.evidence_records
    assert all(record.run_id == result.run_id for record in result.evidence_records)
    assert all(record.status == "official_corpus_passage" for record in result.evidence_records)
    assert all(record.passage_id for record in result.evidence_records)
    assert result.draft.generation.model_call is not None
    assert result.draft.generation.model_call.response_origin == "deterministic_fake"
    assert result.draft.generation.prompt_version == "trust-synthesis-v3"


def test_v3_fake_run_demo_valid_renders_two_metrics_and_separate_evidence() -> None:
    retriever = BM25Retriever(build_retrieval_passages(date(2026, 3, 12)))
    client = FakeLLMClient()

    result = InMemoryTrustWorkflow().run(
        "valid",
        retriever=retriever,
        retrieval_query="Bachem renewable fuel consumption zero",
        retrieval_filters=PassageFilter(
            issuer_ids=("bachem-holding-ag",),
            years=(2025,),
            source_record_types=("sustainability_observation",),
            indicator_types=("renewable_energy_consumption",),
        ),
        llm_client=client,
    )

    quantitative = [claim for claim in result.draft.claims if claim.claim_type == "quantitative"]
    evidence = [claim for claim in result.draft.claims if claim.claim_type == "evidence"]
    assert result.run_id == "run-demo-valid"
    assert len(quantitative) == 2
    assert len(evidence) == 1
    assert not any(character.isdigit() for character in result.draft.summary)
    assert "reported independently" in result.draft.summary
    assert "same period" not in result.draft.summary.casefold()
    assert "caused by" not in result.draft.summary.casefold()
    assert "correlated" not in result.draft.summary.casefold()
    assert result.validation_report.issues == ()
    assert result.rendered_draft.reliable
    assert result.rendered_draft.final_text is not None
    assert all(metric.unit in result.rendered_draft.final_text for metric in result.metric_records)
    assert "{{" not in result.rendered_draft.final_text


def test_rejected_v2_draft_renders_after_only_public_status_rewording() -> None:
    validated_run = ValidatedRunInput.model_validate_json(
        Path("src/ai_quant/fixtures/validated_run_official_v1.json").read_text(
            encoding="utf-8"
        )
    )
    request = build_synthesis_request(
        run_id=validated_run.run_id,
        metrics=validated_run.metrics,
        evidence=validated_run.evidence,
        limits=validated_run.limits,
        context=validated_run.context,
        prompt_version=validated_run.prompt_version,
    )
    proposal = DraftProposal.model_validate(
        {
            "summary": (
                "This synthesis presents historical performance metrics for the run alongside "
                "a separate official evidence record concerning renewable energy consumption "
                "reporting. The metrics and the evidence are drawn from distinct sources and "
                "pertain to different aspects of the run; no correlation or causal relationship "
                "between them is implied. Limitations regarding scope and applicability of the "
                "evidence are noted separately below."
            ),
            "claims": (
                {
                    "text_template": (
                        "Historical metric "
                        "{{metric:metric-run-demo-valid-cumulative-return}} is reported for "
                        "this run."
                    ),
                    "claim_type": "quantitative",
                    "metric_ids": ("metric-run-demo-valid-cumulative-return",),
                    "evidence_ids": (),
                    "uncertainty": (
                        "This is a historical metric and does not by itself establish future "
                        "risk or safety characteristics."
                    ),
                },
                {
                    "text_template": (
                        "Historical metric "
                        "{{metric:metric-run-demo-valid-maximum-drawdown}} is reported for "
                        "this run."
                    ),
                    "claim_type": "quantitative",
                    "metric_ids": ("metric-run-demo-valid-maximum-drawdown",),
                    "evidence_ids": (),
                    "uncertainty": (
                        "This is a historical metric and does not by itself establish that risk "
                        "is limited or low."
                    ),
                },
                {
                    "text_template": (
                        "Separately, official evidence "
                        "{{evidence:evidence-run-demo-valid-retrieval-01}} indicates a value of "
                        "zero reported by the source, not missing data, for total fuel "
                        "consumption from renewable sources over the stated period."
                    ),
                    "claim_type": "evidence",
                    "metric_ids": (),
                    "evidence_ids": ("evidence-run-demo-valid-retrieval-01",),
                    "uncertainty": (
                        "The scope 2 method does not apply to this specific field."
                    ),
                },
            ),
            "limitations": (
                (
                    "The financial metrics and the ESG evidence record originate from different "
                    "sources and are presented as separate observations without implying any "
                    "linkage, correlation or causality between them."
                ),
                (
                    "No claim is made that the metrics and the evidence record cover the same "
                    "period, as their explicit dates are not confirmed to be equal in the "
                    "supplied inputs."
                ),
                (
                    "The evidence record's scope 2 method does not apply to that specific field "
                    "and should not be interpreted as missing evidence or a general conclusion "
                    "about the record."
                ),
                (
                    "The reported zero value for renewable fuel consumption reflects a value "
                    "explicitly reported by the source, not missing or unavailable data."
                ),
            ),
        }
    )
    client = FakeLLMClient(payload_json=proposal.model_dump_json())

    synthesis = client.synthesize(request)
    generation = GenerationMetadata(
        provider=synthesis.metadata.provider,
        model_id=synthesis.metadata.model_id,
        parameters=(),
        prompt_version=synthesis.metadata.prompt_version,
        response_id=synthesis.metadata.response_id or "response-fake-synthesis-v1",
        generated_at=datetime(2026, 9, 23, tzinfo=UTC),
        model_call=synthesis.metadata,
    )
    draft = materialize_generated_draft(validated_run.run_id, proposal, generation)
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

    assert client.call_count == 1
    assert report.issues == ()
    assert rendered.reliable
    assert rendered.final_text is not None
    assert "{{" not in rendered.final_text
    assert "}}" not in rendered.final_text
    assert "reported_zero" not in rendered.final_text.casefold()
    assert "not_applicable" not in rendered.final_text.casefold()


def test_workflow_passes_complete_287_character_official_passage_to_fake() -> None:
    retriever = BM25Retriever(build_retrieval_passages(date(2026, 3, 12)))
    client = FakeLLMClient()

    result = InMemoryTrustWorkflow().run(
        "valid",
        retriever=retriever,
        retrieval_query="Bachem renewable fuel consumption zero",
        retrieval_filters=PassageFilter(
            issuer_ids=("bachem-holding-ag",),
            years=(2025,),
            source_record_types=("sustainability_observation",),
            indicator_types=("renewable_energy_consumption",),
        ),
        llm_client=client,
    )

    assert client.call_count == 1
    assert client.last_request is not None
    assert len(client.last_request.evidence) == 1
    assert len(client.last_request.evidence[0].excerpt) == 287
    assert client.last_request.evidence[0].excerpt == result.evidence_records[0].excerpt
    assert result.evidence_records[0].passage_id == (
        "passage-observation-bachem-2025-renewable-fuel"
    )


@pytest.mark.parametrize("mode", ("error", "timeout"))
def test_workflow_failure_preserves_computed_metrics_and_evidence(mode: str) -> None:
    client = FakeLLMClient(mode=mode)  # type: ignore[arg-type]

    with pytest.raises(WorkflowGenerationError) as caught:
        InMemoryTrustWorkflow().run("valid", llm_client=client)

    failure = caught.value
    assert failure.metric_records
    assert failure.evidence_records
    assert failure.analysis.portfolio_metrics
    assert failure.model_call.status in {"provider_error", "timeout"}
    assert failure.status == failure.model_call.status
    assert failure.error_code in {"unknown_provider_error", "timeout_error"}
    assert failure.draft is None
    assert failure.validation_report is None
    assert failure.generation_calls == 1
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert client.call_count == 1


def test_controller_timeout_preserves_state_and_metadata_with_bounded_test_time() -> None:
    client = FakeLLMClient()
    ticks = iter((10.0, 12.1))
    started = time.monotonic()

    with pytest.raises(WorkflowGenerationError) as caught:
        InMemoryTrustWorkflow().run(
            "valid",
            llm_client=client,
            synthesis_limits=SynthesisLimits(timeout_seconds=2.0),
            budget=GenerationBudget(timeout_seconds=2.0),
            clock=lambda: next(ticks),
        )

    elapsed = time.monotonic() - started
    failure = caught.value
    assert elapsed < 1.0
    assert failure.metric_records
    assert failure.evidence_records
    assert failure.model_call is not None
    assert failure.model_call.status == "timeout"
    assert failure.model_call.error_type == "GenerationControllerTimeout"
    assert failure.status == "timeout"
    assert failure.error_code == "generation-timeout"
    assert failure.draft is None
    assert failure.validation_report is None
    assert failure.generation_calls == 1
    assert client.call_count == 1


def test_transport_timeout_cannot_exceed_controller_budget() -> None:
    client = FakeLLMClient()

    with pytest.raises(ValueError, match="cannot be shorter than the transport timeout"):
        InMemoryTrustWorkflow().run(
            "valid",
            llm_client=client,
            synthesis_limits=SynthesisLimits(timeout_seconds=15.0),
            budget=GenerationBudget(timeout_seconds=2.0),
        )

    assert client.call_count == 0


def test_workflow_accepts_anthropic_client_with_mocked_transport() -> None:
    class Transport:
        calls = 0

        def send(self, request: AnthropicTransportRequest) -> AnthropicTransportResponse:
            self.calls += 1
            assert not hasattr(request, "tools")
            return AnthropicTransportResponse(
                payload_json=json.dumps(
                    {
                        "summary": "Mocked adapter workflow.",
                        "claims": [
                            {
                                "text_template": (
                                    "Return {{metric:metric-run-demo-valid-cumulative-return}}."
                                ),
                                "claim_type": "quantitative",
                                "metric_ids": [
                                    "metric-run-demo-valid-cumulative-return"
                                ],
                                "evidence_ids": [],
                                "uncertainty": None,
                            }
                        ],
                        "limitations": ["Mocked provider compatibility only."],
                    }
                ),
                response_id="msg_mock_workflow",
            )

    transport = Transport()
    client = AnthropicLLMClient(
        api_key="placeholder-test-key",
        model="placeholder-model-id",
        transport=transport,
        response_origin="mocked_provider",
        clock=lambda: 0.0,
    )

    result = InMemoryTrustWorkflow().run("valid", llm_client=client, clock=lambda: 0.0)

    assert transport.calls == 1
    assert result.rendered_draft.reliable
    assert result.draft.generation.model_call is not None
    assert result.draft.generation.model_call.response_origin == "mocked_provider"
