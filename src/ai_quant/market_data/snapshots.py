"""Frozen snapshot provider and one-snapshot-per-run guard."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from ai_quant.market_data.base import MarketDataError
from ai_quant.quant.models import MarketSnapshot, PortfolioDefinition, PriceObservation


class SnapshotMarketDataProvider(Protocol):
    """Provider boundary that materializes one immutable market snapshot."""

    def load_snapshot(self, portfolio: PortfolioDefinition) -> MarketSnapshot:
        """Load adjusted prices once for the requested portfolio."""


class FrozenSnapshotProvider:
    """Load the versioned synthetic CSV fixture without network access."""

    def __init__(
        self,
        fixture_path: Path,
        *,
        provider_name: str = "frozen-demo-fixture",
        retrieved_at: datetime = datetime(2026, 9, 22, 0, 0, tzinfo=UTC),
    ) -> None:
        self._fixture_path = fixture_path
        self._provider_name = provider_name
        self._retrieved_at = retrieved_at
        self._load_count = 0

    @classmethod
    def demo(cls) -> FrozenSnapshotProvider:
        """Return the packaged, wholly offline demo provider."""

        fixture = files("ai_quant.fixtures").joinpath("demo_adjusted_prices.csv")
        return cls(Path(str(fixture)))

    @property
    def load_count(self) -> int:
        """Expose the number of provider reads for integration assertions."""

        return self._load_count

    def load_snapshot(self, portfolio: PortfolioDefinition) -> MarketSnapshot:
        """Read, validate and freeze the requested fixture observations."""

        self._load_count += 1
        rows: list[dict[str, str]] = []
        with self._fixture_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            expected = {"date", "instrument", "adjusted_close", "currency"}
            if set(reader.fieldnames or ()) != expected:
                raise MarketDataError("Frozen price fixture has an unexpected schema.")
            rows.extend(reader)

        cutoff = portfolio.analysis_cutoff.date()
        selected = [
            row
            for row in rows
            if row["instrument"] in portfolio.instruments
            and date.fromisoformat(row["date"]) <= cutoff
        ]
        available = {
            row["instrument"]
            for row in selected
            if row["adjusted_close"].strip()
        }
        missing_assets = [asset for asset in portfolio.instruments if asset not in available]
        if missing_assets:
            raise MarketDataError(
                "No adjusted prices are available for: " + ", ".join(missing_assets)
            )

        currencies_by_asset: dict[str, str] = {}
        observations: list[PriceObservation] = []
        for row in selected:
            instrument = row["instrument"]
            currency = row["currency"]
            previous = currencies_by_asset.setdefault(instrument, currency)
            if previous != currency:
                raise MarketDataError(f"Multiple currencies found for {instrument}.")
            raw_price = row["adjusted_close"].strip()
            observations.append(
                PriceObservation(
                    observed_on=date.fromisoformat(row["date"]),
                    instrument=instrument,
                    adjusted_close=Decimal(raw_price) if raw_price else None,
                )
            )

        if any(currency != portfolio.base_currency for currency in currencies_by_asset.values()):
            raise MarketDataError(
                "Block 2 does not perform FX conversion; all assets must use base_currency."
            )

        return MarketSnapshot.create(
            snapshot_id="demo-adjusted-prices-2026-09-18-v1",
            instruments=portfolio.instruments,
            observations=tuple(observations),
            base_currency=portfolio.base_currency,
            currencies=tuple(currencies_by_asset.items()),
            provider=self._provider_name,
            analysis_cutoff=portfolio.analysis_cutoff,
            retrieved_at=self._retrieved_at,
            adjustment_policy=(
                "Synthetic adjusted-close fixture; values are treated as split/dividend-adjusted "
                "and are never refreshed in demo mode."
            ),
            artifact_uri="package://ai_quant/fixtures/demo_adjusted_prices.csv",
        )


class SnapshotRun:
    """Cache one snapshot and reject attempts to change it within a run."""

    def __init__(self, provider: SnapshotMarketDataProvider) -> None:
        self._provider = provider
        self._portfolio: PortfolioDefinition | None = None
        self._snapshot: MarketSnapshot | None = None

    def snapshot_for(self, portfolio: PortfolioDefinition) -> MarketSnapshot:
        """Return the run snapshot, loading the provider at most once."""

        if self._snapshot is None:
            self._snapshot = self._provider.load_snapshot(portfolio)
            self._portfolio = portfolio
            return self._snapshot
        if portfolio != self._portfolio:
            raise MarketDataError(
                "A run cannot request a second portfolio or market snapshot: "
                "PortfolioDefinition differs from the run definition."
            )
        return self._snapshot
