from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from ai_quant.equity import (
    EquityRepository,
    EquityValidationError,
    build_fundamental_analysis,
    estimated_cash_distribution,
    load_equity_repository,
)


def test_phase3_builds_complete_deterministic_metric_catalogue() -> None:
    analysis = build_fundamental_analysis()

    assert len(analysis.source_metrics) == 170
    assert len(analysis.derived_metrics) == 172
    assert len(analysis.concordance_checks) == 25
    assert analysis.periods == (2021, 2022, 2023, 2024, 2025)
    assert analysis.formula_version == "equity-formulas.v1"
    assert len({item.metric_id for item in analysis.metrics}) == len(analysis.metrics)


def test_real_revenue_growth_and_cagr_match_independent_arithmetic() -> None:
    analysis = build_fundamental_analysis()

    bachem_growth = analysis.metric("bachem", 2025, "revenue_yoy_growth")
    siegfried_growth = analysis.metric("siegfried", 2025, "revenue_yoy_growth")
    bachem_cagr = analysis.metric("bachem", 2025, "revenue_cagr_2021_2025")
    siegfried_cagr = analysis.metric("siegfried", 2025, "revenue_cagr_2021_2025")

    assert float(bachem_growth.value) == pytest.approx((695.070 / 605.259 - 1) * 100)
    assert float(siegfried_growth.value) == pytest.approx((1327.834 / 1294.573 - 1) * 100)
    assert float(bachem_cagr.value) == pytest.approx(((695.070 / 503.234) ** 0.25 - 1) * 100)
    assert float(siegfried_cagr.value) == pytest.approx(
        ((1327.834 / 1102.423) ** 0.25 - 1) * 100
    )
    assert analysis.metric("bachem", 2021, "revenue_yoy_growth").status == "unavailable"
    assert analysis.metric("siegfried", 2021, "revenue_yoy_growth").value is None


@pytest.mark.parametrize("company_id", ["bachem", "siegfried"])
def test_real_margins_and_operating_cash_flow_are_available(company_id: str) -> None:
    analysis = build_fundamental_analysis()

    for name in (
        "ebitda_margin",
        "ebit_margin",
        "net_margin",
        "operating_cash_flow_to_revenue",
    ):
        metric = analysis.metric(company_id, 2025, name)
        assert metric.status == "calculated"
        assert metric.unit == "percent"
        assert metric.formula.version == "equity-formulas.v1"
        assert len(metric.input_metric_ids) == 2
        assert {source.field for source in metric.sources}

    operating_cf = analysis.metric(company_id, 2025, "operating_cash_flow")
    assert operating_cf.status == "reported"
    assert operating_cf.unit == "CHF_millions"


def test_reported_and_calculated_capex_and_fcf_bases_remain_separate() -> None:
    analysis = build_fundamental_analysis()

    assert analysis.metric("bachem", 2024, "capex_reported").status == "unavailable"
    assert analysis.metric("bachem", 2024, "capex_reported_to_revenue").status == "unavailable"
    assert analysis.metric("bachem", 2024, "capex_calculated").status == "calculated"
    assert analysis.metric("bachem", 2024, "capex_calculated_to_revenue").is_available
    assert analysis.metric("bachem", 2025, "capex_reported_to_revenue").is_available

    assert analysis.metric("siegfried", 2025, "capex_reported_to_revenue").is_available
    assert analysis.metric("siegfried", 2025, "capex_calculated_to_revenue").is_available
    assert analysis.metric("siegfried", 2025, "reported_fcf_cash_conversion").is_available
    assert analysis.metric("siegfried", 2025, "calculated_fcf_cash_conversion").is_available
    assert analysis.metric("bachem", 2025, "reported_fcf_cash_conversion").status == "unavailable"
    assert analysis.metric("bachem", 2025, "calculated_fcf_cash_conversion").is_available


def test_free_cash_flow_recomputation_matches_all_source_calculated_values() -> None:
    analysis = build_fundamental_analysis()
    fcf_checks = [
        item for item in analysis.concordance_checks if item.name == "free_cash_flow_calculated"
    ]

    assert len(fcf_checks) == 10
    assert {item.status for item in fcf_checks} == {"pass"}
    assert all(item.absolute_difference == Decimal("0.000") for item in fcf_checks)
    assert all(item.tolerance == Decimal("0.001") for item in fcf_checks)


def test_source_ratio_concordance_uses_documented_rounding_tolerances() -> None:
    analysis = build_fundamental_analysis()
    ebitda_checks = [item for item in analysis.concordance_checks if item.name == "ebitda_calculated"]
    equity_checks = [item for item in analysis.concordance_checks if item.name == "equity_ratio"]

    assert len(ebitda_checks) == 5
    assert {item.company_id for item in ebitda_checks} == {"siegfried"}
    assert {item.status for item in ebitda_checks} == {"pass"}
    assert max(item.absolute_difference for item in ebitda_checks) <= Decimal("0.05")

    assert len(equity_checks) == 10
    assert sum(item.status == "pass" for item in equity_checks) == 5
    assert sum(item.status == "unavailable" for item in equity_checks) == 5
    assert {item.company_id for item in equity_checks if item.status == "pass"} == {"siegfried"}


@pytest.mark.parametrize("company_id", ["bachem", "siegfried"])
def test_net_debt_leverage_and_roe_are_available_for_every_year(company_id: str) -> None:
    analysis = build_fundamental_analysis()

    for year in analysis.periods:
        assert analysis.metric(company_id, year, "net_debt").is_available
        assert analysis.metric(company_id, year, "net_debt_to_ebitda").is_available
        assert analysis.metric(company_id, year, "return_on_period_end_equity").is_available

    assert analysis.metric("bachem", 2025, "net_debt").value == Decimal("26.404")
    assert analysis.metric("siegfried", 2025, "net_debt").value == Decimal("472.118")


def test_distribution_is_available_only_when_share_count_exists() -> None:
    analysis = build_fundamental_analysis()

    bachem_distribution = analysis.metric("bachem", 2025, "estimated_cash_distribution")
    bachem_payout = analysis.metric("bachem", 2025, "payout_ratio")
    siegfried_distribution = analysis.metric(
        "siegfried", 2025, "estimated_cash_distribution"
    )
    siegfried_payout = analysis.metric("siegfried", 2025, "payout_ratio")

    assert bachem_distribution.value == Decimal("67.441986")
    assert float(bachem_payout.value) == pytest.approx(67.441986 / 148.793 * 100)
    assert siegfried_distribution.status == "unavailable"
    assert siegfried_distribution.value is None
    assert siegfried_payout.status == "unavailable"
    assert "registered-shares" in siegfried_distribution.note


def test_every_available_derived_metric_has_formula_inputs_and_field_provenance() -> None:
    analysis = build_fundamental_analysis()

    available = tuple(item for item in analysis.derived_metrics if item.is_available)
    unavailable = tuple(item for item in analysis.derived_metrics if not item.is_available)
    assert available
    assert unavailable
    assert all(item.status == "calculated" for item in available)
    assert all(item.formula is not None for item in available)
    assert all(item.formula.version == "equity-formulas.v1" for item in available)
    assert all(item.input_metric_ids for item in available)
    assert all(item.sources for item in available)
    assert all(source.field != "locked_snapshot_row" for item in available for source in item.sources)
    assert all(item.value is None for item in unavailable)
    assert all(item.formula is not None for item in unavailable)
    assert all(item.formula.version == "equity-formulas.v1" for item in unavailable)
    assert all(item.input_metric_ids for item in unavailable)
    assert all(item.sources for item in unavailable)


def test_concordance_mismatch_is_visible_and_does_not_overwrite_source() -> None:
    repository = load_equity_repository()
    original = repository.metric("SFZN.SW", 2025, "free_cash_flow_calculated")
    altered = replace(original, value=original.value + Decimal("1"))
    metrics = tuple(altered if item.metric_id == original.metric_id else item for item in repository.metrics)
    modified_repository = EquityRepository(
        metrics=metrics,
        manifest=repository.manifest,
        valuation_diagnostic=repository.valuation_diagnostic,
    )

    analysis = build_fundamental_analysis(modified_repository)
    check = next(
        item
        for item in analysis.concordance_checks
        if item.company_id == "siegfried"
        and item.fiscal_year == 2025
        and item.name == "free_cash_flow_calculated"
    )

    assert check.status == "mismatch"
    assert check.absolute_difference == Decimal("1.000")
    assert analysis.metric("siegfried", 2025, "free_cash_flow_calculated").value == Decimal("-2.31")
    assert analysis.metric("siegfried", 2025, "free_cash_flow_recomputed").value == Decimal("-3.310")


def test_distribution_rejects_incompatible_units_and_non_positive_share_count() -> None:
    repository = load_equity_repository()
    dps = repository.metric("BANB.SW", 2025, "dividend_per_share")
    shares = repository.metric("BANB.SW", 2025, "registered_shares")

    with pytest.raises(EquityValidationError, match="CHF_per_share and shares"):
        estimated_cash_distribution(dps, replace(shares, unit="CHF_millions"))

    invalid = estimated_cash_distribution(dps, replace(shares, value=Decimal("0")))
    assert invalid.status == "not_comparable"
    assert invalid.value is None


def test_phase3_does_not_consume_or_create_blocked_valuation_metrics() -> None:
    analysis = build_fundamental_analysis()
    forbidden = {
        "year_end_share_price",
        "market_capitalization_published",
        "price_to_earnings_published",
    }

    assert not ({item.name for item in analysis.metrics} & forbidden)
    assert all("valuation" not in item.name for item in analysis.derived_metrics)
