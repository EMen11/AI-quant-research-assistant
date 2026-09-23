"""Canonical structured LLM clients and deterministic compatibility fake."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_quant.llm.anthropic import (
    AnthropicLLMClient,
    AnthropicSDKTransport,
    AnthropicTransport,
    AnthropicTransportRequest,
    AnthropicTransportResponse,
)
from ai_quant.llm.base import (
    FakeLLM,
    FakeLLMClient,
    LLMAllowlistError,
    LLMClient,
    LLMClientError,
    LLMEvidenceInput,
    LLMMetricInput,
    LLMProviderError,
    LLMResponse,
    LLMSchemaError,
    LLMTimeoutError,
    PublicLLMFailure,
    SynthesisLimits,
    SynthesisRequest,
    SynthesisResult,
    TextLLMClient,
)

if TYPE_CHECKING:
    from ai_quant.config import Settings


def client_from_settings(settings: Settings) -> LLMClient:
    """Construct the offline fake in demo and initialize Anthropic only in live mode."""

    from ai_quant.config import AppMode

    if settings.app_mode is AppMode.DEMO:
        return FakeLLMClient()
    if settings.anthropic_api_key is None or settings.anthropic_model is None:
        raise ValueError("Live settings require an Anthropic key and model.")
    return AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )

__all__ = [
    "AnthropicLLMClient",
    "AnthropicSDKTransport",
    "AnthropicTransport",
    "AnthropicTransportRequest",
    "AnthropicTransportResponse",
    "FakeLLM",
    "FakeLLMClient",
    "LLMAllowlistError",
    "LLMClient",
    "LLMClientError",
    "LLMEvidenceInput",
    "LLMMetricInput",
    "LLMProviderError",
    "PublicLLMFailure",
    "LLMResponse",
    "LLMSchemaError",
    "LLMTimeoutError",
    "SynthesisLimits",
    "SynthesisRequest",
    "SynthesisResult",
    "TextLLMClient",
    "client_from_settings",
]
