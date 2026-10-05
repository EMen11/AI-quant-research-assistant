from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from ai_quant.equity import (
    Company,
    EquityValidationError,
    FiscalPeriod,
    MetricValue,
    SourceReference,
    capex_to_revenue,
    cash_conversion,
    climate_intensity,
    compound_annual_growth,
    dividend_yield,
    enterprise_value,
    fcf_yield,
    format_metric,
    free_cash_flow,
    leverage,
    margin,
    market_capitalization,
    net_debt,
    normalize_emissions,
    payout_ratio,
    return_on_equity,
    unavailable_metric,
    valuation_multiple,
    year_over_year_growth,
)

SHA = "a" * 64


def source(field: str, year: int = 2025, *, source_unit: str = "CHF million") -> SourceReference:
    return SourceReference(
        source_id=f"bachem-{year}-{field}",
        document=f"Bachem Annual Report {year}",
        fiscal_year=year,
        field=field,
        source_unit=source_unit,
        method="reported",
        source_uri=f"reports/BANB.SW/{year}.pdf",
        document_sha256=SHA,
        page=42,
    )


def metric(
    name: str,
    value: str,
    *,
    year: int = 2025,
    unit: str = "CHF_millions",
    company_id: str = "bachem",
) -> MetricValue:
    return MetricValue(
        metric_id=f"{company_id}-{year}-{name}",
        company_id=company_id,
        fiscal_year=year,
        name=name,
        value=Decimal(value),
        unit=unit,
        status="reported",
        sources=(source(name, year, source_unit=unit),),
    )


def test_company_period_source_and_metric_are_immutable() -> None:
    company = Company("bachem", "BANB.SW", "Bachem Holding AG")
    period = FiscalPeriod(2025, date(2025, 12, 31))
    revenue = metric("revenue", "695.07")

    assert period.fiscal_year == 2025
    with pytest.raises(FrozenInstanceError):
        company.name = "Changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        revenue.value = Decimal("0")  # type: ignore[misc]


def test_reported_metric_requires_provenance_and_finite_value() -> None:
    with pytest.raises(EquityValidationError, match="field-level provenance"):
        MetricValue("x", "bachem", 2025, "revenue", Decimal("1"), "CHF_millions", "reported")
    with pytest.raises(EquityValidationError, match="finite"):
        MetricValue(
            "x",
            "bachem",
            2025,
            "revenue",
            Decimal("NaN"),
            "CHF_millions",
            "reported",
            (source("revenue"),),
        )


def test_missing_value_remains_explicit_and_never_becomes_zero() -> None:
    missing = unavailable_metric(
        metric_id="bachem-2025-ebitda",
        company_id="bachem",
        fiscal_year=2025,
        name="ebitda",
        unit="CHF_millions",
        note="Not reported.",
    )
    result = margin(missing, metric("revenue", "100"), name="ebitda")

    assert result.status == "unavailable"
    assert result.value is None
    assert missing.metric_id in result.note


def test_growth_and_cagr_use_exact_fiscal_intervals() -> None:
    current = metric("revenue", "150", year=2025)
    previous = metric("revenue", "120", year=2024)
    start = metric("revenue", "100", year=2021)

    assert year_over_year_growth(current, previous).value == Decimal("25.00")
    cagr = compound_annual_growth(current, start)
    assert float(cagr.value) == pytest.approx(0.1066819 * 100)
    assert cagr.note == "4 fiscal-year intervals."


def test_growth_is_not_comparable_when_prior_value_is_zero() -> None:
    result = year_over_year_growth(metric("revenue", "10"), metric("revenue", "0", year=2024))
    assert result.status == "not_comparable"
    assert result.value is None


def test_margin_and_cash_conversion_abstain_on_invalid_denominators() -> None:
    profit = metric("ebit", "20")
    revenue = metric("revenue", "100")

    assert margin(profit, revenue, name="ebit").value == Decimal("20.0")
    invalid = cash_conversion(metric("fcf", "10"), metric("ebitda", "0"))
    assert invalid.status == "not_comparable"


def test_signed_capex_fcf_and_capex_intensity_are_unambiguous() -> None:
    operating_cash_flow = metric("operating_cash_flow", "200")
    capex = metric("capex_calculated", "-75")
    revenue = metric("revenue", "500")

    fcf = free_cash_flow(operating_cash_flow, capex)
    assert fcf.value == Decimal("125")
    assert capex_to_revenue(capex, revenue).value == Decimal("15.00")
    assert "signed cash outflow" in fcf.note


def test_net_debt_leverage_roe_and_payout() -> None:
    debt = metric("total_debt", "300")
    cash = metric("cash", "80")
    ebitda = metric("ebitda", "110")
    income = metric("net_income", "50")
    equity = metric("total_equity", "400")
    distributions = metric("distributions", "-20")

    net_debt_metric = net_debt(debt, cash)
    assert net_debt_metric.value == Decimal("220")
    assert leverage(net_debt_metric, ebitda).value == Decimal("2")
    assert return_on_equity(income, equity).value == Decimal("12.500")
    assert "period-end equity" in return_on_equity(income, equity).note
    assert payout_ratio(distributions, income).value == Decimal("40.0")


def test_calculated_metrics_inherit_all_field_level_sources() -> None:
    result = net_debt(metric("total_debt", "100"), metric("cash", "25"))

    assert result.status == "calculated"
    assert result.formula.version == "equity-formulas.v1"
    assert result.input_metric_ids == ("bachem-2025-total_debt", "bachem-2025-cash")
    assert {item.field for item in result.sources} == {"total_debt", "cash"}


def test_cross_company_calculation_is_rejected() -> None:
    with pytest.raises(EquityValidationError, match="same company"):
        margin(
            metric("ebit", "10", company_id="bachem"),
            metric("revenue", "100", company_id="siegfried"),
            name="ebit",
        )


def test_published_market_cap_is_authoritative() -> None:
    published = metric("market_capitalization_published", "4493")
    price = metric("year_end_share_price", "59.9", unit="CHF_per_share")
    shares = metric("registered_shares", "75000000", unit="shares")

    selected = market_capitalization(
        published=published,
        year_end_share_price=price,
        registered_shares=shares,
    )

    assert selected is published
    assert selected.value == Decimal("4493")


def test_market_cap_fallback_is_clearly_calculated() -> None:
    result = market_capitalization(
        published=None,
        year_end_share_price=metric("year_end_share_price", "20", unit="CHF_per_share"),
        registered_shares=metric("registered_shares", "5000000", unit="shares"),
    )

    assert result.value == Decimal("100")
    assert result.status == "calculated"
    assert "Fallback calculation" in result.note


def test_enterprise_value_multiples_and_yields() -> None:
    market_cap = metric("market_capitalization", "1000")
    net_debt_metric = metric("net_debt", "200")
    ebitda = metric("ebitda", "100")
    fcf = metric("free_cash_flow", "50")

    ev = enterprise_value(market_cap, net_debt_metric)
    assert ev.value == Decimal("1200")
    assert valuation_multiple(ev, ebitda, name="ev_to_ebitda").value == Decimal("12")
    assert fcf_yield(fcf, market_cap).value == Decimal("5.00")


def test_multiple_is_not_calculated_for_non_positive_denominator() -> None:
    result = valuation_multiple(
        metric("market_capitalization", "1000"),
        metric("net_income", "-5"),
        name="price_to_earnings",
    )
    assert result.status == "not_comparable"
    assert result.value is None


def test_dividend_yield_uses_same_basis_per_share_values() -> None:
    result = dividend_yield(
        metric("dividend_per_share", "0.9", unit="CHF_per_share"),
        metric("year_end_share_price", "60", unit="CHF_per_share"),
    )
    assert result.value == Decimal("1.500")


def test_emissions_normalization_preserves_source_value_and_metadata() -> None:
    source_metric = MetricValue(
        metric_id="bachem-2025-scope2",
        company_id="bachem",
        fiscal_year=2025,
        name="scope2",
        value=Decimal("2.5"),
        unit="ktCO2e",
        status="reported",
        sources=(source("scope2", source_unit="ktCO2e"),),
        scope2_method="location_based",
        assurance="limited",
    )

    normalized = normalize_emissions(source_metric)
    assert normalized.value == Decimal("2500.0")
    assert source_metric.value == Decimal("2.5")
    assert normalized.scope2_method == "location_based"
    assert normalized.assurance == "limited"


def test_climate_intensity_carries_metric_level_method_and_assurance() -> None:
    scope1 = metric("scope1", "1000", unit="tCO2e")
    scope2 = metric("scope2", "500", unit="tCO2e")
    revenue = metric("revenue", "750")

    result = climate_intensity(
        scope1,
        scope2,
        revenue,
        scope2_method="location_based",
        assurance="limited",
    )

    assert result.value == Decimal("2")
    assert result.scope2_method == "location_based"
    assert result.assurance == "limited"


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (metric("revenue", "1234.56"), "CHF 1,234.6m"),
        (metric("margin", "12.34", unit="percent"), "12.3%"),
        (metric("multiple", "8.44", unit="multiple"), "8.4x"),
        (metric("scope1", "1234", unit="tCO2e"), "1,234 tCO₂e"),
    ],
)
def test_formatting_is_unit_aware(item: MetricValue, expected: str) -> None:
    assert format_metric(item) == expected


def test_unavailable_formatting_is_an_em_dash() -> None:
    item = unavailable_metric(
        metric_id="bachem-2025-pe",
        company_id="bachem",
        fiscal_year=2025,
        name="price_to_earnings",
        unit="multiple",
        note="Negative earnings.",
        status="not_comparable",
    )
    assert format_metric(item) == "—"
