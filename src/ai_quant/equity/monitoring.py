"""Deterministic annual monitoring table for the bounded Equity universe."""

from __future__ import annotations

from typing import Literal

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.climate import build_climate_metrics
from ai_quant.equity.formatting import format_metric
from ai_quant.equity.models import FundamentalAnalysis, MetricValue
from ai_quant.equity.repository import EquityRepository, load_equity_repository
from ai_quant.equity.valuation import ValuationAnalysis, build_valuation_analysis
from ai_quant.trust.models import Identifier, NonEmptyText, StrictModel


class MonitoringRow(StrictModel):
    """One non-predictive KPI observation with source and freshness."""

    schema_version: Literal["equity-monitoring-row.v1"] = "equity-monitoring-row.v1"
    monitoring_id: Identifier
    company: Literal["Bachem", "Siegfried"]
    kpi: NonEmptyText
    metric_id: NonEmptyText
    latest_value: float | None
    display_value: NonEmptyText
    unit: NonEmptyText
    fiscal_year: Literal[2025]
    desired_direction_or_threshold: NonEmptyText
    reason: NonEmptyText
    source_uris: tuple[NonEmptyText, ...]
    update_frequency: Literal["annual"] = "annual"
    freshness: Literal["available", "to_update"]
    assurance: NonEmptyText
    predictive: Literal[False] = False


_KPI_POLICY = {
    "revenue_yoy_growth": (
        "Revenue growth",
        "Positive or improving direction; descriptive, not predictive",
        "Tracks the latest reported top-line momentum.",
    ),
    "ebitda_margin": (
        "EBITDA margin",
        "Stable or improving on the disclosed EBITDA definition",
        "Tracks operating profitability before depreciation and amortization.",
    ),
    "ebit_margin": (
        "EBIT margin",
        "Stable or improving",
        "Tracks profitability after depreciation and amortization.",
    ),
    "calculated_fcf_cash_conversion": (
        "Calculated FCF cash conversion",
        "Toward positive conversion, with capex context",
        "Tracks how calculated free cash flow compares with EBITDA.",
    ),
    "capex_calculated_to_revenue": (
        "Calculated capex to revenue",
        "Interpret with capacity investment context; no universal threshold",
        "Makes capital intensity visible without treating lower capex as automatically better.",
    ),
    "net_debt_to_ebitda": (
        "Net debt to EBITDA",
        "Stable or lower, subject to capital-allocation context",
        "Tracks balance-sheet leverage on the approved EBITDA definition.",
    ),
    "return_on_period_end_equity": (
        "ROE on period-end equity",
        "Stable or improving, interpreted with leverage",
        "Tracks earnings relative to period-end equity.",
    ),
    "scope_1_2_market_based_intensity": (
        "Scope one and two market-based intensity",
        "Lower on an unchanged boundary and methodology",
        "Tracks operational carbon intensity with assurance kept visible.",
    ),
    "price_to_earnings_published": (
        "Published price to earnings",
        "Update only when an issuer-published value enters the authorized pipeline",
        "Keeps the known Bachem source gap visible rather than substituting a value.",
    ),
}


def build_monitoring_rows(
    *,
    repository: EquityRepository | None = None,
    fundamentals: FundamentalAnalysis | None = None,
    valuation: ValuationAnalysis | None = None,
    climate_metrics: tuple[MetricValue, ...] | None = None,
) -> tuple[MonitoringRow, ...]:
    """Build available and explicitly missing FY2025 KPI rows without forecasts."""

    repository = repository or load_equity_repository()
    fundamentals = fundamentals or build_fundamental_analysis(repository)
    valuation = valuation or build_valuation_analysis(repository, fundamentals)
    climate_metrics = climate_metrics or build_climate_metrics(repository)
    climate_by_company = {
        metric.company_id: metric
        for metric in climate_metrics
        if metric.name == "scope_1_2_market_based_intensity"
    }
    rows: list[MonitoringRow] = []
    for company_id, company_label in (
        ("bachem", "Bachem"),
        ("siegfried", "Siegfried"),
    ):
        metrics = [
            fundamentals.metric(company_id, 2025, name)
            for name in (
                "revenue_yoy_growth",
                "ebitda_margin",
                "ebit_margin",
                "calculated_fcf_cash_conversion",
                "capex_calculated_to_revenue",
                "net_debt_to_ebitda",
                "return_on_period_end_equity",
            )
        ]
        metrics.append(climate_by_company[company_id])
        if company_id == "bachem":
            metrics.append(
                valuation.metric(company_id, 2025, "price_to_earnings_published")
            )
        rows.extend(_monitoring_row(company_label, metric) for metric in metrics)
    return tuple(rows)


def monitoring_table_rows(rows: tuple[MonitoringRow, ...]) -> tuple[dict[str, object], ...]:
    """Return presentation rows while preserving the authoritative raw value."""

    return tuple(
        {
            "Company": row.company,
            "KPI": row.kpi,
            "Latest authorized value": row.display_value,
            "Raw value": row.latest_value,
            "Unit": row.unit,
            "Fiscal year": f"FY{row.fiscal_year}",
            "Descriptive direction / threshold": row.desired_direction_or_threshold,
            "Monitoring rationale": row.reason,
            "Source": " · ".join(row.source_uris),
            "Frequency": row.update_frequency,
            "Freshness": row.freshness,
            "Assurance": row.assurance,
        }
        for row in rows
    )


def _monitoring_row(
    company: Literal["Bachem", "Siegfried"],
    metric: MetricValue,
) -> MonitoringRow:
    kpi, direction, reason = _KPI_POLICY[metric.name]
    source_uris = tuple(dict.fromkeys(source.source_uri for source in metric.sources))
    if not source_uris:
        source_uris = ("src/ai_quant/fixtures/equity/manifest.v1.json",)
    return MonitoringRow(
        monitoring_id=(
            f"monitor-{metric.company_id}-{metric.fiscal_year}-"
            f"{metric.name.replace('_', '-')}"
        ),
        company=company,
        kpi=kpi,
        metric_id=metric.metric_id,
        latest_value=float(metric.value) if metric.value is not None else None,
        display_value=format_metric(metric),
        unit=metric.unit,
        fiscal_year=2025,
        desired_direction_or_threshold=direction,
        reason=reason,
        source_uris=source_uris,
        freshness="available" if metric.is_available else "to_update",
        assurance=metric.assurance or "not_disclosed",
        predictive=False,
    )
