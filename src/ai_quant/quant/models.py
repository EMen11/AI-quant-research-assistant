"""Immutable domain models for deterministic quantitative analysis."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import pandas as pd


class QuantValidationError(ValueError):
    """Raised when a quantitative input violates an explicit contract."""


@dataclass(frozen=True, slots=True)
class OptimizationConstraints:
    """Long-only per-asset bounds used by the optimizer."""

    minimum_weight: float = 0.0
    maximum_weight: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_weight <= self.maximum_weight <= 1.0:
            raise QuantValidationError("Weights must satisfy 0 <= minimum <= maximum <= 1.")


@dataclass(frozen=True, slots=True)
class PortfolioDefinition:
    """Versionable portfolio input; instruments are never inferred by an LLM."""

    portfolio_id: str
    instruments: tuple[str, ...]
    base_currency: str
    analysis_cutoff: datetime
    weighting_rule: Literal["equal_weight", "custom"] = "equal_weight"
    initial_weights: tuple[tuple[str, float], ...] | None = None
    benchmark_id: str | None = None
    constraints: OptimizationConstraints = OptimizationConstraints()

    def __post_init__(self) -> None:
        if not self.portfolio_id.strip():
            raise QuantValidationError("portfolio_id must not be empty.")
        if not 1 <= len(self.instruments) <= 3:
            raise QuantValidationError("The Block 2 portfolio must contain one to three assets.")
        if len(set(self.instruments)) != len(self.instruments):
            raise QuantValidationError("Portfolio instruments must be unique.")
        if any(not instrument.strip() for instrument in self.instruments):
            raise QuantValidationError("Portfolio instruments must not be empty.")
        if not self.base_currency.strip():
            raise QuantValidationError("base_currency must not be empty.")
        if self.analysis_cutoff.tzinfo is None:
            raise QuantValidationError("analysis_cutoff must be timezone-aware.")
        if self.weighting_rule == "custom":
            if self.initial_weights is None:
                raise QuantValidationError("Custom weighting requires initial_weights.")
            weights = dict(self.initial_weights)
            if len(weights) != len(self.initial_weights) or set(weights) != set(self.instruments):
                raise QuantValidationError("Custom weights must cover every instrument exactly once.")
            if any(
                not math.isfinite(weight)
                or weight < self.constraints.minimum_weight
                or weight > self.constraints.maximum_weight
                for weight in weights.values()
            ):
                raise QuantValidationError("Custom weights must be finite and respect bounds.")
            if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12):
                raise QuantValidationError("Custom weights must sum to 1.")


@dataclass(frozen=True, slots=True)
class RiskFreeRate:
    """Dated annual risk-free-rate assumption, expressed as a decimal rate."""

    annual_rate: float
    currency: str
    as_of: date
    source: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.annual_rate) or self.annual_rate <= -1.0:
            raise QuantValidationError("annual_rate must be finite and greater than -100%.")
        if not self.currency.strip() or not self.source.strip():
            raise QuantValidationError("Risk-free currency and source are required.")


@dataclass(frozen=True, slots=True)
class PriceObservation:
    """One adjusted-close observation; None records an explicit missing value."""

    observed_on: date
    instrument: str
    adjusted_close: Decimal | None

    def __post_init__(self) -> None:
        if not self.instrument.strip():
            raise QuantValidationError("Price observation instrument must not be empty.")
        if self.adjusted_close is not None and self.adjusted_close <= 0:
            raise QuantValidationError("Adjusted prices must be strictly positive.")


@dataclass(frozen=True, slots=True)
class MissingPrice:
    """Explicit lineage record for an unavailable adjusted close."""

    observed_on: date
    instrument: str
    reason: str = "missing_in_fixture"


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Immutable prices and lineage used by exactly one quantitative analysis."""

    snapshot_id: str
    instruments: tuple[str, ...]
    observations: tuple[PriceObservation, ...]
    data_start: date
    data_end: date
    frequency: Literal["daily"]
    base_currency: str
    currencies: tuple[tuple[str, str], ...]
    provider: str
    analysis_cutoff: datetime
    retrieved_at: datetime
    price_field: Literal["adjusted_close"]
    adjustment_policy: str
    missing_values: tuple[MissingPrice, ...]
    content_sha256: str
    artifact_uri: str
    schema_version: str = "market_snapshot_v1"

    def __post_init__(self) -> None:
        if self.analysis_cutoff.tzinfo is None or self.retrieved_at.tzinfo is None:
            raise QuantValidationError("analysis_cutoff and retrieved_at must be timezone-aware.")
        if self.data_start > self.data_end:
            raise QuantValidationError("data_start must not be after data_end.")
        if not self.observations:
            raise QuantValidationError("A market snapshot must contain observations.")
        if len(set(self.instruments)) != len(self.instruments) or not self.instruments:
            raise QuantValidationError("Snapshot instruments must be non-empty and unique.")
        if any(item.instrument not in self.instruments for item in self.observations):
            raise QuantValidationError("Snapshot observation contains an unknown instrument.")
        if set(dict(self.currencies)) != set(self.instruments):
            raise QuantValidationError("Snapshot currencies must cover every instrument.")
        expected_missing = tuple(
            MissingPrice(item.observed_on, item.instrument)
            for item in self.observations
            if item.adjusted_close is None
        )
        if self.missing_values != expected_missing:
            raise QuantValidationError("Snapshot missing-value lineage is inconsistent.")
        if self.content_sha256 != self.compute_content_sha256():
            raise QuantValidationError("Snapshot content hash does not match its canonical payload.")

    @classmethod
    def create(
        cls,
        *,
        snapshot_id: str,
        instruments: tuple[str, ...],
        observations: tuple[PriceObservation, ...],
        base_currency: str,
        currencies: tuple[tuple[str, str], ...],
        provider: str,
        analysis_cutoff: datetime,
        retrieved_at: datetime,
        adjustment_policy: str,
        artifact_uri: str,
    ) -> MarketSnapshot:
        """Create a snapshot and derive its missing-value records and canonical hash."""

        ordered = tuple(sorted(observations, key=lambda item: (item.observed_on, item.instrument)))
        if not ordered:
            raise QuantValidationError("A market snapshot must contain observations.")
        missing = tuple(
            MissingPrice(item.observed_on, item.instrument)
            for item in ordered
            if item.adjusted_close is None
        )
        data_start = min(item.observed_on for item in ordered)
        data_end = max(item.observed_on for item in ordered)
        ordered_currencies = tuple(sorted(currencies))
        canonical_payload = _canonical_snapshot_payload(
            analysis_cutoff=analysis_cutoff,
            adjustment_policy=adjustment_policy,
            artifact_uri=artifact_uri,
            base_currency=base_currency,
            currencies=ordered_currencies,
            data_end=data_end,
            data_start=data_start,
            frequency="daily",
            instruments=instruments,
            missing_values=missing,
            observations=ordered,
            price_field="adjusted_close",
            provider=provider,
            retrieved_at=retrieved_at,
            schema_version="market_snapshot_v1",
        )
        return cls(
            snapshot_id=snapshot_id,
            instruments=instruments,
            observations=ordered,
            data_start=data_start,
            data_end=data_end,
            frequency="daily",
            base_currency=base_currency,
            currencies=ordered_currencies,
            provider=provider,
            analysis_cutoff=analysis_cutoff,
            retrieved_at=retrieved_at,
            price_field="adjusted_close",
            adjustment_policy=adjustment_policy,
            missing_values=missing,
            content_sha256=hashlib.sha256(canonical_payload).hexdigest(),
            artifact_uri=artifact_uri,
        )

    def canonical_payload(self) -> bytes:
        """Return the UTF-8 canonical JSON bytes covered by ``content_sha256``."""

        return _canonical_snapshot_payload(
            analysis_cutoff=self.analysis_cutoff,
            adjustment_policy=self.adjustment_policy,
            artifact_uri=self.artifact_uri,
            base_currency=self.base_currency,
            currencies=self.currencies,
            data_end=self.data_end,
            data_start=self.data_start,
            frequency=self.frequency,
            instruments=self.instruments,
            missing_values=self.missing_values,
            observations=self.observations,
            price_field=self.price_field,
            provider=self.provider,
            retrieved_at=self.retrieved_at,
            schema_version=self.schema_version,
        )

    def compute_content_sha256(self) -> str:
        """Hash the documented canonical serialization of prices and metadata."""

        return hashlib.sha256(self.canonical_payload()).hexdigest()

    @property
    def rows(self) -> int:
        """Return the number of long-form price observations, including explicit nulls."""

        return len(self.observations)

    def price_frame(self) -> pd.DataFrame:
        """Return a new adjusted-price frame; callers cannot mutate the snapshot."""

        records = [
            {
                "date": item.observed_on,
                "instrument": item.instrument,
                "adjusted_close": (
                    float(item.adjusted_close) if item.adjusted_close is not None else math.nan
                ),
            }
            for item in self.observations
        ]
        frame = pd.DataFrame.from_records(records)
        if frame.duplicated(subset=["date", "instrument"]).any():
            raise QuantValidationError("Snapshot contains duplicate date/instrument observations.")
        return (
            frame.pivot(index="date", columns="instrument", values="adjusted_close")
            .reindex(columns=self.instruments)
            .sort_index()
        )


@dataclass(frozen=True, slots=True)
class ReturnMatrix:
    """The one immutable complete-case simple-return matrix for an analysis."""

    dates: tuple[date, ...]
    instruments: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    dropped_dates: tuple[date, ...]
    frequency: Literal["daily"] = "daily"
    convention: Literal["simple"] = "simple"

    def __post_init__(self) -> None:
        if len(self.dates) != len(self.values):
            raise QuantValidationError("Return dates and rows must have equal length.")
        if any(len(row) != len(self.instruments) for row in self.values):
            raise QuantValidationError("Every return row must cover every instrument.")
        if any(not math.isfinite(value) for row in self.values for value in row):
            raise QuantValidationError("ReturnMatrix values must all be finite.")

    def to_frame(self) -> pd.DataFrame:
        """Return a defensive DataFrame copy for vectorized pure calculations."""

        return pd.DataFrame(self.values, index=self.dates, columns=self.instruments, dtype=float)

    @property
    def content_sha256(self) -> str:
        """Hash dates, instruments and values for reuse/audit diagnostics."""

        payload = json.dumps(
            {
                "dates": [item.isoformat() for item in self.dates],
                "instruments": self.instruments,
                "values": self.values,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A scalar metric with explicit interpretation metadata."""

    value: float
    unit: str
    formula_version: str
    horizon: str
    confidence_level: float | None = None


@dataclass(frozen=True, slots=True)
class MatrixValue:
    """Immutable labelled covariance or correlation matrix."""

    labels: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    unit: str
    formula_version: str


def _canonical_snapshot_payload(
    *,
    analysis_cutoff: datetime,
    adjustment_policy: str,
    artifact_uri: str,
    base_currency: str,
    currencies: tuple[tuple[str, str], ...],
    data_end: date,
    data_start: date,
    frequency: str,
    instruments: tuple[str, ...],
    missing_values: tuple[MissingPrice, ...],
    observations: tuple[PriceObservation, ...],
    price_field: str,
    provider: str,
    retrieved_at: datetime,
    schema_version: str,
) -> bytes:
    payload = {
        "analysis_cutoff": analysis_cutoff.isoformat(),
        "adjustment_policy": adjustment_policy,
        "artifact_uri": artifact_uri,
        "base_currency": base_currency,
        "currencies": list(currencies),
        "data_end": data_end.isoformat(),
        "data_start": data_start.isoformat(),
        "frequency": frequency,
        "instruments": list(instruments),
        "missing_values": [
            {
                "instrument": item.instrument,
                "observed_on": item.observed_on.isoformat(),
                "reason": item.reason,
            }
            for item in missing_values
        ],
        "observations": [
            {
                "adjusted_close": (
                    format(item.adjusted_close, "f")
                    if item.adjusted_close is not None
                    else None
                ),
                "instrument": item.instrument,
                "observed_on": item.observed_on.isoformat(),
            }
            for item in observations
        ],
        "price_field": price_field,
        "provider": provider,
        "retrieved_at": retrieved_at.isoformat(),
        "schema_version": schema_version,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
