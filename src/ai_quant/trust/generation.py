"""Bounded structured-generation boundary with a deterministic fixture fake."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ai_quant.trust.models import (
    DraftProposal,
    GenerationMetadata,
    GenerationParameter,
)


class GenerationError(RuntimeError):
    """Base error for the bounded structured-generation boundary."""


class GenerationBudgetExceeded(GenerationError):
    """Raised before a call would exceed the configured call budget."""


class GenerationTimeout(GenerationError):
    """Raised when a completed call exceeds the configured time budget."""


class DraftSchemaError(GenerationError):
    """Raised when provider output does not match the closed proposal schema."""


@dataclass(frozen=True, slots=True)
class StructuredGenerationResponse:
    """Provider-neutral transport response, before schema validation."""

    payload_json: str
    provider: str
    model_id: str
    parameters: tuple[GenerationParameter, ...]
    prompt_version: str
    response_id: str
    generated_at: datetime


class StructuredDraftGenerator(Protocol):
    """Minimal interface for one structured narrative proposal call."""

    def generate(
        self,
        *,
        allowed_metric_ids: tuple[str, ...],
        allowed_evidence_ids: tuple[str, ...],
    ) -> StructuredGenerationResponse:
        """Return untrusted JSON containing only proposal fields."""


@dataclass(frozen=True, slots=True)
class GenerationBudget:
    """Hard bounds for one workflow generation phase."""

    max_calls: int = 1
    timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_calls < 1:
            raise ValueError("max_calls must be at least one.")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")


class GenerationController:
    """Enforce a call budget, timeout and exact schema at one boundary."""

    def __init__(
        self,
        generator: StructuredDraftGenerator,
        budget: GenerationBudget,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._generator = generator
        self._budget = budget
        self._clock = clock
        self._calls_used = 0

    @property
    def calls_used(self) -> int:
        """Return the number of provider calls attempted by this controller."""

        return self._calls_used

    def generate(
        self,
        *,
        allowed_metric_ids: tuple[str, ...],
        allowed_evidence_ids: tuple[str, ...],
    ) -> tuple[DraftProposal, GenerationMetadata]:
        """Make one bounded call, then validate its JSON and audit metadata."""

        if self._calls_used >= self._budget.max_calls:
            raise GenerationBudgetExceeded(
                f"Generation call budget exhausted ({self._budget.max_calls} call maximum)."
            )

        started_at = self._clock()
        self._calls_used += 1
        response = self._generator.generate(
            allowed_metric_ids=allowed_metric_ids,
            allowed_evidence_ids=allowed_evidence_ids,
        )
        elapsed = self._clock() - started_at
        if elapsed > self._budget.timeout_seconds:
            raise GenerationTimeout(
                f"Structured generation exceeded {self._budget.timeout_seconds:g} seconds."
            )

        try:
            proposal = DraftProposal.model_validate_json(response.payload_json)
            metadata = GenerationMetadata(
                provider=response.provider,
                model_id=response.model_id,
                parameters=response.parameters,
                prompt_version=response.prompt_version,
                response_id=response.response_id,
                generated_at=response.generated_at,
            )
        except ValidationError as exc:
            raise DraftSchemaError("Structured generation response failed validation.") from exc
        return proposal, metadata


class FixtureDraftGenerator:
    """Offline fake that reads a versioned response fixture and never uses a network."""

    def __init__(self, fixture_path: Path, *, response_id: str) -> None:
        self._fixture_path = fixture_path
        self._response_id = response_id
        self.call_count = 0

    @classmethod
    def valid(cls) -> FixtureDraftGenerator:
        """Build the valid demo scenario fake."""

        return cls(_fixture_path("trust_valid_draft_v1.json"), response_id="response-demo-valid-v1")

    @classmethod
    def blocked(cls) -> FixtureDraftGenerator:
        """Build the blocked demo scenario fake."""

        return cls(
            _fixture_path("trust_blocked_draft_v1.json"),
            response_id="response-demo-blocked-v1",
        )

    def generate(
        self,
        *,
        allowed_metric_ids: tuple[str, ...],
        allowed_evidence_ids: tuple[str, ...],
    ) -> StructuredGenerationResponse:
        """Return fixture JSON; allowed IDs are inputs, never generated authority."""

        # The fake deliberately cannot materialize records, validation or human review.
        del allowed_metric_ids, allowed_evidence_ids
        self.call_count += 1
        return StructuredGenerationResponse(
            payload_json=self._fixture_path.read_text(encoding="utf-8"),
            provider="offline-fixture",
            model_id="structured-fake-v1",
            parameters=(GenerationParameter(name="temperature", value=0.0),),
            prompt_version="trust-boundary-v1",
            response_id=self._response_id,
            generated_at=datetime(2026, 9, 23, tzinfo=UTC),
        )


def _fixture_path(filename: str) -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / filename
