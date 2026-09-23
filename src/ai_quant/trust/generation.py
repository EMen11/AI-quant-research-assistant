"""Bounded structured-generation boundary with a deterministic fixture fake."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ai_quant.content_rules import CanonicalSummaryError, normalize_proposal_summary
from ai_quant.llm import LLMClient, SynthesisRequest
from ai_quant.model_calls import ModelCallMetadata, failed_model_call
from ai_quant.trust.models import (
    DraftProposal,
    EvidenceRecord,
    GenerationMetadata,
    GenerationParameter,
    PublicDemoFixture,
)


class GenerationError(RuntimeError):
    """Base error for the bounded structured-generation boundary."""

    error_code = "generation-error"

    def __init__(
        self,
        message: str,
        *,
        model_call: ModelCallMetadata | None = None,
    ) -> None:
        super().__init__(message)
        self.model_call = model_call
        self.status = "generation_failed" if model_call is None else model_call.status


class GenerationBudgetExceeded(GenerationError):
    """Raised before a call would exceed the configured call budget."""

    error_code = "generation-budget-exceeded"


class GenerationTimeout(GenerationError):
    """Raised when a completed call exceeds the configured time budget."""

    error_code = "generation-timeout"


class DraftSchemaError(GenerationError):
    """Raised when provider output does not match the closed proposal schema."""

    error_code = "generation-schema-error"


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
    model_call: ModelCallMetadata | None = None


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
    timeout_seconds: float = 15.0

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
            failed_call = (
                None
                if response.model_call is None
                else failed_model_call(
                    response.model_call,
                    status="timeout",
                    error_type="GenerationControllerTimeout",
                )
            )
            raise GenerationTimeout(
                f"Structured generation exceeded {self._budget.timeout_seconds:g} seconds.",
                model_call=failed_call,
            ) from None

        schema_is_invalid = False
        try:
            proposal = DraftProposal.model_validate_json(response.payload_json)
            proposal = normalize_proposal_summary(
                proposal,
                has_metrics=bool(allowed_metric_ids),
                has_evidence=bool(allowed_evidence_ids),
            )
            metadata = GenerationMetadata(
                provider=response.provider,
                model_id=response.model_id,
                parameters=response.parameters,
                prompt_version=response.prompt_version,
                response_id=response.response_id,
                generated_at=response.generated_at,
                model_call=response.model_call,
            )
        except (CanonicalSummaryError, ValidationError):
            schema_is_invalid = True
        if schema_is_invalid:
            failed_call = (
                None
                if response.model_call is None
                else failed_model_call(
                    response.model_call,
                    status="schema_error",
                    error_type="DraftSchemaValidationError",
                )
            )
            raise DraftSchemaError(
                "Structured generation response failed validation.",
                model_call=failed_call,
            ) from None
        return proposal, metadata


class FixtureDraftGenerator:
    """Offline fake that reads a versioned response fixture and never uses a network."""

    def __init__(
        self,
        fixture_path: Path,
        *,
        response_id: str,
        public_fixture: PublicDemoFixture | None = None,
    ) -> None:
        self._fixture_path = fixture_path
        self._response_id = response_id
        self._public_fixture = public_fixture
        self.call_count = 0

    @classmethod
    def valid(cls) -> FixtureDraftGenerator:
        """Build the human-approved, live-derived public demo fixture."""

        fixture_path = _fixture_path("llm/public_demo_live_v3_v1.json")
        fixture = PublicDemoFixture.model_validate_json(
            fixture_path.read_text(encoding="utf-8")
        )
        assert fixture.model_call.response_id is not None
        return cls(
            fixture_path,
            response_id=fixture.model_call.response_id,
            public_fixture=fixture,
        )

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

        if self._public_fixture is not None:
            fixture = self._public_fixture
            expected_evidence_ids = tuple(record.evidence_id for record in fixture.evidence)
            if allowed_metric_ids != fixture.allowed_metric_ids:
                raise ValueError("Controller metric allowlist differs from public fixture.")
            if allowed_evidence_ids != expected_evidence_ids:
                raise ValueError("Controller evidence allowlist differs from public fixture.")
            self.call_count += 1
            return StructuredGenerationResponse(
                payload_json=fixture.proposal.model_dump_json(),
                provider=fixture.provider,
                model_id=fixture.model_id,
                parameters=(
                    GenerationParameter(name="max-output-tokens", value=1_200),
                    GenerationParameter(
                        name="normalization-version",
                        value=fixture.normalization_version,
                    ),
                    GenerationParameter(
                        name="fixture-derivation",
                        value=fixture.fixture_derivation,
                    ),
                ),
                prompt_version=fixture.prompt_version,
                response_id=self._response_id,
                generated_at=datetime(
                    fixture.promotion_review.reviewed_on.year,
                    fixture.promotion_review.reviewed_on.month,
                    fixture.promotion_review.reviewed_on.day,
                    tzinfo=UTC,
                ),
                model_call=fixture.model_call,
            )

        # The fake deliberately cannot materialize records, validation or human review.
        del allowed_metric_ids, allowed_evidence_ids
        self.call_count += 1
        return StructuredGenerationResponse(
            payload_json=self._fixture_path.read_text(encoding="utf-8"),
            provider="offline-fixture",
            model_id="structured-fake-v1",
            parameters=(GenerationParameter(name="temperature", value=0.0),),
            prompt_version="trust-synthesis-v3",
            response_id=self._response_id,
            generated_at=datetime(2026, 9, 23, tzinfo=UTC),
            model_call=ModelCallMetadata(
                provider="offline-fixture",
                model_id="structured-fake-v1",
                prompt_version="trust-synthesis-v3",
                status="success",
                latency_ms=0.0,
                response_id=self._response_id,
                input_tokens=None,
                output_tokens=None,
                retry_count=0,
                error_type=None,
                cost_estimate=None,
                currency=None,
                pricing_source_url=None,
                pricing_valid_on=None,
                cost_unavailable_reason="Synthetic offline fixture has no provider billing.",
                response_origin="synthetic_offline_fixture",
            ),
        )

    def public_evidence_for(self, run_id: str) -> tuple[EvidenceRecord, ...]:
        """Return approved official evidence for this fixture's run, if available."""

        if self._public_fixture is None:
            return ()
        if self._public_fixture.run_id != run_id:
            raise ValueError("Public fixture evidence belongs to another run.")
        return self._public_fixture.evidence


class LLMStructuredDraftGenerator:
    """Adapt the canonical structured client to the existing Block 3 controller."""

    def __init__(self, client: LLMClient, request: SynthesisRequest) -> None:
        self._client = client
        self._request = request

    def generate(
        self,
        *,
        allowed_metric_ids: tuple[str, ...],
        allowed_evidence_ids: tuple[str, ...],
    ) -> StructuredGenerationResponse:
        if allowed_metric_ids != self._request.allowed_metric_ids:
            raise ValueError("Controller metric allowlist differs from synthesis request.")
        if allowed_evidence_ids != self._request.allowed_evidence_ids:
            raise ValueError("Controller evidence allowlist differs from synthesis request.")
        result = self._client.synthesize(self._request)
        return StructuredGenerationResponse(
            payload_json=result.payload_json,
            provider=result.metadata.provider,
            model_id=result.metadata.model_id,
            parameters=(
                GenerationParameter(
                    name="max-output-tokens",
                    value=self._request.limits.max_output_tokens,
                ),
            ),
            prompt_version=result.metadata.prompt_version,
            response_id=result.metadata.response_id or "response-unavailable",
            generated_at=datetime(2026, 9, 23, tzinfo=UTC),
            model_call=result.metadata,
        )


def _fixture_path(filename: str) -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / filename
