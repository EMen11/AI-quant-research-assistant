"""Closed, versioned contract for the Bachem/Siegfried analyst note."""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_quant.content_rules import (
    evidence_placeholder_ids,
    metric_placeholder_ids,
    numeric_literals,
)
from ai_quant.trust.models import Identifier, NonEmptyText, StrictModel

StatementKind = Literal[
    "sourced_fact",
    "calculated_metric",
    "analyst_interpretation",
    "limitation",
]

REQUIRED_LIMITATION_IDS = (
    "two-company-universe",
    "annual-data-only",
    "historical-closing-valuations",
    "no-consensus",
    "no-prediction",
    "bachem-published-pe-unavailable",
)

_PROHIBITED_RECOMMENDATION = re.compile(
    r"\b(?:buy|sell|hold|acheter|vendre|conserver)\b",
    flags=re.IGNORECASE,
)
_TARGET_PRICE = re.compile(
    r"\b(?:target price|price target|cours cible|objectif de cours)\b",
    flags=re.IGNORECASE,
)
_PREDICTION = re.compile(
    r"\b(?:share price|stock price|cours de (?:bourse|l.action))\b.{0,60}"
    r"\b(?:will|va|devrait|could|pourrait)\b",
    flags=re.IGNORECASE,
)
_PERSONALIZED_ADVICE = re.compile(
    r"\b(?:you should|vous devriez|for your portfolio|pour votre portefeuille|"
    r"suited to your|adapt[eé] à votre)\b",
    flags=re.IGNORECASE,
)


class MetricUse(StrictModel):
    """Generator-declared use of one authoritative metric record."""

    metric_id: Identifier
    value: float
    unit: NonEmptyText
    period: NonEmptyText


class EvidenceUse(StrictModel):
    """Generator-declared use of one allowlisted Evidence record."""

    evidence_id: Identifier
    exact_excerpt: Annotated[str, Field(min_length=1, max_length=4_000)]


class NoteStatement(StrictModel):
    """One typed note statement with explicit metric and Evidence bindings."""

    statement_id: Identifier
    kind: StatementKind
    text_template: Annotated[str, Field(min_length=1, max_length=1_000)]
    metric_uses: tuple[MetricUse, ...] = ()
    evidence_uses: tuple[EvidenceUse, ...] = ()
    uncertainty: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def references_match_kind_and_placeholders(self) -> NoteStatement:
        metric_ids = tuple(item.metric_id for item in self.metric_uses)
        evidence_ids = tuple(item.evidence_id for item in self.evidence_uses)
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("metric_uses must contain unique metric IDs.")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence_uses must contain unique Evidence IDs.")
        if tuple(metric_placeholder_ids(self.text_template)) != metric_ids:
            raise ValueError("Metric placeholders must match metric_uses in order.")
        if tuple(evidence_placeholder_ids(self.text_template)) != evidence_ids:
            raise ValueError("Evidence placeholders must match evidence_uses in order.")
        if numeric_literals(self.text_template):
            raise ValueError("Narrative text cannot contain free numeric literals.")
        if self.uncertainty is not None and numeric_literals(self.uncertainty):
            raise ValueError("Uncertainty text cannot contain free numeric literals.")
        if self.kind == "sourced_fact" and not self.evidence_uses:
            raise ValueError("sourced_fact statements require authorized Evidence.")
        if self.kind == "calculated_metric" and not self.metric_uses:
            raise ValueError("calculated_metric statements require an authorized metric.")
        if self.kind == "analyst_interpretation" and not (
            self.metric_uses or self.evidence_uses
        ):
            raise ValueError("analyst_interpretation statements require an explicit basis.")
        if self.kind == "limitation" and (self.metric_uses or self.evidence_uses):
            raise ValueError("Limitations are represented separately from claims.")
        _reject_prohibited_output(self.text_template)
        if self.uncertainty is not None:
            _reject_prohibited_output(self.uncertainty)
        return self


class NoteSection(StrictModel):
    """A mandatory analyst-note section containing typed statements."""

    title: NonEmptyText
    statements: Annotated[tuple[NoteStatement, ...], Field(min_length=1, max_length=2)]


class AnalystNoteSections(StrictModel):
    """The eleven mandatory sections of analyst_note.v1."""

    comparison_scope: NoteSection
    company_profiles: NoteSection
    growth_profitability: NoteSection
    cash_balance_capital_allocation: NoteSection
    relative_historical_valuation: NoteSection
    sustainability_comparability: NoteSection
    favorable_arguments: NoteSection
    risks_attention: NoteSection
    catalysts: NoteSection
    monitoring_indicators: NoteSection
    comparative_conclusion: NoteSection

    def ordered(self) -> tuple[NoteSection, ...]:
        """Return sections in the fixed editorial order."""

        return (
            self.comparison_scope,
            self.company_profiles,
            self.growth_profitability,
            self.cash_balance_capital_allocation,
            self.relative_historical_valuation,
            self.sustainability_comparability,
            self.favorable_arguments,
            self.risks_attention,
            self.catalysts,
            self.monitoring_indicators,
            self.comparative_conclusion,
        )


class NoteLimitation(StrictModel):
    """A mandatory, machine-checkable limitation visible in the note."""

    limitation_id: Identifier
    text: NonEmptyText

    @model_validator(mode="after")
    def text_is_non_numeric_and_non_advisory(self) -> NoteLimitation:
        if numeric_literals(self.text):
            raise ValueError("Limitation text cannot contain free numeric literals.")
        _reject_prohibited_output(self.text)
        return self


class AnalystNoteV1(StrictModel):
    """Versioned Research Note proposal; validation and review remain external."""

    schema_version: Literal["analyst-note.v1"] = "analyst-note.v1"
    note_id: Identifier
    run_id: Identifier
    comparison_as_of: date
    data_period: Literal["FY2021-FY2025"]
    executive_summary: NonEmptyText
    sections: AnalystNoteSections
    limitations: Annotated[tuple[NoteLimitation, ...], Field(min_length=1)]
    ai_assistance_disclosure: NonEmptyText

    @model_validator(mode="after")
    def note_invariants(self) -> AnalystNoteV1:
        if numeric_literals(self.executive_summary):
            raise ValueError("Executive summary cannot contain free numeric literals.")
        _reject_prohibited_output(self.executive_summary)
        _reject_prohibited_output(self.ai_assistance_disclosure)

        statements = tuple(
            statement
            for section in self.sections.ordered()
            for statement in section.statements
        )
        if len(statements) > 12:
            raise ValueError("analyst_note.v1 supports at most twelve statements.")
        statement_ids = tuple(item.statement_id for item in statements)
        if len(set(statement_ids)) != len(statement_ids):
            raise ValueError("statement_id values must be unique.")

        limitation_ids = tuple(item.limitation_id for item in self.limitations)
        if len(set(limitation_ids)) != len(limitation_ids):
            raise ValueError("limitation_id values must be unique.")
        if limitation_ids != REQUIRED_LIMITATION_IDS:
            raise ValueError(
                "analyst_note.v1 must represent every required limitation in fixed order."
            )
        return self

    @property
    def statements(self) -> tuple[NoteStatement, ...]:
        """Return every statement in deterministic section order."""

        return tuple(
            statement
            for section in self.sections.ordered()
            for statement in section.statements
        )


def _reject_prohibited_output(text: str) -> None:
    if _PROHIBITED_RECOMMENDATION.search(text):
        raise ValueError("BUY/SELL/HOLD-style recommendations are forbidden.")
    if _TARGET_PRICE.search(text):
        raise ValueError("Target prices are forbidden.")
    if _PREDICTION.search(text):
        raise ValueError("Share-price predictions are forbidden.")
    if _PERSONALIZED_ADVICE.search(text):
        raise ValueError("Personalized investment recommendations are forbidden.")
