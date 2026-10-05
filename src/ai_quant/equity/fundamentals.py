"""Deterministic fundamental-analysis formulas."""

from __future__ import annotations

from decimal import Decimal

from ai_quant.equity.models import (
    EquityValidationError,
    MetricValue,
    calculated_metric,
    merged_sources,
    require_compatible_inputs,
    unavailable_metric,
)

ONE_HUNDRED = Decimal("100")


def year_over_year_growth(
    current: MetricValue,
    previous: MetricValue,
    *,
    name: str | None = None,
) -> MetricValue:
    """Calculate percentage growth between two explicit fiscal-year observations."""

    require_compatible_inputs(current, previous)
    output_name = name or f"{current.name}_yoy_growth"
    output_id = _metric_id(current, output_name)
    missing = _missing_inputs(
        output_id,
        current,
        "percent",
        (current, previous),
        name=output_name,
        formula_id="year-over-year-growth",
        expression="(current / previous - 1) * 100",
    )
    if missing is not None:
        return missing
    if current.unit != previous.unit:
        raise EquityValidationError("growth inputs must use the same unit.")
    if previous.value == 0:
        return _not_comparable(
            output_id,
            current,
            "percent",
            (current, previous),
            "Prior-year value is zero; growth is not comparable.",
            name=output_name,
            formula_id="year-over-year-growth",
            expression="(current / previous - 1) * 100",
        )
    value = (current.value / previous.value - Decimal("1")) * ONE_HUNDRED
    return calculated_metric(
        metric_id=output_id,
        company_id=current.company_id,
        fiscal_year=current.fiscal_year,
        name=output_name,
        value=value,
        unit="percent",
        formula_id="year-over-year-growth",
        expression="(current / previous - 1) * 100",
        inputs=(current, previous),
    )


def compound_annual_growth(
    end: MetricValue,
    start: MetricValue,
    *,
    name: str | None = None,
) -> MetricValue:
    """Calculate CAGR across the exact number of fiscal-year intervals."""

    require_compatible_inputs(end, start)
    output_name = name or f"{end.name}_cagr"
    output_id = _metric_id(end, output_name)
    missing = _missing_inputs(
        output_id,
        end,
        "percent",
        (end, start),
        name=output_name,
        formula_id="compound-annual-growth",
        expression="((end / start) ** (1 / year_intervals) - 1) * 100",
    )
    if missing is not None:
        return missing
    if end.unit != start.unit:
        raise EquityValidationError("CAGR inputs must use the same unit.")
    periods = end.fiscal_year - start.fiscal_year
    if periods <= 0:
        raise EquityValidationError("CAGR end fiscal year must be after start fiscal year.")
    if start.value <= 0 or end.value < 0:
        return _not_comparable(
            output_id,
            end,
            "percent",
            (end, start),
            "CAGR requires a positive start value and a non-negative end value.",
            name=output_name,
            formula_id="compound-annual-growth",
            expression="((end / start) ** (1 / year_intervals) - 1) * 100",
        )
    value = ((end.value / start.value) ** (Decimal("1") / Decimal(periods)) - 1) * ONE_HUNDRED
    return calculated_metric(
        metric_id=output_id,
        company_id=end.company_id,
        fiscal_year=end.fiscal_year,
        name=output_name,
        value=value,
        unit="percent",
        formula_id="compound-annual-growth",
        expression="((end / start) ** (1 / year_intervals) - 1) * 100",
        inputs=(end, start),
        note=f"{periods} fiscal-year intervals.",
    )


def margin(profit: MetricValue, revenue: MetricValue, *, name: str) -> MetricValue:
    """Calculate a profit margin as a percentage of revenue."""

    return _percentage_ratio(
        profit,
        revenue,
        name=name,
        formula_id=f"{name}-margin",
        expression="profit / revenue * 100",
        denominator_must_be_positive=True,
    )


def free_cash_flow(
    operating_cash_flow: MetricValue,
    capex: MetricValue,
    *,
    name: str = "free_cash_flow_calculated",
) -> MetricValue:
    """Calculate FCF using signed capex: operating cash flow plus capex cash outflow."""

    require_compatible_inputs(operating_cash_flow, capex)
    _require_same_period(operating_cash_flow, capex)
    output_id = _metric_id(operating_cash_flow, name)
    missing = _missing_inputs(
        output_id,
        operating_cash_flow,
        operating_cash_flow.unit,
        (operating_cash_flow, capex),
        name=name,
        formula_id="free-cash-flow-signed-capex",
        expression="operating_cash_flow + signed_capex",
    )
    if missing is not None:
        return missing
    _require_same_unit(operating_cash_flow, capex)
    return calculated_metric(
        metric_id=output_id,
        company_id=operating_cash_flow.company_id,
        fiscal_year=operating_cash_flow.fiscal_year,
        name=name,
        value=operating_cash_flow.value + capex.value,
        unit=operating_cash_flow.unit,
        formula_id="free-cash-flow-signed-capex",
        expression="operating_cash_flow + signed_capex",
        inputs=(operating_cash_flow, capex),
        note="Capex is expected to be recorded as a signed cash outflow.",
    )


def cash_conversion(
    free_cash_flow_metric: MetricValue,
    ebitda: MetricValue,
    *,
    name: str = "cash_conversion",
) -> MetricValue:
    """Calculate FCF conversion relative to EBITDA."""

    return _percentage_ratio(
        free_cash_flow_metric,
        ebitda,
        name=name,
        formula_id="fcf-to-ebitda",
        expression="free_cash_flow / EBITDA * 100",
        denominator_must_be_positive=True,
    )


def capex_to_revenue(
    capex: MetricValue,
    revenue: MetricValue,
    *,
    name: str = "capex_to_revenue",
) -> MetricValue:
    """Calculate capex intensity using the absolute signed capex outflow."""

    return _percentage_ratio(
        capex,
        revenue,
        name=name,
        formula_id="absolute-capex-to-revenue",
        expression="abs(signed_capex) / revenue * 100",
        denominator_must_be_positive=True,
        absolute_numerator=True,
    )


def net_debt(total_debt: MetricValue, cash: MetricValue) -> MetricValue:
    """Calculate net debt; a negative result represents net cash."""

    require_compatible_inputs(total_debt, cash)
    _require_same_period(total_debt, cash)
    output_id = _metric_id(total_debt, "net-debt")
    missing = _missing_inputs(
        output_id,
        total_debt,
        total_debt.unit,
        (total_debt, cash),
        name="net_debt",
        formula_id="net-debt",
        expression="total_debt - cash_and_cash_equivalents",
    )
    if missing is not None:
        return missing
    _require_same_unit(total_debt, cash)
    return calculated_metric(
        metric_id=output_id,
        company_id=total_debt.company_id,
        fiscal_year=total_debt.fiscal_year,
        name="net_debt",
        value=total_debt.value - cash.value,
        unit=total_debt.unit,
        formula_id="net-debt",
        expression="total_debt - cash_and_cash_equivalents",
        inputs=(total_debt, cash),
    )


def leverage(net_debt_metric: MetricValue, ebitda: MetricValue) -> MetricValue:
    """Calculate net debt to EBITDA in turns."""

    return _plain_ratio(
        net_debt_metric,
        ebitda,
        name="net_debt_to_ebitda",
        formula_id="net-debt-to-ebitda",
        expression="net_debt / EBITDA",
        denominator_must_be_positive=True,
    )


def return_on_equity(net_income: MetricValue, equity: MetricValue) -> MetricValue:
    """Calculate ROE using period-end equity, explicitly named to avoid ambiguity."""

    result = _percentage_ratio(
        net_income,
        equity,
        name="return_on_period_end_equity",
        formula_id="net-income-to-period-end-equity",
        expression="net_income / period_end_equity * 100",
        denominator_must_be_positive=True,
    )
    if result.is_available:
        return MetricValue(
            metric_id=result.metric_id,
            company_id=result.company_id,
            fiscal_year=result.fiscal_year,
            name=result.name,
            value=result.value,
            unit=result.unit,
            status=result.status,
            sources=result.sources,
            formula=result.formula,
            input_metric_ids=result.input_metric_ids,
            note="Uses period-end equity, not average equity.",
        )
    return result


def payout_ratio(distributions: MetricValue, net_income: MetricValue) -> MetricValue:
    """Calculate payout from the absolute distribution cash outflow."""

    return _percentage_ratio(
        distributions,
        net_income,
        name="payout_ratio",
        formula_id="absolute-distributions-to-net-income",
        expression="abs(distributions) / net_income * 100",
        denominator_must_be_positive=True,
        absolute_numerator=True,
    )


def estimated_cash_distribution(
    dividend_per_share: MetricValue,
    registered_shares: MetricValue,
) -> MetricValue:
    """Estimate aggregate distribution from same-year DPS and registered shares."""

    require_compatible_inputs(dividend_per_share, registered_shares)
    _require_same_period(dividend_per_share, registered_shares)
    output_name = "estimated_cash_distribution"
    output_id = _metric_id(dividend_per_share, output_name)
    missing = _missing_inputs(
        output_id,
        dividend_per_share,
        "CHF_millions",
        (dividend_per_share, registered_shares),
        name=output_name,
        formula_id="dividend-per-share-times-registered-shares",
        expression="dividend_per_share * registered_shares / 1_000_000",
    )
    if missing is not None:
        return missing
    if dividend_per_share.unit != "CHF_per_share" or registered_shares.unit != "shares":
        raise EquityValidationError(
            "cash distribution requires CHF_per_share and shares inputs."
        )
    if registered_shares.value <= 0:
        return _not_comparable(
            output_id,
            dividend_per_share,
            "CHF_millions",
            (dividend_per_share, registered_shares),
            "Cash distribution requires a positive share count.",
            name=output_name,
            formula_id="dividend-per-share-times-registered-shares",
            expression="dividend_per_share * registered_shares / 1_000_000",
        )
    return calculated_metric(
        metric_id=output_id,
        company_id=dividend_per_share.company_id,
        fiscal_year=dividend_per_share.fiscal_year,
        name=output_name,
        value=dividend_per_share.value * registered_shares.value / Decimal("1000000"),
        unit="CHF_millions",
        formula_id="dividend-per-share-times-registered-shares",
        expression="dividend_per_share * registered_shares / 1_000_000",
        inputs=(dividend_per_share, registered_shares),
        note=(
            "Estimate based on registered shares; treasury-share treatment may differ from "
            "the issuer's published total distribution."
        ),
    )


def _percentage_ratio(
    numerator: MetricValue,
    denominator: MetricValue,
    *,
    name: str,
    formula_id: str,
    expression: str,
    denominator_must_be_positive: bool,
    absolute_numerator: bool = False,
) -> MetricValue:
    result = _ratio(
        numerator,
        denominator,
        name=name,
        unit="percent",
        formula_id=formula_id,
        expression=expression,
        denominator_must_be_positive=denominator_must_be_positive,
        absolute_numerator=absolute_numerator,
        multiplier=ONE_HUNDRED,
    )
    return result


def _plain_ratio(
    numerator: MetricValue,
    denominator: MetricValue,
    *,
    name: str,
    formula_id: str,
    expression: str,
    denominator_must_be_positive: bool,
) -> MetricValue:
    return _ratio(
        numerator,
        denominator,
        name=name,
        unit="multiple",
        formula_id=formula_id,
        expression=expression,
        denominator_must_be_positive=denominator_must_be_positive,
        absolute_numerator=False,
        multiplier=Decimal("1"),
    )


def _ratio(
    numerator: MetricValue,
    denominator: MetricValue,
    *,
    name: str,
    unit: str,
    formula_id: str,
    expression: str,
    denominator_must_be_positive: bool,
    absolute_numerator: bool,
    multiplier: Decimal,
) -> MetricValue:
    require_compatible_inputs(numerator, denominator)
    _require_same_period(numerator, denominator)
    output_id = _metric_id(numerator, name)
    missing = _missing_inputs(
        output_id,
        numerator,
        unit,
        (numerator, denominator),
        name=name,
        formula_id=formula_id,
        expression=expression,
    )
    if missing is not None:
        return missing
    _require_same_unit(numerator, denominator)
    invalid_denominator = denominator.value <= 0 if denominator_must_be_positive else denominator.value == 0
    if invalid_denominator:
        return _not_comparable(
            output_id,
            numerator,
            unit,
            (numerator, denominator),
            "The formula denominator is zero or invalid for this metric.",
            name=name,
            formula_id=formula_id,
            expression=expression,
        )
    numerator_value = abs(numerator.value) if absolute_numerator else numerator.value
    return calculated_metric(
        metric_id=output_id,
        company_id=numerator.company_id,
        fiscal_year=numerator.fiscal_year,
        name=name,
        value=numerator_value / denominator.value * multiplier,
        unit=unit,
        formula_id=formula_id,
        expression=expression,
        inputs=(numerator, denominator),
    )


def _metric_id(anchor: MetricValue, suffix: str) -> str:
    return f"{anchor.company_id}-{anchor.fiscal_year}-{suffix}"


def _missing_inputs(
    output_id: str,
    anchor: MetricValue,
    unit: str,
    inputs: tuple[MetricValue, ...],
    *,
    name: str | None = None,
    formula_id: str,
    expression: str,
) -> MetricValue | None:
    missing = tuple(item.metric_id for item in inputs if not item.is_available)
    if not missing:
        return None
    return unavailable_metric(
        metric_id=output_id,
        company_id=anchor.company_id,
        fiscal_year=anchor.fiscal_year,
        name=name or output_id.rsplit("-", maxsplit=1)[-1],
        unit=unit,
        note="Unavailable because input metrics are unavailable: " + ", ".join(missing),
        sources=merged_sources(inputs),
        input_metric_ids=tuple(item.metric_id for item in inputs),
        formula_id=formula_id,
        expression=expression,
    )


def _not_comparable(
    output_id: str,
    anchor: MetricValue,
    unit: str,
    inputs: tuple[MetricValue, ...],
    note: str,
    *,
    name: str | None = None,
    formula_id: str,
    expression: str,
) -> MetricValue:
    return unavailable_metric(
        metric_id=output_id,
        company_id=anchor.company_id,
        fiscal_year=anchor.fiscal_year,
        name=name or output_id.rsplit("-", maxsplit=1)[-1],
        unit=unit,
        note=note,
        status="not_comparable",
        sources=merged_sources(inputs),
        input_metric_ids=tuple(item.metric_id for item in inputs),
        formula_id=formula_id,
        expression=expression,
    )


def _require_same_unit(left: MetricValue, right: MetricValue) -> None:
    if left.unit != right.unit:
        raise EquityValidationError("calculation inputs must use the same unit.")


def _require_same_period(left: MetricValue, right: MetricValue) -> None:
    if left.fiscal_year != right.fiscal_year:
        raise EquityValidationError("calculation inputs must use the same fiscal year.")
