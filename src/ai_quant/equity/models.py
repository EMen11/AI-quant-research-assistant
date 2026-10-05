"""Immutable Equity Research records with field-level lineage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

FORMULA_VERSION = "equity-formulas.v1"

MetricStatus = Literal["reported", "calculated", "unavailable", "not_comparable"]
SourceMethod = Literal["reported", "calculated"]
Scope2Method = Literal["location_based", "market_based", "not_applicable"]
AssuranceStatus = Literal["reasonable", "limited", "none", "not_disclosed"]
ConcordanceStatus = Literal["pass", "mismatch", "unavailable"]


class EquityValidationError(ValueError):
    """Raised when an Equity record violates an explicit data contract."""


@dataclass(frozen=True, slots=True)
class Company:
    """One issuer in the explicitly bounded comparison universe."""

    company_id: str
    ticker: str
    name: str

    def __post_init__(self) -> None:
        _require_text(self.company_id, "company_id")
        _require_text(self.ticker, "ticker")
        _require_text(self.name, "name")


@dataclass(frozen=True, slots=True)
class FiscalPeriod:
    """A fiscal year with an explicit closing date."""

    fiscal_year: int
    ended_on: date

    def __post_init__(self) -> None:
        if not 1900 <= self.fiscal_year <= 2200:
            raise EquityValidationError("fiscal_year is outside the supported range.")
        if self.ended_on.year != self.fiscal_year:
            raise EquityValidationError("ended_on must fall within fiscal_year.")


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Field-level route back to the exact source document and extraction method."""

    source_id: str
    document: str
    fiscal_year: int
    field: str
    source_unit: str
    method: SourceMethod
    source_uri: str
    document_sha256: str
    page: int | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.source_id, "source_id"),
            (self.document, "document"),
            (self.field, "field"),
            (self.source_unit, "source_unit"),
            (self.source_uri, "source_uri"),
        ):
            _require_text(value, label)
        if not 1900 <= self.fiscal_year <= 2200:
            raise EquityValidationError("source fiscal_year is outside the supported range.")
        if self.page is not None and self.page < 1:
            raise EquityValidationError("source page must be positive when provided.")
        if len(self.document_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.document_sha256
        ):
            raise EquityValidationError("document_sha256 must be a lowercase SHA-256 digest.")


@dataclass(frozen=True, slots=True)
class Formula:
    """Versioned deterministic transformation applied by Python."""

    formula_id: str
    expression: str
    version: str = FORMULA_VERSION

    def __post_init__(self) -> None:
        _require_text(self.formula_id, "formula_id")
        _require_text(self.expression, "expression")
        _require_text(self.version, "formula version")


@dataclass(frozen=True, slots=True)
class MetricValue:
    """One reported or calculated value with explicit availability and provenance."""

    metric_id: str
    company_id: str
    fiscal_year: int
    name: str
    value: Decimal | None
    unit: str
    status: MetricStatus
    sources: tuple[SourceReference, ...] = ()
    formula: Formula | None = None
    input_metric_ids: tuple[str, ...] = ()
    note: str | None = None
    scope2_method: Scope2Method | None = None
    assurance: AssuranceStatus | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.metric_id, "metric_id"),
            (self.company_id, "company_id"),
            (self.name, "metric name"),
            (self.unit, "metric unit"),
        ):
            _require_text(value, label)
        if not 1900 <= self.fiscal_year <= 2200:
            raise EquityValidationError("metric fiscal_year is outside the supported range.")
        if self.value is not None and not self.value.is_finite():
            raise EquityValidationError("metric value must be finite when provided.")
        if self.status in ("unavailable", "not_comparable") and self.value is not None:
            raise EquityValidationError(f"{self.status} metrics cannot carry a numeric value.")
        if self.status in ("reported", "calculated") and self.value is None:
            raise EquityValidationError(f"{self.status} metrics require a numeric value.")
        if self.status == "reported" and not self.sources:
            raise EquityValidationError("reported metrics require field-level provenance.")
        if self.status == "reported" and self.formula is not None:
            raise EquityValidationError("reported metrics cannot carry a calculation formula.")
        if self.status == "calculated":
            if self.formula is None or not self.input_metric_ids:
                raise EquityValidationError(
                    "calculated metrics require a formula and input metric IDs."
                )
            if not self.sources:
                raise EquityValidationError(
                    "calculated metrics require provenance inherited from their inputs."
                )
        if self.formula is not None and not self.input_metric_ids:
            raise EquityValidationError("formula-bearing metrics require input metric IDs.")
        if len(set(self.input_metric_ids)) != len(self.input_metric_ids):
            raise EquityValidationError("input_metric_ids must be unique.")
        if len({source.source_id for source in self.sources}) != len(self.sources):
            raise EquityValidationError("metric source references must be unique.")
        if self.note is not None:
            _require_text(self.note, "metric note")

    @property
    def is_available(self) -> bool:
        """Return whether this metric carries a usable numeric value."""

        return self.status in ("reported", "calculated")


@dataclass(frozen=True, slots=True)
class ConcordanceCheck:
    """Deterministic comparison between a source ratio/value and its recomputation."""

    check_id: str
    company_id: str
    fiscal_year: int
    name: str
    status: ConcordanceStatus
    source_metric_id: str
    recomputed_metric_id: str
    source_value: Decimal | None
    recomputed_value: Decimal | None
    absolute_difference: Decimal | None
    tolerance: Decimal
    unit: str
    note: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.check_id, "check_id"),
            (self.company_id, "company_id"),
            (self.name, "check name"),
            (self.source_metric_id, "source_metric_id"),
            (self.recomputed_metric_id, "recomputed_metric_id"),
            (self.unit, "check unit"),
            (self.note, "check note"),
        ):
            _require_text(value, label)
        if self.tolerance < 0:
            raise EquityValidationError("concordance tolerance cannot be negative.")
        values = (self.source_value, self.recomputed_value, self.absolute_difference)
        if any(value is not None and not value.is_finite() for value in values):
            raise EquityValidationError("concordance values must be finite.")
        if self.status == "unavailable" and any(value is not None for value in values):
            raise EquityValidationError("unavailable concordance checks cannot carry values.")
        if self.status in ("pass", "mismatch") and any(value is None for value in values):
            raise EquityValidationError("completed concordance checks require all values.")


@dataclass(frozen=True, slots=True)
class FundamentalAnalysis:
    """Immutable Phase 3 result containing inputs, derived values, and concordance checks."""

    source_metrics: tuple[MetricValue, ...]
    derived_metrics: tuple[MetricValue, ...]
    concordance_checks: tuple[ConcordanceCheck, ...]
    periods: tuple[int, ...]
    formula_version: str = FORMULA_VERSION

    def __post_init__(self) -> None:
        if self.periods != tuple(range(2021, 2026)):
            raise EquityValidationError("Phase 3 periods must be exactly FY2021-FY2025.")
        metric_ids = [item.metric_id for item in (*self.source_metrics, *self.derived_metrics)]
        if len(metric_ids) != len(set(metric_ids)):
            raise EquityValidationError("Phase 3 metric IDs must be unique.")
        check_ids = [item.check_id for item in self.concordance_checks]
        if len(check_ids) != len(set(check_ids)):
            raise EquityValidationError("Phase 3 concordance check IDs must be unique.")

    @property
    def metrics(self) -> tuple[MetricValue, ...]:
        """Return source and calculated metrics in one immutable collection."""

        return self.source_metrics + self.derived_metrics

    def metric(self, company_id: str, fiscal_year: int, name: str) -> MetricValue:
        """Return one source or derived metric by its stable business coordinates."""

        matches = tuple(
            item
            for item in self.metrics
            if item.company_id == company_id
            and item.fiscal_year == fiscal_year
            and item.name == name
        )
        if len(matches) != 1:
            raise KeyError(f"Metric not found: {company_id} FY{fiscal_year} {name}")
        return matches[0]


def unavailable_metric(
    *,
    metric_id: str,
    company_id: str,
    fiscal_year: int,
    name: str,
    unit: str,
    note: str,
    status: Literal["unavailable", "not_comparable"] = "unavailable",
    sources: tuple[SourceReference, ...] = (),
    input_metric_ids: tuple[str, ...] = (),
    formula_id: str | None = None,
    expression: str | None = None,
) -> MetricValue:
    """Create an explicit missing/non-comparable record; missing never becomes zero."""

    if (formula_id is None) != (expression is None):
        raise EquityValidationError(
            "unavailable metric formula_id and expression must be provided together."
        )
    formula = (
        Formula(formula_id=formula_id, expression=expression)
        if formula_id is not None and expression is not None
        else None
    )
    return MetricValue(
        metric_id=metric_id,
        company_id=company_id,
        fiscal_year=fiscal_year,
        name=name,
        value=None,
        unit=unit,
        status=status,
        sources=sources,
        formula=formula,
        input_metric_ids=input_metric_ids,
        note=note,
    )


def calculated_metric(
    *,
    metric_id: str,
    company_id: str,
    fiscal_year: int,
    name: str,
    value: Decimal,
    unit: str,
    formula_id: str,
    expression: str,
    inputs: tuple[MetricValue, ...],
    note: str | None = None,
    scope2_method: Scope2Method | None = None,
    assurance: AssuranceStatus | None = None,
) -> MetricValue:
    """Build a calculated metric and inherit de-duplicated source lineage."""

    source_by_id = {
        source.source_id: source for item in inputs for source in item.sources
    }
    return MetricValue(
        metric_id=metric_id,
        company_id=company_id,
        fiscal_year=fiscal_year,
        name=name,
        value=value,
        unit=unit,
        status="calculated",
        sources=tuple(source_by_id[key] for key in sorted(source_by_id)),
        formula=Formula(formula_id=formula_id, expression=expression),
        input_metric_ids=tuple(item.metric_id for item in inputs),
        note=note,
        scope2_method=scope2_method,
        assurance=assurance,
    )


def require_compatible_inputs(*metrics: MetricValue) -> None:
    """Reject calculations that silently mix issuers."""

    if not metrics:
        raise EquityValidationError("at least one metric input is required.")
    if len({metric.company_id for metric in metrics}) != 1:
        raise EquityValidationError("calculation inputs must belong to the same company.")


def merged_sources(metrics: tuple[MetricValue, ...]) -> tuple[SourceReference, ...]:
    """Return deterministically ordered, de-duplicated input provenance."""

    source_by_id = {
        source.source_id: source for metric in metrics for source in metric.sources
    }
    return tuple(source_by_id[key] for key in sorted(source_by_id))


def _require_text(value: str, label: str) -> None:
    if not value.strip():
        raise EquityValidationError(f"{label} must not be empty.")
