"""Phase 3 deterministic fundamentals analysis over embedded FY2021-FY2025 fixtures."""

from __future__ import annotations

from decimal import Decimal

from ai_quant.equity.fundamentals import (
    capex_to_revenue,
    cash_conversion,
    compound_annual_growth,
    estimated_cash_distribution,
    free_cash_flow,
    leverage,
    margin,
    net_debt,
    payout_ratio,
    return_on_equity,
    year_over_year_growth,
)
from ai_quant.equity.models import (
    ConcordanceCheck,
    EquityValidationError,
    FundamentalAnalysis,
    MetricValue,
    calculated_metric,
    unavailable_metric,
)
from ai_quant.equity.repository import (
    COMPANY_IDS,
    EXPECTED_TICKERS,
    EXPECTED_YEARS,
    EquityRepository,
    load_equity_repository,
)

PHASE3_SOURCE_METRICS = frozenset(
    {
        "revenue",
        "ebitda",
        "ebit",
        "depreciation_amortization",
        "net_income",
        "dividend_per_share",
        "total_assets",
        "total_equity",
        "cash",
        "total_debt",
        "operating_cash_flow",
        "capex_reported",
        "capex_calculated",
        "free_cash_flow_reported",
        "free_cash_flow_calculated",
        "equity_ratio",
        "registered_shares",
    }
)


def build_fundamental_analysis(
    repository: EquityRepository | None = None,
) -> FundamentalAnalysis:
    """Compute the complete V4.1 Phase 3 fundamental metric set deterministically."""

    repository = repository or load_equity_repository()
    source_metrics = tuple(
        item for item in repository.metrics if item.name in PHASE3_SOURCE_METRICS
    )
    derived: list[MetricValue] = []
    checks: list[ConcordanceCheck] = []

    for ticker in EXPECTED_TICKERS:
        company_id = COMPANY_IDS[ticker]
        for year in EXPECTED_YEARS:
            revenue = repository.metric(ticker, year, "revenue")
            ebitda = repository.metric(ticker, year, "ebitda")
            ebit = repository.metric(ticker, year, "ebit")
            depreciation = repository.metric(ticker, year, "depreciation_amortization")
            net_income = repository.metric(ticker, year, "net_income")
            operating_cf = repository.metric(ticker, year, "operating_cash_flow")
            capex_reported = repository.metric(ticker, year, "capex_reported")
            capex_calculated = repository.metric(ticker, year, "capex_calculated")
            fcf_reported = repository.metric(ticker, year, "free_cash_flow_reported")
            fcf_calculated = repository.metric(ticker, year, "free_cash_flow_calculated")
            cash = repository.metric(ticker, year, "cash")
            total_debt = repository.metric(ticker, year, "total_debt")
            total_equity = repository.metric(ticker, year, "total_equity")
            total_assets = repository.metric(ticker, year, "total_assets")
            dividend_per_share = repository.metric(ticker, year, "dividend_per_share")
            registered_shares = repository.metric(ticker, year, "registered_shares")

            if year == EXPECTED_YEARS[0]:
                revenue_growth = unavailable_metric(
                    metric_id=f"{company_id}-{year}-revenue-yoy-growth",
                    company_id=company_id,
                    fiscal_year=year,
                    name="revenue_yoy_growth",
                    unit="percent",
                    note="FY2020 is outside the approved Phase 3 fixture window.",
                    sources=revenue.sources,
                    input_metric_ids=(revenue.metric_id,),
                    formula_id="year-over-year-growth",
                    expression="(current / previous - 1) * 100",
                )
            else:
                previous_revenue = repository.metric(ticker, year - 1, "revenue")
                revenue_growth = year_over_year_growth(
                    revenue,
                    previous_revenue,
                    name="revenue_yoy_growth",
                )

            fcf_recomputed = free_cash_flow(
                operating_cf,
                capex_calculated,
                name="free_cash_flow_recomputed",
            )
            net_debt_metric = net_debt(total_debt, cash)
            distribution = estimated_cash_distribution(
                dividend_per_share,
                registered_shares,
            )
            ebitda_from_components = _sum_metric(
                ebit,
                depreciation,
                name="ebitda_from_ebit_and_depreciation",
                formula_id="ebit-plus-depreciation-amortization",
                expression="ebit + depreciation_amortization",
            )
            equity_ratio = margin(
                total_equity,
                total_assets,
                name="equity_ratio_recomputed",
            )

            derived.extend(
                (
                    revenue_growth,
                    margin(ebitda, revenue, name="ebitda_margin"),
                    margin(ebit, revenue, name="ebit_margin"),
                    margin(net_income, revenue, name="net_margin"),
                    margin(
                        operating_cf,
                        revenue,
                        name="operating_cash_flow_to_revenue",
                    ),
                    capex_to_revenue(
                        capex_reported,
                        revenue,
                        name="capex_reported_to_revenue",
                    ),
                    capex_to_revenue(
                        capex_calculated,
                        revenue,
                        name="capex_calculated_to_revenue",
                    ),
                    fcf_recomputed,
                    cash_conversion(
                        fcf_reported,
                        ebitda,
                        name="reported_fcf_cash_conversion",
                    ),
                    cash_conversion(
                        fcf_calculated,
                        ebitda,
                        name="calculated_fcf_cash_conversion",
                    ),
                    net_debt_metric,
                    leverage(net_debt_metric, ebitda),
                    return_on_equity(net_income, total_equity),
                    distribution,
                    payout_ratio(distribution, net_income),
                    ebitda_from_components,
                    equity_ratio,
                )
            )
            checks.append(
                _concordance_check(
                    source=fcf_calculated,
                    recomputed=fcf_recomputed,
                    name="free_cash_flow_calculated",
                    tolerance=Decimal("0.001"),
                    note=(
                        "Checks source calculated FCF against operating cash flow plus "
                        "signed calculated capex."
                    ),
                )
            )
            if ebitda.status == "calculated":
                checks.append(
                    _concordance_check(
                        source=ebitda,
                        recomputed=ebitda_from_components,
                        name="ebitda_calculated",
                        tolerance=Decimal("0.05"),
                        note="Allows source rounding to the nearest CHF 0.1 million.",
                    )
                )
            source_equity_ratio = repository.metric(ticker, year, "equity_ratio")
            checks.append(
                _concordance_check(
                    source=source_equity_ratio,
                    recomputed=equity_ratio,
                    name="equity_ratio",
                    tolerance=Decimal("0.01"),
                    note="Checks period-end equity divided by total assets.",
                )
            )

        revenue_start = repository.metric(ticker, EXPECTED_YEARS[0], "revenue")
        revenue_end = repository.metric(ticker, EXPECTED_YEARS[-1], "revenue")
        derived.append(
            compound_annual_growth(
                revenue_end,
                revenue_start,
                name="revenue_cagr_2021_2025",
            )
        )

    return FundamentalAnalysis(
        source_metrics=tuple(sorted(source_metrics, key=lambda item: item.metric_id)),
        derived_metrics=tuple(sorted(derived, key=lambda item: item.metric_id)),
        concordance_checks=tuple(sorted(checks, key=lambda item: item.check_id)),
        periods=EXPECTED_YEARS,
    )


def _sum_metric(
    left: MetricValue,
    right: MetricValue,
    *,
    name: str,
    formula_id: str,
    expression: str,
) -> MetricValue:
    if left.company_id != right.company_id or left.fiscal_year != right.fiscal_year:
        raise EquityValidationError("sum inputs must use the same company and fiscal year.")
    if left.unit != right.unit:
        raise EquityValidationError("sum inputs must use the same unit.")
    metric_id = f"{left.company_id}-{left.fiscal_year}-{name.replace('_', '-')}"
    if not left.is_available or not right.is_available:
        missing = tuple(item.metric_id for item in (left, right) if not item.is_available)
        return unavailable_metric(
            metric_id=metric_id,
            company_id=left.company_id,
            fiscal_year=left.fiscal_year,
            name=name,
            unit=left.unit,
            note="Unavailable because input metrics are unavailable: " + ", ".join(missing),
            sources=tuple(
                {source.source_id: source for item in (left, right) for source in item.sources}.values()
            ),
            input_metric_ids=(left.metric_id, right.metric_id),
            formula_id=formula_id,
            expression=expression,
        )
    return calculated_metric(
        metric_id=metric_id,
        company_id=left.company_id,
        fiscal_year=left.fiscal_year,
        name=name,
        value=left.value + right.value,
        unit=left.unit,
        formula_id=formula_id,
        expression=expression,
        inputs=(left, right),
    )


def _concordance_check(
    *,
    source: MetricValue,
    recomputed: MetricValue,
    name: str,
    tolerance: Decimal,
    note: str,
) -> ConcordanceCheck:
    if source.company_id != recomputed.company_id or source.fiscal_year != recomputed.fiscal_year:
        raise EquityValidationError(
            "concordance inputs must use the same company and fiscal year."
        )
    if source.unit != recomputed.unit:
        raise EquityValidationError("concordance inputs must use the same unit.")
    check_id = f"{source.company_id}-{source.fiscal_year}-{name}-concordance"
    if not source.is_available or not recomputed.is_available:
        return ConcordanceCheck(
            check_id=check_id,
            company_id=source.company_id,
            fiscal_year=source.fiscal_year,
            name=name,
            status="unavailable",
            source_metric_id=source.metric_id,
            recomputed_metric_id=recomputed.metric_id,
            source_value=None,
            recomputed_value=None,
            absolute_difference=None,
            tolerance=tolerance,
            unit=source.unit,
            note=note,
        )
    difference = abs(source.value - recomputed.value)
    return ConcordanceCheck(
        check_id=check_id,
        company_id=source.company_id,
        fiscal_year=source.fiscal_year,
        name=name,
        status="pass" if difference <= tolerance else "mismatch",
        source_metric_id=source.metric_id,
        recomputed_metric_id=recomputed.metric_id,
        source_value=source.value,
        recomputed_value=recomputed.value,
        absolute_difference=difference,
        tolerance=tolerance,
        unit=source.unit,
        note=note,
    )
