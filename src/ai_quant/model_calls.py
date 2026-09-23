"""Provider-neutral, secret-free metadata for one model call attempt."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelCallMetadata(BaseModel):
    """Audit metadata for a success or failure; prompts and secrets are excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["model-call-metadata.v1"] = "model-call-metadata.v1"
    provider: str = Field(
        min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    model_id: str = Field(
        min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    prompt_version: str = Field(
        min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    status: Literal["success", "provider_error", "timeout", "schema_error", "allowlist_error"]
    latency_ms: float = Field(ge=0)
    response_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    provider_request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    http_status: int | None = Field(default=None, ge=100, le=599)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    stop_reason: Literal[
        "end_turn",
        "max_tokens",
        "stop_sequence",
        "tool_use",
        "pause_turn",
        "refusal",
        "model_context_window_exceeded",
    ] | None = None
    retry_count: int | None = Field(default=None, ge=0)
    error_type: str | None = Field(default=None, min_length=1, max_length=120)
    cost_estimate: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    pricing_source_url: str | None = Field(default=None, pattern=r"^https://")
    pricing_valid_on: date | None = None
    pricing_snapshot_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    cost_unavailable_reason: str | None = Field(default=None, min_length=1, max_length=500)
    response_origin: Literal[
        "deterministic_fake",
        "synthetic_offline_fixture",
        "mocked_provider",
        "live_provider",
    ]

    @model_validator(mode="after")
    def pricing_fields_are_consistent(self) -> ModelCallMetadata:
        expected_total = (
            None
            if self.input_tokens is None or self.output_tokens is None
            else self.input_tokens + self.output_tokens
        )
        if self.total_tokens is not None and self.total_tokens != expected_total:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens.")
        if self.cost_estimate is None:
            if self.cost_unavailable_reason is None:
                raise ValueError("Unknown cost requires cost_unavailable_reason.")
            provenance = (
                self.currency,
                self.pricing_source_url,
                self.pricing_valid_on,
                self.pricing_snapshot_id,
            )
            if any(value is not None for value in provenance) and any(
                value is None for value in provenance
            ):
                raise ValueError("Partial pricing provenance is not allowed.")
        else:
            if any(
                value is None
                for value in (
                    self.currency,
                    self.pricing_source_url,
                    self.pricing_valid_on,
                    self.pricing_snapshot_id,
                )
            ):
                raise ValueError("A cost estimate requires currency and pricing provenance.")
            if self.cost_unavailable_reason is not None:
                raise ValueError("An estimated cost cannot have an unavailable reason.")
        if self.status == "success" and self.error_type is not None:
            raise ValueError("Successful calls cannot carry an error_type.")
        if self.status != "success" and self.error_type is None:
            raise ValueError("Failed calls require a cleaned error_type.")
        return self


def failed_model_call(
    metadata: ModelCallMetadata,
    *,
    status: Literal["provider_error", "timeout", "schema_error", "allowlist_error"],
    error_type: str,
) -> ModelCallMetadata:
    """Return a revalidated failure projection without prompts or raw exceptions."""

    values = metadata.model_dump()
    values.update(status=status, error_type=error_type)
    return ModelCallMetadata.model_validate(values)
