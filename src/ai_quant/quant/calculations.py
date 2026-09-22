"""Pure return, risk and portfolio calculations using one return matrix."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from ai_quant.quant.models import (
    MarketSnapshot,
    MatrixValue,
    MetricValue,
    QuantValidationError,
    ReturnMatrix,
    RiskFreeRate,
)

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class RiskEstimate:
    """One-period loss estimates at a stated confidence level."""

    confidence_level: float
    historical_var: MetricValue
    parametric_var: MetricValue
    expected_shortfall: MetricValue


@dataclass(frozen=True, slots=True)
class PortfolioMetrics:
    """Aggregated metrics computed from weighted daily simple returns."""

    cumulative_return: MetricValue
    historical_annualized_return: MetricValue
    annualized_volatility: MetricValue
    maximum_drawdown: MetricValue
    historical_sharpe_ratio: MetricValue | None
    risk_estimates: tuple[RiskEstimate, ...]


def build_return_matrix(
    snapshot: MarketSnapshot,
    *,
    minimum_complete_returns: int = 2,
) -> ReturnMatrix:
    """Build daily simple returns once, without filling prices, then drop incomplete rows."""

    if minimum_complete_returns < 1:
        raise QuantValidationError("minimum_complete_returns must be positive.")
    prices = snapshot.price_frame()
    empty_assets = tuple(asset for asset in prices if prices[asset].notna().sum() == 0)
    if empty_assets:
        raise QuantValidationError("Assets without adjusted prices: " + ", ".join(empty_assets))

    raw_returns = prices.pct_change(fill_method=None)
    incomplete = raw_returns.isna().any(axis=1)
    complete_returns = raw_returns.loc[~incomplete]
    if len(complete_returns) < minimum_complete_returns:
        raise QuantValidationError(
            "Insufficient aligned history: "
            f"{len(complete_returns)} complete return rows; "
            f"at least {minimum_complete_returns} required."
        )

    return ReturnMatrix(
        dates=tuple(complete_returns.index),
        instruments=tuple(complete_returns.columns),
        values=tuple(tuple(float(value) for value in row) for row in complete_returns.to_numpy()),
        dropped_dates=tuple(raw_returns.index[incomplete]),
    )


def cumulative_returns(return_matrix: ReturnMatrix) -> tuple[float, ...]:
    """Return ``product(1 + r_t) - 1`` for each asset."""

    values = return_matrix.to_frame().to_numpy(dtype=float)
    return tuple(float(value) for value in np.prod(1.0 + values, axis=0) - 1.0)


def historical_annualized_returns(
    return_matrix: ReturnMatrix,
    *,
    annualization_factor: int = TRADING_DAYS_PER_YEAR,
) -> tuple[float, ...]:
    """Geometrically annualize observed cumulative simple returns."""

    _validate_annualization_factor(annualization_factor)
    periods = len(return_matrix.values)
    return tuple(
        float((1.0 + cumulative) ** (annualization_factor / periods) - 1.0)
        for cumulative in cumulative_returns(return_matrix)
    )


def annualized_volatility(
    return_matrix: ReturnMatrix,
    *,
    annualization_factor: int = TRADING_DAYS_PER_YEAR,
) -> tuple[float, ...]:
    """Annualize sample standard deviation (ddof=1) of daily simple returns."""

    _validate_annualization_factor(annualization_factor)
    _require_observations(len(return_matrix.values), 2)
    daily = np.std(return_matrix.to_frame().to_numpy(dtype=float), axis=0, ddof=1)
    return tuple(float(value * math.sqrt(annualization_factor)) for value in daily)


def drawdown(returns: tuple[float, ...]) -> tuple[float, ...]:
    """Return non-positive wealth drawdowns relative to the running peak."""

    _validate_returns(returns)
    wealth = np.cumprod(1.0 + np.asarray(returns, dtype=float))
    peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return tuple(float(value) for value in wealth / peaks - 1.0)


def maximum_drawdown(returns: tuple[float, ...]) -> float:
    """Return maximum drawdown as a non-negative loss magnitude."""

    return max(0.0, -min(drawdown(returns)))


def historical_var(returns: tuple[float, ...], confidence_level: float) -> float:
    """Return positive one-period loss VaR from the linear empirical quantile."""

    _validate_confidence(confidence_level)
    _validate_returns(returns)
    threshold = float(np.quantile(returns, 1.0 - confidence_level, method="linear"))
    return max(0.0, -threshold)


def parametric_var(returns: tuple[float, ...], confidence_level: float) -> float:
    """Return positive one-period Gaussian VaR using sample volatility."""

    _validate_confidence(confidence_level)
    _validate_returns(returns)
    _require_observations(len(returns), 2)
    values = np.asarray(returns, dtype=float)
    threshold = float(
        np.mean(values)
        + NormalDist().inv_cdf(1.0 - confidence_level) * np.std(values, ddof=1)
    )
    return max(0.0, -threshold)


def expected_shortfall(returns: tuple[float, ...], confidence_level: float) -> float:
    """Return positive mean loss for returns at or below historical VaR's threshold."""

    _validate_confidence(confidence_level)
    _validate_returns(returns)
    values = np.asarray(returns, dtype=float)
    threshold = float(np.quantile(values, 1.0 - confidence_level, method="linear"))
    tail = values[values <= threshold]
    return max(0.0, -float(np.mean(tail)))


def annualized_covariance(
    return_matrix: ReturnMatrix,
    *,
    annualization_factor: int = TRADING_DAYS_PER_YEAR,
) -> MatrixValue:
    """Return the annualized sample covariance matrix of daily simple returns."""

    _validate_annualization_factor(annualization_factor)
    _require_observations(len(return_matrix.values), 2)
    values = np.cov(return_matrix.to_frame().to_numpy(dtype=float), rowvar=False, ddof=1)
    values = np.atleast_2d(values) * annualization_factor
    return _matrix_value(return_matrix, values, "decimal²/year", "covariance_sample_v1")


def correlation(return_matrix: ReturnMatrix) -> MatrixValue:
    """Return the Pearson correlation matrix of daily simple returns."""

    _require_observations(len(return_matrix.values), 2)
    values = np.corrcoef(return_matrix.to_frame().to_numpy(dtype=float), rowvar=False)
    values = np.atleast_2d(values)
    return _matrix_value(return_matrix, values, "coefficient", "correlation_pearson_v1")


def aggregate_portfolio_metrics(
    return_matrix: ReturnMatrix,
    weights: tuple[tuple[str, float], ...],
    risk_free_rate: RiskFreeRate,
    *,
    confidence_levels: tuple[float, ...] = (0.95, 0.99),
    annualization_factor: int = TRADING_DAYS_PER_YEAR,
) -> PortfolioMetrics:
    """Compute all portfolio metrics from the supplied, already-built return matrix."""

    _validate_annualization_factor(annualization_factor)
    weight_map = dict(weights)
    if set(weight_map) != set(return_matrix.instruments):
        raise QuantValidationError("Portfolio weights must cover ReturnMatrix instruments.")
    ordered_weights = np.asarray([weight_map[item] for item in return_matrix.instruments])
    if np.any(ordered_weights < 0.0) or not math.isclose(
        float(np.sum(ordered_weights)), 1.0, abs_tol=1e-9
    ):
        raise QuantValidationError("Portfolio weights must be long-only and sum to 1.")

    daily = return_matrix.to_frame().to_numpy(dtype=float) @ ordered_weights
    daily_returns = tuple(float(value) for value in daily)
    cumulative = float(np.prod(1.0 + daily) - 1.0)
    annualized_return = float(
        (1.0 + cumulative) ** (annualization_factor / len(daily_returns)) - 1.0
    )
    volatility = float(np.std(daily, ddof=1) * math.sqrt(annualization_factor))
    sharpe = (
        MetricValue(
            value=(annualized_return - risk_free_rate.annual_rate) / volatility,
            unit="ratio",
            formula_version="historical_sharpe_v1",
            horizon="annualized from daily observations",
        )
        if volatility > 0.0
        else None
    )
    risk = tuple(
        RiskEstimate(
            confidence_level=level,
            historical_var=MetricValue(
                historical_var(daily_returns, level),
                "decimal loss",
                "var_historical_linear_v1",
                "1 trading day",
                level,
            ),
            parametric_var=MetricValue(
                parametric_var(daily_returns, level),
                "decimal loss",
                "var_gaussian_v1",
                "1 trading day",
                level,
            ),
            expected_shortfall=MetricValue(
                expected_shortfall(daily_returns, level),
                "decimal loss",
                "expected_shortfall_historical_v1",
                "1 trading day",
                level,
            ),
        )
        for level in confidence_levels
    )
    return PortfolioMetrics(
        cumulative_return=MetricValue(
            cumulative,
            "decimal return",
            "cumulative_simple_v1",
            f"{len(daily_returns)} complete daily observations",
        ),
        historical_annualized_return=MetricValue(
            annualized_return,
            "decimal return/year",
            "historical_geometric_annualized_v1",
            f"annualized with {annualization_factor} trading days",
        ),
        annualized_volatility=MetricValue(
            volatility,
            "decimal volatility/year",
            "volatility_sample_annualized_v1",
            f"annualized with {annualization_factor} trading days",
        ),
        maximum_drawdown=MetricValue(
            maximum_drawdown(daily_returns),
            "decimal loss",
            "maximum_drawdown_v1",
            "full snapshot period",
        ),
        historical_sharpe_ratio=sharpe,
        risk_estimates=risk,
    )


def _matrix_value(
    return_matrix: ReturnMatrix,
    values: np.ndarray,
    unit: str,
    version: str,
) -> MatrixValue:
    return MatrixValue(
        labels=return_matrix.instruments,
        values=tuple(tuple(float(value) for value in row) for row in values),
        unit=unit,
        formula_version=version,
    )


def _validate_returns(returns: tuple[float, ...]) -> None:
    if not returns or any(not math.isfinite(value) or value <= -1.0 for value in returns):
        raise QuantValidationError("Returns must be finite, non-empty and greater than -100%.")


def _validate_confidence(confidence_level: float) -> None:
    if not 0.0 < confidence_level < 1.0:
        raise QuantValidationError("confidence_level must be strictly between 0 and 1.")


def _validate_annualization_factor(annualization_factor: int) -> None:
    if annualization_factor <= 0:
        raise QuantValidationError("annualization_factor must be positive.")


def _require_observations(actual: int, required: int) -> None:
    if actual < required:
        raise QuantValidationError(f"At least {required} return observations are required.")

