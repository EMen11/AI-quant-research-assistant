"""Deterministic orchestration over exactly one immutable market snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from ai_quant.quant.calculations import (
    PortfolioMetrics,
    aggregate_portfolio_metrics,
    annualized_covariance,
    annualized_volatility,
    build_return_matrix,
    correlation,
    cumulative_returns,
    historical_annualized_returns,
)
from ai_quant.quant.models import (
    MarketSnapshot,
    MatrixValue,
    MetricValue,
    PortfolioDefinition,
    ReturnMatrix,
    RiskFreeRate,
)
from ai_quant.quant.optimizer import OptimizationResult, optimize_markowitz_long_only


class SnapshotRunLike(Protocol):
    """Minimal run boundary used without coupling the quant core to a provider."""

    def snapshot_for(self, portfolio: PortfolioDefinition) -> MarketSnapshot:
        """Return the sole immutable snapshot for this run."""


@dataclass(frozen=True, slots=True)
class AssetMetrics:
    """Per-asset metrics derived from the shared ReturnMatrix."""

    instrument: str
    cumulative_return: MetricValue
    historical_annualized_return: MetricValue
    annualized_volatility: MetricValue


@dataclass(frozen=True, slots=True)
class QuantAnalysis:
    """Complete deterministic result referencing exactly one MarketSnapshot."""

    portfolio: PortfolioDefinition
    snapshot: MarketSnapshot
    return_matrix: ReturnMatrix
    asset_metrics: tuple[AssetMetrics, ...]
    covariance: MatrixValue
    correlation: MatrixValue
    baseline_weights: tuple[tuple[str, float], ...]
    portfolio_metrics: PortfolioMetrics
    risk_free_rate: RiskFreeRate
    optimization: OptimizationResult
    assumptions: tuple[str, ...]


def analyze_portfolio(
    portfolio: PortfolioDefinition,
    snapshot_run: SnapshotRunLike,
    risk_free_rate: RiskFreeRate,
) -> QuantAnalysis:
    """Load one snapshot, build one return matrix and reuse both everywhere."""

    snapshot = snapshot_run.snapshot_for(portfolio)
    returns = build_return_matrix(snapshot)
    cumulative = cumulative_returns(returns)
    annualized = historical_annualized_returns(returns)
    volatility = annualized_volatility(returns)
    asset_metrics = tuple(
        AssetMetrics(
            instrument=instrument,
            cumulative_return=MetricValue(
                cumulative[index],
                "decimal return",
                "cumulative_simple_v1",
                f"{len(returns.values)} complete daily observations",
            ),
            historical_annualized_return=MetricValue(
                annualized[index],
                "decimal return/year",
                "historical_geometric_annualized_v1",
                "252 trading days",
            ),
            annualized_volatility=MetricValue(
                volatility[index],
                "decimal volatility/year",
                "volatility_sample_annualized_v1",
                "252 trading days",
            ),
        )
        for index, instrument in enumerate(returns.instruments)
    )
    baseline_weights = _baseline_weights(portfolio)
    return QuantAnalysis(
        portfolio=portfolio,
        snapshot=snapshot,
        return_matrix=returns,
        asset_metrics=asset_metrics,
        covariance=annualized_covariance(returns),
        correlation=correlation(returns),
        baseline_weights=baseline_weights,
        portfolio_metrics=aggregate_portfolio_metrics(
            returns, baseline_weights, risk_free_rate
        ),
        risk_free_rate=risk_free_rate,
        optimization=optimize_markowitz_long_only(returns, portfolio, risk_free_rate),
        assumptions=(
            "Adjusted-close prices from one frozen synthetic snapshot; no live refresh.",
            "Daily simple returns; missing prices are never forward-filled.",
            "Only complete aligned return rows are used by every calculation.",
            "252 trading days per year; sample volatility and covariance (ddof=1).",
            "VaR and Expected Shortfall are positive one-day loss magnitudes.",
            "Markowitz maximizes historical Sharpe under long-only bounds; it is not a forecast.",
        ),
    )


def demo_portfolio() -> PortfolioDefinition:
    """Return the explicit three-asset portfolio used by the offline demo."""

    return PortfolioDefinition(
        portfolio_id="demo-chf-three-assets-v1",
        instruments=("DEMO-ALPHA", "DEMO-BETA", "DEMO-GAMMA"),
        base_currency="CHF",
        analysis_cutoff=datetime(2026, 9, 18, 23, 59, tzinfo=UTC),
    )


def demo_risk_free_rate() -> RiskFreeRate:
    """Return a labelled demo assumption, never presented as live market data."""

    return RiskFreeRate(
        annual_rate=0.01,
        currency="CHF",
        as_of=date(2026, 9, 18),
        source="Synthetic Block 2 demo assumption; fixed fixture, not a real-time quote.",
    )


def _baseline_weights(portfolio: PortfolioDefinition) -> tuple[tuple[str, float], ...]:
    if portfolio.weighting_rule == "custom":
        assert portfolio.initial_weights is not None
        return tuple(portfolio.initial_weights)
    equal_weight = 1.0 / len(portfolio.instruments)
    return tuple((instrument, equal_weight) for instrument in portfolio.instruments)
