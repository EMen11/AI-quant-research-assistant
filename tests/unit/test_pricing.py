"""Deterministic Decimal pricing tests for standard Anthropic token usage."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ai_quant.llm.pricing import estimate_standard_token_cost, load_pricing_snapshot


def test_known_model_cost_uses_exact_decimal_formula() -> None:
    estimate = estimate_standard_token_cost(
        model_id="claude-sonnet-5",
        input_tokens=500_000,
        output_tokens=250_000,
        call_succeeded=True,
    )

    assert estimate.cost_estimate == Decimal("3.500000")
    assert estimate.currency == "USD"
    assert estimate.cost_unavailable_reason is None


def test_cost_serialization_is_deterministic_and_keeps_six_decimal_places() -> None:
    first = estimate_standard_token_cost(
        model_id="claude-sonnet-5",
        input_tokens=120,
        output_tokens=45,
        call_succeeded=True,
    )
    second = estimate_standard_token_cost(
        model_id="claude-sonnet-5",
        input_tokens=120,
        output_tokens=45,
        call_succeeded=True,
    )

    assert first.cost_estimate == Decimal("0.000690")
    assert first.model_dump_json() == second.model_dump_json()
    assert '"cost_estimate":"0.000690"' in first.model_dump_json()


def test_unknown_model_has_stable_unavailable_reason() -> None:
    estimate = estimate_standard_token_cost(
        model_id="unknown-model",
        input_tokens=120,
        output_tokens=45,
        call_succeeded=True,
    )

    assert estimate.cost_estimate is None
    assert estimate.cost_unavailable_reason == "pricing_unavailable_for_model"


def test_missing_tokens_have_stable_unavailable_reason() -> None:
    estimate = estimate_standard_token_cost(
        model_id="claude-sonnet-5",
        input_tokens=None,
        output_tokens=None,
        call_succeeded=True,
    )

    assert estimate.cost_estimate is None
    assert estimate.cost_unavailable_reason == "token_usage_unavailable"


def test_failed_call_never_invents_cost() -> None:
    estimate = estimate_standard_token_cost(
        model_id="claude-sonnet-5",
        input_tokens=120,
        output_tokens=45,
        call_succeeded=False,
    )

    assert estimate.cost_estimate is None
    assert estimate.cost_unavailable_reason == "model_call_failed"


def test_snapshot_records_official_source_date_scope_and_prices() -> None:
    snapshot = load_pricing_snapshot()
    pricing = snapshot.models[0]

    assert snapshot.pricing_snapshot_id == (
        "anthropic-standard-token-pricing-2026-09-23-v1"
    )
    assert snapshot.source_url == "https://platform.claude.com/docs/en/models/overview"
    assert snapshot.consulted_on == date(2026, 9, 23)
    assert snapshot.scope == "standard_input_output_tokens_only_no_prompt_caching"
    assert pricing.model_id == "claude-sonnet-5"
    assert pricing.input_price_per_million_tokens == Decimal("2")
    assert pricing.output_price_per_million_tokens == Decimal("10")
