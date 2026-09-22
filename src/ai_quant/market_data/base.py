"""Minimal market-data interface and deterministic frozen provider."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


class MarketDataError(RuntimeError):
    """Raised when requested frozen market data is unavailable."""


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One immutable closing-price observation."""

    observed_on: date
    close: Decimal


@dataclass(frozen=True, slots=True)
class MarketSeries:
    """A frozen series returned by a market-data provider."""

    symbol: str
    currency: str
    provider: str
    points: tuple[PricePoint, ...]

    @property
    def latest(self) -> PricePoint:
        """Return the last observation in the frozen series."""

        if not self.points:
            raise MarketDataError(f"Frozen series {self.symbol!r} is empty.")
        return self.points[-1]


class MarketDataProvider(Protocol):
    """Boundary implemented by frozen and future live providers."""

    def get_series(self, symbols: Iterable[str]) -> tuple[MarketSeries, ...]:
        """Return market series for every requested symbol."""


class FrozenMarketDataProvider:
    """In-memory provider that never performs network access."""

    def __init__(self, series_by_symbol: Mapping[str, MarketSeries]) -> None:
        self._series_by_symbol = dict(series_by_symbol)

    def get_series(self, symbols: Iterable[str]) -> tuple[MarketSeries, ...]:
        """Return requested series or fail explicitly when one is absent."""

        requested = tuple(symbols)
        missing = [symbol for symbol in requested if symbol not in self._series_by_symbol]
        if missing:
            joined = ", ".join(missing)
            raise MarketDataError(f"Frozen market data unavailable for: {joined}.")
        return tuple(self._series_by_symbol[symbol] for symbol in requested)

    @classmethod
    def demo(cls) -> FrozenMarketDataProvider:
        """Create the small illustrative fixture displayed by the public demo."""

        observed_on = date(2026, 9, 18)
        series = {
            "DEMO-ALPHA": MarketSeries(
                symbol="DEMO-ALPHA",
                currency="CHF",
                provider="frozen-demo-fixture",
                points=(PricePoint(observed_on=observed_on, close=Decimal("100.00")),),
            ),
            "DEMO-BETA": MarketSeries(
                symbol="DEMO-BETA",
                currency="CHF",
                provider="frozen-demo-fixture",
                points=(PricePoint(observed_on=observed_on, close=Decimal("125.00")),),
            ),
        }
        return cls(series)
