"""Historical closing-date valuation formulas."""

from __future__ import annotations

from decimal import Decimal

from ai_quant.equity.fundamentals import _not_comparable
from ai_quant.equity.models import (
    EquityValidationError,
    MetricValue,
    calculated_metric,
    merged_sources,
    require_compatible_inputs,
    unavailable_metric,
)

ONE_HUNDRED = Decimal("100")
ONE_MILLION = Decimal("1000000")


def market_capitalization(
    *,
    published: MetricValue | None,
    year_end_share_price: MetricValue | None,
    registered_shares: MetricValue | None,
) -> MetricValue:
    """Prefer published market cap; otherwise keep a clearly calculated fallback."""

    available_published = published is not None and published.is_available
    if available_published:
        if published.unit != "CHF_millions":
            raise EquityValidationError("published market cap must use CHF_millions.")
        return published
    if year_end_share_price is None or registered_shares is None:
        anchor = published or year_end_share_price or registered_shares
        if anchor is None:
            raise EquityValidationError("market capitalization requires at least one input.")
        inputs = tuple(
            item
            for item in (published, year_end_share_price, registered_shares)
            if item is not None
        )
        return unavailable_metric(
            metric_id=f"{anchor.company_id}-{anchor.fiscal_year}-market-capitalization",
            company_id=anchor.company_id,
            fiscal_year=anchor.fiscal_year,
            name="market_capitalization",
            unit="CHF_millions",
            note="Published market cap is missing and fallback inputs are incomplete.",
            sources=merged_sources(inputs),
            input_metric_ids=tuple(item.metric_id for item in inputs),
        )
    require_compatible_inputs(year_end_share_price, registered_shares)
    if year_end_share_price.fiscal_year != registered_shares.fiscal_year:
        raise EquityValidationError("market cap fallback inputs must use the same fiscal year.")
    if not year_end_share_price.is_available or not registered_shares.is_available:
        return unavailable_metric(
            metric_id=(
                f"{year_end_share_price.company_id}-{year_end_share_price.fiscal_year}"
                "-market-capitalization"
            ),
            company_id=year_end_share_price.company_id,
            fiscal_year=year_end_share_price.fiscal_year,
            name="market_capitalization",
            unit="CHF_millions",
            note="Published market cap is missing and a fallback input is unavailable.",
            sources=merged_sources((year_end_share_price, registered_shares)),
            input_metric_ids=(year_end_share_price.metric_id, registered_shares.metric_id),
        )
    if year_end_share_price.unit != "CHF_per_share" or registered_shares.unit != "shares":
        raise EquityValidationError(
            "market cap fallback requires CHF_per_share and shares inputs."
        )
    return calculated_metric(
        metric_id=(
            f"{year_end_share_price.company_id}-{year_end_share_price.fiscal_year}"
            "-market-capitalization-calculated"
        ),
        company_id=year_end_share_price.company_id,
        fiscal_year=year_end_share_price.fiscal_year,
        name="market_capitalization_calculated",
        value=year_end_share_price.value * registered_shares.value / ONE_MILLION,
        unit="CHF_millions",
        formula_id="share-price-times-registered-shares",
        expression="year_end_share_price * registered_shares / 1_000_000",
        inputs=(year_end_share_price, registered_shares),
        note=(
            "Fallback calculation; it may differ from published market cap because registered "
            "shares can include treasury shares."
        ),
    )


def enterprise_value(market_cap: MetricValue, net_debt: MetricValue) -> MetricValue:
    """Calculate enterprise value as equity value plus net debt."""

    require_compatible_inputs(market_cap, net_debt)
    _same_period_and_chf_millions(market_cap, net_debt)
    output_id = f"{market_cap.company_id}-{market_cap.fiscal_year}-enterprise-value"
    if not market_cap.is_available or not net_debt.is_available:
        return unavailable_metric(
            metric_id=output_id,
            company_id=market_cap.company_id,
            fiscal_year=market_cap.fiscal_year,
            name="enterprise_value",
            unit="CHF_millions",
            note="Enterprise value requires both market capitalization and net debt.",
            sources=merged_sources((market_cap, net_debt)),
            input_metric_ids=(market_cap.metric_id, net_debt.metric_id),
        )
    return calculated_metric(
        metric_id=output_id,
        company_id=market_cap.company_id,
        fiscal_year=market_cap.fiscal_year,
        name="enterprise_value",
        value=market_cap.value + net_debt.value,
        unit="CHF_millions",
        formula_id="enterprise-value",
        expression="market_capitalization + net_debt",
        inputs=(market_cap, net_debt),
    )


def valuation_multiple(
    numerator: MetricValue,
    denominator: MetricValue,
    *,
    name: str,
) -> MetricValue:
    """Calculate a closing-date multiple, abstaining on non-positive denominators."""

    require_compatible_inputs(numerator, denominator)
    _same_period_and_chf_millions(numerator, denominator)
    output_id = f"{numerator.company_id}-{numerator.fiscal_year}-{name}"
    if not numerator.is_available or not denominator.is_available:
        return unavailable_metric(
            metric_id=output_id,
            company_id=numerator.company_id,
            fiscal_year=numerator.fiscal_year,
            name=name,
            unit="multiple",
            note="Valuation multiple requires both inputs.",
            sources=merged_sources((numerator, denominator)),
            input_metric_ids=(numerator.metric_id, denominator.metric_id),
            formula_id=name,
            expression="valuation_numerator / financial_denominator",
        )
    if numerator.value < 0 or denominator.value <= 0:
        return _not_comparable(
            output_id,
            numerator,
            "multiple",
            (numerator, denominator),
            "Valuation multiples require a non-negative numerator and positive denominator.",
            name=name,
            formula_id=name,
            expression="valuation_numerator / financial_denominator",
        )
    return calculated_metric(
        metric_id=output_id,
        company_id=numerator.company_id,
        fiscal_year=numerator.fiscal_year,
        name=name,
        value=numerator.value / denominator.value,
        unit="multiple",
        formula_id=name,
        expression="valuation_numerator / financial_denominator",
        inputs=(numerator, denominator),
        note="Historical multiple at the fiscal-year closing date.",
    )


def fcf_yield(free_cash_flow: MetricValue, market_cap: MetricValue) -> MetricValue:
    """Calculate FCF yield; negative FCF remains visible rather than being suppressed."""

    return _yield_metric(
        free_cash_flow,
        market_cap,
        name="free_cash_flow_yield",
        formula_id="free-cash-flow-yield",
        expression="free_cash_flow / market_capitalization * 100",
    )


def dividend_yield(dividend_per_share: MetricValue, share_price: MetricValue) -> MetricValue:
    """Calculate dividend yield from same-basis per-share values."""

    require_compatible_inputs(dividend_per_share, share_price)
    if dividend_per_share.fiscal_year != share_price.fiscal_year:
        raise EquityValidationError("dividend yield inputs must use the same fiscal year.")
    if (
        dividend_per_share.unit != "CHF_per_share"
        or share_price.unit != "CHF_per_share"
    ):
        raise EquityValidationError("dividend yield inputs must use CHF_per_share.")
    return _yield_metric(
        dividend_per_share,
        share_price,
        name="dividend_yield",
        formula_id="dividend-yield",
        expression="dividend_per_share / year_end_share_price * 100",
        require_same_unit=False,
    )


def _yield_metric(
    numerator: MetricValue,
    denominator: MetricValue,
    *,
    name: str,
    formula_id: str,
    expression: str,
    require_same_unit: bool = True,
) -> MetricValue:
    require_compatible_inputs(numerator, denominator)
    if numerator.fiscal_year != denominator.fiscal_year:
        raise EquityValidationError("yield inputs must use the same fiscal year.")
    if require_same_unit and numerator.unit != denominator.unit:
        raise EquityValidationError("yield inputs must use the same unit.")
    output_id = f"{numerator.company_id}-{numerator.fiscal_year}-{name}"
    if not numerator.is_available or not denominator.is_available:
        return unavailable_metric(
            metric_id=output_id,
            company_id=numerator.company_id,
            fiscal_year=numerator.fiscal_year,
            name=name,
            unit="percent",
            note="Yield requires both inputs.",
            sources=merged_sources((numerator, denominator)),
            input_metric_ids=(numerator.metric_id, denominator.metric_id),
            formula_id=formula_id,
            expression=expression,
        )
    if denominator.value <= 0:
        return _not_comparable(
            output_id,
            numerator,
            "percent",
            (numerator, denominator),
            "Yield requires a positive valuation denominator.",
            name=name,
            formula_id=formula_id,
            expression=expression,
        )
    return calculated_metric(
        metric_id=output_id,
        company_id=numerator.company_id,
        fiscal_year=numerator.fiscal_year,
        name=name,
        value=numerator.value / denominator.value * ONE_HUNDRED,
        unit="percent",
        formula_id=formula_id,
        expression=expression,
        inputs=(numerator, denominator),
        note="Historical yield at the fiscal-year closing date.",
    )


def _same_period_and_chf_millions(left: MetricValue, right: MetricValue) -> None:
    if left.fiscal_year != right.fiscal_year:
        raise EquityValidationError("valuation inputs must use the same fiscal year.")
    if left.unit != "CHF_millions" or right.unit != "CHF_millions":
        raise EquityValidationError("valuation inputs must use CHF_millions.")
