"""Presentation-only formatting that never changes authoritative values."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ai_quant.equity.models import MetricValue


def format_metric(metric: MetricValue) -> str:
    """Format one Equity metric using its explicit unit and availability state."""

    if not metric.is_available:
        return "—"
    value = metric.value
    if metric.unit == "CHF_millions":
        return f"CHF {_number(value, 1)}m"
    if metric.unit == "CHF_per_share":
        return f"CHF {_number(value, 2)}/share"
    if metric.unit == "percent":
        return f"{_number(value, 1)}%"
    if metric.unit == "multiple":
        return f"{_number(value, 1)}x"
    if metric.unit == "shares":
        return f"{value:,.0f} shares"
    if metric.unit == "tCO2e":
        return f"{value:,.0f} tCO₂e"
    if metric.unit == "ktCO2e":
        return f"{_number(value, 1)} ktCO₂e"
    if metric.unit == "tCO2e_per_CHF_million":
        return f"{_number(value, 1)} tCO₂e/CHF m"
    return f"{value} {metric.unit}"


def _number(value: Decimal, decimals: int) -> str:
    quantum = Decimal("1").scaleb(-decimals)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return f"{rounded:,.{decimals}f}"
