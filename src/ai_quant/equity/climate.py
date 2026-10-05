"""Climate normalization kept separate from financial interpretation."""

from __future__ import annotations

from decimal import Decimal

from ai_quant.equity.models import (
    AssuranceStatus,
    EquityValidationError,
    MetricValue,
    Scope2Method,
    calculated_metric,
    merged_sources,
    require_compatible_inputs,
    unavailable_metric,
)


def normalize_emissions(metric: MetricValue, *, target_unit: str = "tCO2e") -> MetricValue:
    """Normalize emissions between tonnes and kilotonnes without mutating source values."""

    if target_unit not in {"tCO2e", "ktCO2e"}:
        raise EquityValidationError("target emissions unit must be tCO2e or ktCO2e.")
    output_id = f"{metric.company_id}-{metric.fiscal_year}-{metric.name}-{target_unit}"
    if not metric.is_available:
        return unavailable_metric(
            metric_id=output_id,
            company_id=metric.company_id,
            fiscal_year=metric.fiscal_year,
            name=metric.name,
            unit=target_unit,
            note="Emissions cannot be normalized because the source metric is unavailable.",
            sources=metric.sources,
            input_metric_ids=(metric.metric_id,),
        )
    conversions = {
        ("tCO2e", "tCO2e"): Decimal("1"),
        ("ktCO2e", "ktCO2e"): Decimal("1"),
        ("ktCO2e", "tCO2e"): Decimal("1000"),
        ("tCO2e", "ktCO2e"): Decimal("0.001"),
    }
    try:
        factor = conversions[(metric.unit, target_unit)]
    except KeyError as error:
        raise EquityValidationError("source emissions unit must be tCO2e or ktCO2e.") from error
    return calculated_metric(
        metric_id=output_id,
        company_id=metric.company_id,
        fiscal_year=metric.fiscal_year,
        name=metric.name,
        value=metric.value * factor,
        unit=target_unit,
        formula_id="emissions-unit-normalization",
        expression=f"source_emissions * {factor}",
        inputs=(metric,),
        scope2_method=metric.scope2_method,
        assurance=metric.assurance,
    )


def climate_intensity(
    scope1: MetricValue,
    scope2: MetricValue,
    revenue: MetricValue,
    *,
    scope2_method: Scope2Method,
    assurance: AssuranceStatus,
) -> MetricValue:
    """Calculate Scope 1+2 intensity with an explicit Scope 2 method and assurance."""

    require_compatible_inputs(scope1, scope2, revenue)
    if len({scope1.fiscal_year, scope2.fiscal_year, revenue.fiscal_year}) != 1:
        raise EquityValidationError("climate intensity inputs must use the same fiscal year.")
    output_id = f"{scope1.company_id}-{scope1.fiscal_year}-scope1-2-intensity"
    if not scope1.is_available or not scope2.is_available or not revenue.is_available:
        return unavailable_metric(
            metric_id=output_id,
            company_id=scope1.company_id,
            fiscal_year=scope1.fiscal_year,
            name="scope1_2_intensity",
            unit="tCO2e_per_CHF_million",
            note="Climate intensity requires Scope 1, Scope 2, and revenue.",
            sources=merged_sources((scope1, scope2, revenue)),
            input_metric_ids=(scope1.metric_id, scope2.metric_id, revenue.metric_id),
        )
    if scope1.unit != "tCO2e" or scope2.unit != "tCO2e":
        raise EquityValidationError("emissions must be normalized to tCO2e first.")
    if revenue.unit != "CHF_millions":
        raise EquityValidationError("climate intensity revenue must use CHF_millions.")
    if revenue.value <= 0:
        return unavailable_metric(
            metric_id=output_id,
            company_id=scope1.company_id,
            fiscal_year=scope1.fiscal_year,
            name="scope1_2_intensity",
            unit="tCO2e_per_CHF_million",
            note="Climate intensity requires positive revenue.",
            status="not_comparable",
            sources=merged_sources((scope1, scope2, revenue)),
            input_metric_ids=(scope1.metric_id, scope2.metric_id, revenue.metric_id),
        )
    return calculated_metric(
        metric_id=output_id,
        company_id=scope1.company_id,
        fiscal_year=scope1.fiscal_year,
        name="scope1_2_intensity",
        value=(scope1.value + scope2.value) / revenue.value,
        unit="tCO2e_per_CHF_million",
        formula_id="scope1-plus-scope2-intensity",
        expression="(scope1_tCO2e + scope2_tCO2e) / revenue_CHF_millions",
        inputs=(scope1, scope2, revenue),
        note="Financial and climate values are combined only for descriptive intensity.",
        scope2_method=scope2_method,
        assurance=assurance,
    )
