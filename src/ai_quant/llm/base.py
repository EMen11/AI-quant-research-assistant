"""Minimal LLM interface and deterministic fake implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Text returned by an LLM implementation with its provider identity."""

    text: str
    provider: str


class LLMClient(Protocol):
    """Boundary implemented by deterministic fakes and future live clients."""

    def complete(self, prompt: str) -> LLMResponse:
        """Return a response for a prompt."""


class FakeLLM:
    """Deterministic LLM used by demo mode and automated tests."""

    def __init__(self, response_text: str = "Offline demo ready.") -> None:
        self._response_text = response_text
        self.call_count = 0

    def complete(self, prompt: str) -> LLMResponse:
        """Return a fixed response without performing any network request."""

        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        self.call_count += 1
        return LLMResponse(text=self._response_text, provider="fake")
