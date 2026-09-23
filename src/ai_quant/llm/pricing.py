"""Versioned standard-token pricing used only for deterministic cost estimates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictPricingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModelTokenPricing(_StrictPricingModel):
    model_id: str = Field(min_length=1, max_length=160)
    input_price_per_million_tokens: Annotated[Decimal, Field(ge=0)]
    output_price_per_million_tokens: Annotated[Decimal, Field(ge=0)]


class PricingSnapshot(_StrictPricingModel):
    schema_version: Literal["llm-pricing-snapshot.v1"]
    pricing_snapshot_id: str = Field(min_length=1, max_length=160)
    currency: Literal["USD"]
    unit_token_count: Literal[1_000_000]
    source_url: str = Field(pattern=r"^https://")
    consulted_on: date
    scope: Literal["standard_input_output_tokens_only_no_prompt_caching"]
    models: Annotated[tuple[ModelTokenPricing, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def model_ids_are_unique(self) -> PricingSnapshot:
        model_ids = tuple(pricing.model_id for pricing in self.models)
        if len(model_ids) != len(set(model_ids)):
            raise ValueError("Pricing snapshot model IDs must be unique.")
        return self


PricingUnavailableReason = Literal[
    "pricing_unavailable_for_model",
    "token_usage_unavailable",
    "model_call_failed",
]


class TokenCostEstimate(_StrictPricingModel):
    cost_estimate: Decimal | None
    currency: Literal["USD"]
    pricing_snapshot_id: str
    pricing_source_url: str
    pricing_consulted_on: date
    cost_unavailable_reason: PricingUnavailableReason | None


@lru_cache(maxsize=1)
def load_pricing_snapshot() -> PricingSnapshot:
    """Load the committed pricing snapshot without network access."""

    return PricingSnapshot.model_validate_json(_snapshot_path().read_text(encoding="utf-8"))


def estimate_standard_token_cost(
    *,
    model_id: str,
    input_tokens: int | None,
    output_tokens: int | None,
    call_succeeded: bool,
) -> TokenCostEstimate:
    """Estimate standard input/output token cost with exact Decimal arithmetic."""

    snapshot = load_pricing_snapshot()
    common = {
        "currency": snapshot.currency,
        "pricing_snapshot_id": snapshot.pricing_snapshot_id,
        "pricing_source_url": snapshot.source_url,
        "pricing_consulted_on": snapshot.consulted_on,
    }
    if not call_succeeded:
        return TokenCostEstimate(
            cost_estimate=None,
            cost_unavailable_reason="model_call_failed",
            **common,
        )
    pricing = next(
        (entry for entry in snapshot.models if entry.model_id == model_id),
        None,
    )
    if pricing is None:
        return TokenCostEstimate(
            cost_estimate=None,
            cost_unavailable_reason="pricing_unavailable_for_model",
            **common,
        )
    if input_tokens is None or output_tokens is None:
        return TokenCostEstimate(
            cost_estimate=None,
            cost_unavailable_reason="token_usage_unavailable",
            **common,
        )
    input_cost = Decimal(input_tokens) * pricing.input_price_per_million_tokens
    output_cost = Decimal(output_tokens) * pricing.output_price_per_million_tokens
    total = (input_cost + output_cost) / Decimal(snapshot.unit_token_count)
    return TokenCostEstimate(
        cost_estimate=total.quantize(Decimal("0.000001")),
        cost_unavailable_reason=None,
        **common,
    )


def _snapshot_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "llm"
        / "anthropic_pricing.v1.json"
    )
