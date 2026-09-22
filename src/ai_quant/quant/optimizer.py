"""Long-only Markowitz optimization with explicit diagnostics and no fallback."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from ai_quant.quant.calculations import TRADING_DAYS_PER_YEAR
from ai_quant.quant.models import PortfolioDefinition, ReturnMatrix, RiskFreeRate


@dataclass(frozen=True, slots=True)
class OptimizationDiagnostics:
    """Auditable status for every solver and constraint check."""

    converged: bool
    solver_success: bool
    solver_status: int
    solver_message: str
    constraints_satisfied: bool
    bounds_satisfied: bool
    weight_sum: float | None
    excluded_assets: tuple[str, ...]
    failure_reason: str | None
    iterations: int
    objective: str = "maximum_historical_sharpe"


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Weights are emitted only when convergence and all checks succeed."""

    weights: tuple[tuple[str, float], ...]
    diagnostics: OptimizationDiagnostics


def optimize_markowitz_long_only(
    return_matrix: ReturnMatrix,
    portfolio: PortfolioDefinition,
    risk_free_rate: RiskFreeRate,
    *,
    annualization_factor: int = TRADING_DAYS_PER_YEAR,
    max_iterations: int = 500,
    tolerance: float = 1e-9,
) -> OptimizationResult:
    """Maximize historical Sharpe subject to long-only bounds and sum(weights)=1."""

    frame = return_matrix.to_frame()
    variances = frame.var(axis=0, ddof=1)
    excluded = tuple(
        asset
        for asset in return_matrix.instruments
        if not math.isfinite(float(variances[asset])) or float(variances[asset]) <= tolerance
    )
    active = tuple(asset for asset in return_matrix.instruments if asset not in excluded)
    minimum = portfolio.constraints.minimum_weight
    maximum = portfolio.constraints.maximum_weight

    if not active:
        return _preflight_failure(excluded, "No asset has positive finite sample variance.")
    if excluded and minimum > tolerance:
        return _preflight_failure(
            excluded,
            "Excluded assets cannot satisfy a strictly positive minimum weight.",
        )
    if len(active) * minimum > 1.0 + tolerance or len(active) * maximum < 1.0 - tolerance:
        return _preflight_failure(excluded, "Weight bounds cannot satisfy sum(weights)=1.")

    values = frame.loc[:, active].to_numpy(dtype=float)
    annual_means = np.mean(values, axis=0) * annualization_factor
    annual_covariance = np.atleast_2d(np.cov(values, rowvar=False, ddof=1)) * annualization_factor

    def negative_sharpe(weights: np.ndarray) -> float:
        variance = float(weights @ annual_covariance @ weights)
        if not math.isfinite(variance) or variance <= tolerance:
            return 1e12
        excess_return = float(weights @ annual_means) - risk_free_rate.annual_rate
        return -excess_return / math.sqrt(variance)

    initial = np.full(len(active), 1.0 / len(active))
    result = minimize(
        negative_sharpe,
        initial,
        method="SLSQP",
        bounds=tuple((minimum, maximum) for _ in active),
        constraints=({"type": "eq", "fun": lambda weights: float(np.sum(weights) - 1.0)},),
        options={"maxiter": max_iterations, "ftol": tolerance, "disp": False},
    )
    candidate = np.asarray(result.x, dtype=float)
    weight_sum = float(np.sum(candidate)) if candidate.size else None
    bounds_satisfied = bool(
        candidate.size
        and np.all(candidate >= minimum - tolerance)
        and np.all(candidate <= maximum + tolerance)
    )
    constraint_satisfied = bool(
        weight_sum is not None and math.isclose(weight_sum, 1.0, abs_tol=tolerance * 10)
    )
    converged = bool(result.success and bounds_satisfied and constraint_satisfied)
    failure_reason = None if converged else str(result.message)
    diagnostics = OptimizationDiagnostics(
        converged=converged,
        solver_success=bool(result.success),
        solver_status=int(result.status),
        solver_message=str(result.message),
        constraints_satisfied=constraint_satisfied,
        bounds_satisfied=bounds_satisfied,
        weight_sum=weight_sum,
        excluded_assets=excluded,
        failure_reason=failure_reason,
        iterations=int(getattr(result, "nit", 0)),
    )
    if not converged:
        return OptimizationResult(weights=(), diagnostics=diagnostics)

    active_weights = dict(zip(active, (float(value) for value in candidate), strict=True))
    weights = tuple((asset, active_weights.get(asset, 0.0)) for asset in portfolio.instruments)
    return OptimizationResult(weights=weights, diagnostics=diagnostics)


def _preflight_failure(
    excluded_assets: tuple[str, ...],
    reason: str,
) -> OptimizationResult:
    return OptimizationResult(
        weights=(),
        diagnostics=OptimizationDiagnostics(
            converged=False,
            solver_success=False,
            solver_status=-1,
            solver_message="Preflight validation failed.",
            constraints_satisfied=False,
            bounds_satisfied=False,
            weight_sum=None,
            excluded_assets=excluded_assets,
            failure_reason=reason,
            iterations=0,
        ),
    )
