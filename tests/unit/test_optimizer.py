from datetime import UTC, date, datetime, timedelta

import pytest

from ai_quant.quant import (
    OptimizationConstraints,
    PortfolioDefinition,
    ReturnMatrix,
    RiskFreeRate,
    optimize_markowitz_long_only,
)


def make_returns(*, constant_second_asset: bool = False) -> ReturnMatrix:
    second = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0) if constant_second_asset else (
        0.002,
        0.001,
        -0.002,
        0.003,
        0.001,
        -0.001,
    )
    first = (0.010, -0.004, 0.008, 0.003, -0.002, 0.009)
    return ReturnMatrix(
        dates=tuple(date(2026, 1, 1) + timedelta(days=index) for index in range(6)),
        instruments=("A", "B"),
        values=tuple(zip(first, second, strict=True)),
        dropped_dates=(),
    )


def make_portfolio(constraints: OptimizationConstraints) -> PortfolioDefinition:
    return PortfolioDefinition(
        portfolio_id="optimizer-test",
        instruments=("A", "B"),
        base_currency="CHF",
        analysis_cutoff=datetime(2026, 1, 31, tzinfo=UTC),
        constraints=constraints,
    )


def risk_free() -> RiskFreeRate:
    return RiskFreeRate(0.01, "CHF", date(2026, 1, 1), "Unit-test assumption.")


def test_feasible_optimization_converges_with_sum_and_bounds() -> None:
    portfolio = make_portfolio(OptimizationConstraints(0.20, 0.80))

    result = optimize_markowitz_long_only(make_returns(), portfolio, risk_free())

    assert result.diagnostics.converged
    assert result.diagnostics.constraints_satisfied
    assert result.diagnostics.bounds_satisfied
    assert result.diagnostics.weight_sum == pytest.approx(1.0)
    assert sum(weight for _, weight in result.weights) == pytest.approx(1.0)
    assert all(0.20 - 1e-9 <= weight <= 0.80 + 1e-9 for _, weight in result.weights)


def test_infeasible_bounds_fail_before_solver_without_weights() -> None:
    portfolio = make_portfolio(OptimizationConstraints(0.60, 0.80))

    result = optimize_markowitz_long_only(make_returns(), portfolio, risk_free())

    assert not result.diagnostics.converged
    assert result.weights == ()
    assert result.diagnostics.failure_reason == "Weight bounds cannot satisfy sum(weights)=1."


def test_solver_failure_is_reported_without_fallback_weights() -> None:
    portfolio = make_portfolio(OptimizationConstraints(0.0, 1.0))

    result = optimize_markowitz_long_only(
        make_returns(), portfolio, risk_free(), max_iterations=0
    )

    assert not result.diagnostics.converged
    assert not result.diagnostics.solver_success
    assert result.weights == ()
    assert result.diagnostics.failure_reason


def test_zero_variance_asset_is_listed_as_excluded() -> None:
    portfolio = make_portfolio(OptimizationConstraints(0.0, 1.0))

    result = optimize_markowitz_long_only(
        make_returns(constant_second_asset=True), portfolio, risk_free()
    )

    assert result.diagnostics.excluded_assets == ("B",)
    assert result.diagnostics.converged
    assert dict(result.weights)["B"] == 0.0

