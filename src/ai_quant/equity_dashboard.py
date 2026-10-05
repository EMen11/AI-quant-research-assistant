"""Offline Streamlit presentation for deterministic Equity research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.climate import CLIMATE_FIXTURE_CUTOFF, build_climate_metrics
from ai_quant.equity.formatting import format_metric
from ai_quant.equity.models import FundamentalAnalysis, MetricValue, SourceReference
from ai_quant.equity.monitoring import (
    MonitoringRow,
    build_monitoring_rows,
    monitoring_table_rows,
)
from ai_quant.equity.repository import EquityRepository, load_equity_repository
from ai_quant.equity.research import (
    AuthorizedSource,
    EquityResearchResult,
    build_research_note_context,
    run_equity_research_note,
)
from ai_quant.equity.valuation import ValuationAnalysis, build_valuation_analysis
from ai_quant.sustainability import SustainabilityCorpus, load_corpus

COMPANY_LABELS = {"bachem": "Bachem", "siegfried": "Siegfried"}
COMPANY_ORDER = ("bachem", "siegfried")
BLOCKED_SIEGFRIED_VALUATION_FIELDS = (
    "year_end_share_price",
    "registered_shares",
    "market_capitalization_published",
    "price_to_earnings_published",
)


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """Stable UI label for one canonical Equity metric."""

    name: str
    label: str


SNAPSHOT_METRICS = (
    MetricSpec("revenue", "Revenue"),
    MetricSpec("revenue_yoy_growth", "Annual revenue growth"),
    MetricSpec("revenue_cagr_2021_2025", "Revenue CAGR FY2021–FY2025"),
    MetricSpec("ebitda_margin", "EBITDA margin"),
    MetricSpec("ebit_margin", "EBIT margin"),
    MetricSpec("net_margin", "Net margin"),
    MetricSpec("operating_cash_flow", "Operating cash flow"),
    MetricSpec("operating_cash_flow_to_revenue", "Operating cash flow / CA"),
    MetricSpec("free_cash_flow_calculated", "Source-calculated FCF"),
    MetricSpec("calculated_fcf_cash_conversion", "Calculated FCF cash conversion"),
    MetricSpec("net_debt", "Net debt"),
    MetricSpec("net_debt_to_ebitda", "Net debt / EBITDA"),
    MetricSpec("return_on_period_end_equity", "ROE on period-end equity"),
    MetricSpec("equity_ratio_recomputed", "Recomputed equity ratio"),
)

SNAPSHOT_PRIMARY_METRICS = (
    MetricSpec("revenue", "Revenue"),
    MetricSpec("revenue_cagr_2021_2025", "Revenue CAGR FY2021–FY2025"),
    MetricSpec("ebitda_margin", "EBITDA margin"),
    MetricSpec("ebit_margin", "EBIT margin"),
    MetricSpec("calculated_fcf_cash_conversion", "Calculated FCF cash conversion"),
    MetricSpec("net_debt_to_ebitda", "Net debt / EBITDA"),
    MetricSpec("return_on_period_end_equity", "ROE on period-end equity"),
)

RESEARCH_NOTE_COMPARISON_METRICS = (
    *SNAPSHOT_PRIMARY_METRICS,
    MetricSpec("enterprise_value_to_ebitda", "Historical EV / EBITDA"),
)

PRIMARY_FUNDAMENTAL_SECTIONS = (
    (
        "Growth",
        (
            MetricSpec("revenue", "Revenue"),
            MetricSpec("revenue_yoy_growth", "Annual revenue growth"),
            MetricSpec("revenue_cagr_2021_2025", "Revenue CAGR FY2021–FY2025"),
        ),
    ),
    (
        "Profitability",
        (
            MetricSpec("ebitda_margin", "EBITDA margin"),
            MetricSpec("ebit_margin", "EBIT margin"),
            MetricSpec("net_margin", "Net margin"),
        ),
    ),
    (
        "Cash generation",
        (
            MetricSpec("operating_cash_flow", "Operating cash flow"),
            MetricSpec("operating_cash_flow_to_revenue", "Operating cash flow / revenue"),
            MetricSpec("free_cash_flow_calculated", "Source-calculated FCF"),
            MetricSpec("calculated_fcf_cash_conversion", "Calculated FCF cash conversion"),
            MetricSpec("capex_calculated_to_revenue", "Calculated capex / revenue"),
        ),
    ),
    (
        "Balance sheet & returns",
        (
            MetricSpec("net_debt", "Net debt"),
            MetricSpec("net_debt_to_ebitda", "Net debt / EBITDA"),
            MetricSpec("return_on_period_end_equity", "ROE on period-end equity"),
            MetricSpec("equity_ratio_recomputed", "Recomputed equity ratio"),
        ),
    ),
)

FUNDAMENTAL_SECTIONS = (
    (
        "Revenue and growth",
        (
            MetricSpec("revenue", "Revenue"),
            MetricSpec("revenue_yoy_growth", "Annual growth"),
            MetricSpec("revenue_cagr_2021_2025", "CAGR FY2021–FY2025"),
        ),
    ),
    (
        "Margins",
        (
            MetricSpec("ebitda_margin", "EBITDA margin"),
            MetricSpec("ebit_margin", "EBIT margin"),
            MetricSpec("net_margin", "Net margin"),
        ),
    ),
    (
        "Operating cash flow",
        (
            MetricSpec("operating_cash_flow", "Operating cash flow"),
            MetricSpec("operating_cash_flow_to_revenue", "Operating cash flow / CA"),
        ),
    ),
    (
        "Capex / revenue",
        (
            MetricSpec("capex_reported_to_revenue", "Capex reported / CA"),
            MetricSpec("capex_calculated_to_revenue", "Capex calculated / CA"),
        ),
    ),
    (
        "Free cash flow and cash conversion",
        (
            MetricSpec("free_cash_flow_reported", "FCF reported"),
            MetricSpec("free_cash_flow_calculated", "Source-calculated FCF"),
            MetricSpec("free_cash_flow_recomputed", "FCF recomputed by AI Quant"),
            MetricSpec("reported_fcf_cash_conversion", "Reported FCF cash conversion"),
            MetricSpec(
                "calculated_fcf_cash_conversion",
                "Calculated FCF cash conversion",
            ),
        ),
    ),
    (
        "Net debt and leverage",
        (
            MetricSpec("net_debt", "Net debt"),
            MetricSpec("net_debt_to_ebitda", "Net debt / EBITDA"),
        ),
    ),
    (
        "ROE",
        (MetricSpec("return_on_period_end_equity", "ROE on period-end equity"),),
    ),
    (
        "Equity ratio",
        (
            MetricSpec("equity_ratio", "Reported equity ratio"),
            MetricSpec("equity_ratio_recomputed", "Recomputed equity ratio"),
        ),
    ),
)

VALUATION_SECTIONS = (
    (
        "Market value",
        (
            MetricSpec("year_end_share_price", "Historical closing share price"),
            MetricSpec("registered_shares", "Registered shares"),
            MetricSpec(
                "market_capitalization_published",
                "Published market capitalization",
            ),
            MetricSpec(
                "market_capitalization_calculated",
                "Indicative price × shares market capitalization",
            ),
        ),
    ),
    (
        "Trading multiples",
        (
            MetricSpec("enterprise_value", "Enterprise Value"),
            MetricSpec("enterprise_value_to_revenue", "EV / Revenue"),
            MetricSpec("enterprise_value_to_ebitda", "EV / EBITDA"),
            MetricSpec("enterprise_value_to_ebit", "EV / EBIT"),
            MetricSpec("price_to_earnings_published", "Published P/E"),
            MetricSpec("price_to_earnings_calculated", "Calculated P/E"),
            MetricSpec("price_to_book", "Recalculated P/B"),
        ),
    ),
    (
        "Yield metrics",
        (
            MetricSpec("free_cash_flow_yield", "FCF yield (FCF calculated)"),
            MetricSpec("dividend_yield", "Dividend yield"),
        ),
    ),
)

ESG_METRICS = (
    MetricSpec("scope_1_emissions", "Scope 1"),
    MetricSpec("scope_2_market_based_emissions", "Scope 2 · market-based"),
    MetricSpec("scope_2_location_based_emissions", "Scope 2 · location-based"),
    MetricSpec(
        "scope_1_2_market_based_intensity",
        "Scope 1+2 intensity · market-based",
    ),
    MetricSpec(
        "scope_1_2_location_based_intensity",
        "Scope 1+2 intensity · location-based",
    ),
)

_METRIC_LABELS = {
    spec.name: spec.label
    for _, specs in FUNDAMENTAL_SECTIONS
    for spec in specs
} | {
    spec.name: spec.label for spec in SNAPSHOT_METRICS
} | {
    spec.name: spec.label for _, specs in VALUATION_SECTIONS for spec in specs
} | {spec.name: spec.label for spec in ESG_METRICS}


def render_equity_dashboard() -> None:
    """Render the complete offline Equity Research Copilot."""

    repository = load_equity_repository()
    analysis = build_fundamental_analysis(repository)
    valuation = build_valuation_analysis(repository, analysis)
    climate_corpus = load_corpus(CLIMATE_FIXTURE_CUTOFF)
    climate_metrics = build_climate_metrics(repository, climate_corpus)
    research_context = build_research_note_context(
        repository=repository,
        fundamentals=analysis,
        valuation=valuation,
        climate_metrics=climate_metrics,
        corpus=climate_corpus,
    )
    monitoring_rows = build_monitoring_rows(
        repository=repository,
        fundamentals=analysis,
        valuation=valuation,
        climate_metrics=climate_metrics,
    )

    st.title("Equity Research")
    st.caption(
        "Bachem (BANB.SW) / Siegfried (SFZN.SW) · FY2021–FY2025 · "
        "locked local fixtures"
    )
    st.caption(
        "A finance-first view of growth, profitability, cash generation, balance-sheet "
        "strength, returns and historical valuation."
    )
    _render_valuation_limit(repository)

    _render_executive_investment_view(analysis, valuation)

    with st.expander("Data & methodology"):
        st.markdown(
            "Reported figures come from the locked annual source set. Calculated figures "
            "use deterministic Python formulas. Missing or non-comparable values remain "
            "empty; they are never replaced with zero. Historical valuation data refers "
            "to fiscal-year closes and is not current market data."
        )

    (
        snapshot_tab,
        research_note_tab,
        fundamentals_tab,
        valuation_tab,
        monitoring_tab,
        esg_tab,
    ) = st.tabs(
        (
            "Snapshot",
            "Research Note",
            "Fundamentals",
            "Valuation",
            "Monitoring",
            "ESG & Sources",
        )
    )
    with snapshot_tab:
        _render_snapshot(analysis, valuation)
    with research_note_tab:
        scenario_label = st.selectbox(
            "Research note scenario",
            options=("Valid", "Blocked"),
            key="equity-research-note-scenario",
        )
        result = run_equity_research_note(
            "admissible" if scenario_label == "Valid" else "blocked",
            context=research_context,
        )
        _render_research_note(result, analysis, valuation)
    with fundamentals_tab:
        _render_fundamentals(analysis)
    with valuation_tab:
        _render_valuation(valuation, repository)
    with monitoring_tab:
        _render_monitoring(monitoring_rows)
    with esg_tab:
        _render_esg_and_sources(climate_metrics, climate_corpus)


def snapshot_rows(analysis: FundamentalAnalysis) -> tuple[dict[str, str], ...]:
    """Build the FY2025 side-by-side comparison without valuation data."""

    rows: list[dict[str, str]] = []
    for spec in SNAPSHOT_METRICS:
        bachem = analysis.metric("bachem", 2025, spec.name)
        siegfried = analysis.metric("siegfried", 2025, spec.name)
        rows.append(
            {
                "Metric": spec.label,
                "Bachem FY2025": format_metric(bachem),
                "Bachem status": bachem.status,
                "Siegfried FY2025": format_metric(siegfried),
                "Siegfried status": siegfried.status,
            }
        )
    return tuple(rows)


def research_comparison_rows(
    fundamentals: FundamentalAnalysis,
    valuation: ValuationAnalysis,
) -> tuple[dict[str, str], ...]:
    """Build the eight KPI comparison used by the primary research views."""

    rows: list[dict[str, str]] = []
    for spec in RESEARCH_NOTE_COMPARISON_METRICS:
        source = valuation if spec.name == "enterprise_value_to_ebitda" else fundamentals
        rows.append(
            {
                "Metric": spec.label,
                "Bachem FY2025": format_metric(source.metric("bachem", 2025, spec.name)),
                "Siegfried FY2025": format_metric(
                    source.metric("siegfried", 2025, spec.name)
                ),
            }
        )
    return tuple(rows)


def executive_investment_rows(
    fundamentals: FundamentalAnalysis,
    valuation: ValuationAnalysis,
) -> tuple[dict[str, str], ...]:
    """Return six decision-oriented observations backed by existing FY2025 metrics."""

    metrics = (
        ("Growth", fundamentals, "revenue_yoy_growth", "Latest reported momentum"),
        ("Profitability", fundamentals, "ebitda_margin", "Operating margin profile"),
        (
            "Cash generation",
            fundamentals,
            "calculated_fcf_cash_conversion",
            "FCF conversion after capital expenditure",
        ),
        (
            "Balance sheet",
            fundamentals,
            "net_debt_to_ebitda",
            "Leverage on the approved EBITDA definition",
        ),
        (
            "Key watchpoint",
            fundamentals,
            "capex_calculated_to_revenue",
            "Capital intensity relative to revenue",
        ),
        (
            "Historical valuation",
            valuation,
            "enterprise_value_to_ebitda",
            "Fiscal-year-close multiple, not a current quote",
        ),
    )
    return tuple(
        {
            "Research lens": label,
            "Bachem": format_metric(source.metric("bachem", 2025, metric_name)),
            "Siegfried": format_metric(source.metric("siegfried", 2025, metric_name)),
            "What it shows": description,
        }
        for label, source, metric_name, description in metrics
    )


def primary_fundamental_rows(
    analysis: FundamentalAnalysis,
    specs: tuple[MetricSpec, ...],
) -> tuple[dict[str, str], ...]:
    """Build a concise financial table without technical provenance columns."""

    return tuple(
        {
            "Company": COMPANY_LABELS[company_id],
            "Fiscal year": f"FY{year}",
            "Metric": spec.label,
            "Value": format_metric(analysis.metric(company_id, year, spec.name)),
        }
        for company_id in COMPANY_ORDER
        for spec in specs
        for year in _periods_for(spec, analysis)
    )


def primary_valuation_rows(
    analysis: ValuationAnalysis,
    specs: tuple[MetricSpec, ...],
) -> tuple[dict[str, str], ...]:
    """Build concise historical valuation rows for the main analyst view."""

    return tuple(
        {
            "Company": COMPANY_LABELS[company_id],
            "Fiscal year": f"FY{year}",
            "Metric": spec.label,
            "Value": format_metric(analysis.metric(company_id, year, spec.name)),
        }
        for company_id in COMPANY_ORDER
        for spec in specs
        for year in analysis.periods
    )


def primary_monitoring_rows(
    rows: tuple[MonitoringRow, ...],
) -> tuple[dict[str, str], ...]:
    """Build the finance-facing monitoring view while retaining explicit freshness."""

    return tuple(
        {
            "Company": row.company,
            "KPI": row.kpi,
            "Latest value": row.display_value,
            "Why it matters": row.reason,
            "Status": "Available" if row.freshness == "available" else "To update",
        }
        for row in rows
    )


def fundamental_rows(
    analysis: FundamentalAnalysis,
    specs: tuple[MetricSpec, ...],
) -> tuple[dict[str, str], ...]:
    """Build traceable FY2021–FY2025 rows for one fundamentals section."""

    rows: list[dict[str, str]] = []
    for company_id in COMPANY_ORDER:
        for spec in specs:
            for year in _periods_for(spec, analysis):
                metric = analysis.metric(company_id, year, spec.name)
                rows.append(_metric_row(metric, spec.label))
    return tuple(rows)


def valuation_rows(
    analysis: ValuationAnalysis,
    specs: tuple[MetricSpec, ...],
) -> tuple[dict[str, str], ...]:
    """Build traceable historical valuation rows for FY2021-FY2025."""

    return tuple(
        _metric_row(analysis.metric(company_id, year, spec.name), spec.label)
        for company_id in COMPANY_ORDER
        for spec in specs
        for year in analysis.periods
    )


def esg_metric_rows(metrics: tuple[MetricValue, ...]) -> tuple[dict[str, str], ...]:
    """Build FY2025 climate rows while keeping both Scope 2 methods separate."""

    by_coordinate = {
        (metric.company_id, metric.name): metric for metric in metrics
    }
    rows: list[dict[str, str]] = []
    for company_id in COMPANY_ORDER:
        for spec in ESG_METRICS:
            metric = by_coordinate[(company_id, spec.name)]
            row = _metric_row(metric, spec.label)
            row["Scope 2 method"] = metric.scope2_method or "not_applicable"
            row["Assurance"] = metric.assurance or "not_disclosed"
            rows.append(row)
    return tuple(rows)


def primary_esg_metric_rows(
    metrics: tuple[MetricValue, ...],
) -> tuple[dict[str, str], ...]:
    """Build the secondary ESG view without hashes or formula metadata."""

    detailed = esg_metric_rows(metrics)
    return tuple(
        {
            "Company": row["Company"],
            "Metric": row["Metric"],
            "Value": row["Value"],
            "Scope 2 method": row["Scope 2 method"],
            "Assurance": row["Assurance"],
        }
        for row in detailed
    )


def research_source_rows(
    sources: tuple[AuthorizedSource, ...],
) -> tuple[dict[str, str | int], ...]:
    """Build the source list displayed with the Research Note."""

    return tuple(
        {
            "Evidence ID": source.evidence_id,
            "Document": source.title,
            "Page": source.page,
            "Openable source": source.source_uri,
        }
        for source in sources
    )


def primary_research_source_rows(
    sources: tuple[AuthorizedSource, ...],
) -> tuple[dict[str, str | int], ...]:
    """Build a human-readable source list without internal evidence identifiers."""

    return tuple(
        {
            "Document": source.title,
            "Page": source.page,
            "Openable source": source.source_uri,
        }
        for source in sources
    )


def _render_research_note(
    result: EquityResearchResult,
    fundamentals: FundamentalAnalysis,
    valuation: ValuationAnalysis,
) -> None:
    st.header("Research Note — Bachem / Siegfried")
    st.caption(
        "A decision-support note built from authorized annual data. Python supplies and "
        "validates every figure; AI structures the narrative but does not make a final decision."
    )
    st.subheader("Executive summary")
    st.markdown(result.analyst_note.executive_summary)

    if result.review_status == "blocked":
        st.error(
            "Validation blocked this scenario. No reliable research note is shown and it "
            "cannot proceed to human review."
        )
        with st.expander("Validation diagnostics"):
            st.dataframe(
                tuple(
                    {
                        "Code": issue.code,
                        "Severity": issue.severity,
                        "Diagnostic": issue.message,
                    }
                    for issue in result.validation_report.issues
                ),
                hide_index=True,
                width="stretch",
            )
        return

    st.success(
        "Automated validation passed: figures, units, periods, references and citations "
        "match the authorized research context."
    )
    st.warning(
        "Awaiting human review. Automated checks do not constitute analyst approval."
    )

    sections = result.analyst_note.sections.ordered()
    claims_by_title = {
        section.title: claim.text
        for section, claim in zip(sections, result.rendered_draft.claims, strict=True)
    }

    st.subheader("Financial comparison")
    st.dataframe(
        research_comparison_rows(fundamentals, valuation),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Investment case")
    left, right = st.columns(2)
    comparison = {
        row["Metric"]: row
        for row in research_comparison_rows(fundamentals, valuation)
    }
    with left:
        st.markdown("**Bachem**")
        _render_company_case("Bachem FY2025", comparison)
    with right:
        st.markdown("**Siegfried**")
        _render_company_case("Siegfried FY2025", comparison)

    st.subheader("Key risks")
    st.markdown(
        "- **Bachem:** calculated capex / revenue is "
        f"{format_metric(fundamentals.metric('bachem', 2025, 'capex_calculated_to_revenue'))}."
    )
    st.markdown(
        "- **Siegfried:** net debt / EBITDA is "
        f"{comparison['Net debt / EBITDA']['Siegfried FY2025']}."
    )

    st.subheader("Catalysts / What to watch")
    st.markdown(
        "- Later reported improvement can be tracked through calculated FCF cash conversion: "
        f"{comparison['Calculated FCF cash conversion']['Bachem FY2025']} for Bachem and "
        f"{comparison['Calculated FCF cash conversion']['Siegfried FY2025']} for Siegfried."
    )
    st.markdown(
        "- EBIT margin remains an annual monitoring baseline: "
        f"{comparison['EBIT margin']['Bachem FY2025']} for Bachem and "
        f"{comparison['EBIT margin']['Siegfried FY2025']} for Siegfried."
    )
    st.caption("These are monitoring conditions, not forecasts.")

    st.subheader("Valuation context")
    st.markdown(claims_by_title["Relative and historical valuation"])
    st.caption(
        "Historical FY-end data — not current market data. Bachem published P/E is "
        "unavailable; calculated P/E remains a separate metric."
    )

    st.subheader("Sustainability context")
    sustainability_claim = claims_by_title[
        "Sustainability and comparability limitations"
    ].split(" [official corpus evidence:", maxsplit=1)[0]
    st.markdown(f"{sustainability_claim}.")

    st.subheader("Limitations")
    for limitation in result.analyst_note.limitations:
        st.markdown(f"- {limitation.text}")

    with st.expander("Full structured note"):
        kind_labels = {
            "sourced_fact": "Reported fact",
            "calculated_metric": "Calculated metric",
            "analyst_interpretation": "Analyst interpretation",
            "limitation": "Limitation",
        }
        for section, claim in zip(sections, result.rendered_draft.claims, strict=True):
            st.markdown(f"**{section.title}**")
            statement = section.statements[0]
            st.caption(kind_labels[statement.kind])
            st.markdown(claim.text)
            if statement.uncertainty:
                st.caption(f"Caveat: {statement.uncertainty}")

    with st.expander("Authorized sources"):
        st.dataframe(
            primary_research_source_rows(result.context.authorized_sources),
            hide_index=True,
            width="stretch",
        )
        for source in result.context.authorized_sources:
            if source.source_uri.startswith("https://"):
                st.link_button(
                    f"Open {source.title} · p. {source.page}",
                    source.source_uri,
                )
            else:
                st.caption(f"Local source: {source.source_uri}")

    with st.expander("How validation works"):
        st.markdown(
            "1. Python checks that every number, unit and period matches an authorized "
            "metric.\n2. Citations must resolve to the closed evidence set.\n3. Prohibited "
            "recommendations, target prices and unsupported causal claims fail closed."
        )
        st.caption(
            f"Internal routing status: {result.review_status}. No HumanReview object has "
            "been created."
        )
        st.dataframe(
            research_source_rows(result.context.authorized_sources),
            hide_index=True,
            width="stretch",
        )
        st.dataframe(
            tuple(
                {
                    "Limitation ID": limitation.limitation_id,
                    "Required limitation": limitation.text,
                }
                for limitation in result.analyst_note.limitations
            ),
            hide_index=True,
            width="stretch",
        )


def _render_company_case(
    company_column: str,
    comparison: dict[str, dict[str, str]],
) -> None:
    st.markdown(
        f"- Growth and profitability: {comparison['Revenue CAGR FY2021–FY2025'][company_column]} "
        f"revenue CAGR and {comparison['EBITDA margin'][company_column]} EBITDA margin."
    )
    st.markdown(
        f"- Cash and balance sheet: "
        f"{comparison['Calculated FCF cash conversion'][company_column]} cash conversion and "
        f"{comparison['Net debt / EBITDA'][company_column]} net debt / EBITDA."
    )
    st.markdown(
        f"- Historical valuation: "
        f"{comparison['Historical EV / EBITDA'][company_column]} EV / EBITDA at FY2025 close."
    )


def _render_executive_investment_view(
    fundamentals: FundamentalAnalysis,
    valuation: ValuationAnalysis,
) -> None:
    st.header("Executive Investment View")
    st.caption(
        "Six evidence-backed observations to orient the comparison before opening the "
        "supporting detail."
    )
    st.dataframe(
        executive_investment_rows(fundamentals, valuation),
        hide_index=True,
        width="stretch",
    )


def _render_snapshot(
    analysis: FundamentalAnalysis,
    valuation: ValuationAnalysis,
) -> None:
    st.header("Snapshot FY2025")
    st.caption(
        "Eight headline KPIs for a rapid comparison. This is descriptive research, not an "
        "investment ranking."
    )
    st.dataframe(
        research_comparison_rows(analysis, valuation),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Show detailed metrics"):
        st.dataframe(snapshot_rows(analysis), hide_index=True, width="stretch")
    metrics = tuple(
        analysis.metric(company_id, 2025, spec.name)
        for company_id in COMPANY_ORDER
        for spec in SNAPSHOT_METRICS
    )
    _render_metric_inspector(metrics, key="snapshot-metric-inspector")


def _render_fundamentals(analysis: FundamentalAnalysis) -> None:
    st.header("Fundamentals FY2021–FY2025")
    st.caption(
        "The primary view focuses on growth, profitability, cash generation, balance-sheet "
        "strength and returns."
    )
    for section_label, specs in PRIMARY_FUNDAMENTAL_SECTIONS:
        st.subheader(section_label)
        st.dataframe(
            primary_fundamental_rows(analysis, specs),
            hide_index=True,
            width="stretch",
        )

    displayed: list[MetricValue] = []
    with st.expander("View calculation details"):
        for section_label, specs in FUNDAMENTAL_SECTIONS:
            st.markdown(f"**{section_label}**")
            st.dataframe(
                fundamental_rows(analysis, specs),
                hide_index=True,
                width="stretch",
            )
            displayed.extend(
                analysis.metric(company_id, year, spec.name)
                for company_id in COMPANY_ORDER
                for spec in specs
                for year in _periods_for(spec, analysis)
            )
    _render_metric_inspector(tuple(displayed), key="fundamentals-metric-inspector")


def _render_valuation(
    analysis: ValuationAnalysis,
    repository: EquityRepository,
) -> None:
    st.header("Historical valuation FY2021–FY2025")
    st.warning("Historical FY-end data — not current market data.")
    st.caption(
        "Bachem published P/E is unavailable. Calculated P/E is shown separately and does "
        "not replace the missing published field."
    )

    displayed: list[MetricValue] = []
    for section_label, specs in VALUATION_SECTIONS:
        st.subheader(section_label)
        st.dataframe(
            primary_valuation_rows(analysis, specs),
            hide_index=True,
            width="stretch",
        )
        displayed.extend(
            analysis.metric(company_id, year, spec.name)
            for company_id in COMPANY_ORDER
            for spec in specs
            for year in analysis.periods
        )

    with st.expander("View valuation methodology & detailed fields"):
        st.markdown(
            "Published market capitalization and indicative price × shares capitalization "
            "remain distinct. Published market capitalization is the basis used for "
            "Enterprise Value and recalculated multiples."
        )
        st.markdown(
            "Bachem FY2021 uses its pre-split 1:5 basis and FY2022–FY2025 the published "
            "post-split basis. Siegfried prices and shares use the issuer-published series "
            "adjusted for the 1:10 split. FY2021–FY2024 DPS remains on its native pre-split "
            "basis, so the related dividend yield is not comparable."
        )
        for section_label, specs in VALUATION_SECTIONS:
            st.markdown(f"**{section_label}**")
            st.dataframe(
                valuation_rows(analysis, specs),
                hide_index=True,
                width="stretch",
            )
    _render_metric_inspector(tuple(displayed), key="valuation-metric-inspector")

    with st.expander("Technical valuation status"):
        readiness = repository.valuation_diagnostic["phase_readiness"][
            "phase_4_comparative_valuation"
        ]
        st.caption(f"Comparative gate readiness: {readiness}.")


def _render_monitoring(rows: tuple[MonitoringRow, ...]) -> None:
    st.header("Monitoring")
    st.caption(
        "Latest authorized annual KPIs and the questions they help an analyst revisit. "
        "This is a descriptive watchlist without consensus estimates or forecasts."
    )
    st.dataframe(
        primary_monitoring_rows(rows),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Monitoring details & provenance"):
        st.dataframe(
            monitoring_table_rows(rows),
            hide_index=True,
            width="stretch",
        )


def _render_esg_and_sources(
    metrics: tuple[MetricValue, ...],
    corpus: SustainabilityCorpus,
) -> None:
    st.header("ESG & Sources")
    st.caption(
        "A secondary view of FY2025 climate disclosures, targets and assurance. No ESG score "
        "is produced and no missing value is inferred."
    )

    st.subheader("Descriptive emissions and intensities")
    st.dataframe(primary_esg_metric_rows(metrics), hide_index=True, width="stretch")
    st.caption(
        "Market-based and location-based Scope 2 methods remain separate. Intensities do "
        "not constitute a ranking."
    )

    st.subheader("Published climate targets")
    st.dataframe(_primary_target_rows(corpus), hide_index=True, width="stretch")

    with st.expander("Source & technical provenance"):
        st.markdown(
            "Issuer evidence documents published disclosures; it does not independently "
            "certify their physical truth."
        )
        st.markdown("**Full emissions detail**")
        st.dataframe(esg_metric_rows(metrics), hide_index=True, width="stretch")
        st.markdown("**Full target detail**")
        st.dataframe(_target_rows(corpus), hide_index=True, width="stretch")
        st.markdown("**Metric-level assurance**")
        st.dataframe(_assurance_rows(corpus), hide_index=True, width="stretch")
        st.markdown("**Comparability caveats**")
        st.dataframe(_comparison_rows(corpus), hide_index=True, width="stretch")
        for limitation in corpus.coverage_report.limitations:
            st.caption(f"Corpus limitation: {limitation}")
        st.markdown("**Authorized source documents**")
        st.dataframe(_document_rows(corpus), hide_index=True, width="stretch")

    _render_metric_inspector(metrics, key="esg-metric-inspector")


def _target_rows(corpus: SustainabilityCorpus) -> tuple[dict[str, str | int], ...]:
    documents = {document.document_id: document for document in corpus.documents}
    return tuple(
        {
            "Company": _issuer_label(target.issuer_id),
            "Published target": f"{target.target_value}%",
            "Period": f"{target.base_year} → {target.target_year}",
            "Covered scopes": ", ".join(target.covered_scopes),
            "Status": "reported",
            "Declared validation": target.validation_status,
            "Assurance": target.assurance_status,
            "Method / standard": target.methodology_or_standard,
            "Document": documents[target.document_id].title,
            "PDF page": target.pdf_page,
            "SHA-256": target.document_sha256,
        }
        for target in corpus.targets
    )


def _primary_target_rows(
    corpus: SustainabilityCorpus,
) -> tuple[dict[str, str | int], ...]:
    """Build a concise climate-target view without technical document fingerprints."""

    return tuple(
        {
            "Company": row["Company"],
            "Published target": row["Published target"],
            "Period": row["Period"],
            "Covered scopes": row["Covered scopes"],
            "Declared validation": row["Declared validation"],
            "Assurance": row["Assurance"],
        }
        for row in _target_rows(corpus)
    )


def _assurance_rows(corpus: SustainabilityCorpus) -> tuple[dict[str, str | int], ...]:
    observations = {
        observation.observation_id: observation for observation in corpus.observations
    }
    documents = {document.document_id: document for document in corpus.documents}
    return tuple(
        {
            "Company": _issuer_label(observations[item.observation_id].issuer_id),
            "Metric": observations[item.observation_id].raw_metric_label,
            "Assurance status": item.status,
            "Level": item.level,
            "Scope confirmed": "yes" if item.assurance_scope_confirmed else "no",
            "Document": documents[item.document_id].title,
            "PDF page": item.pdf_page,
            "SHA-256": item.document_sha256,
            "Notes": item.notes,
        }
        for item in corpus.assurance_assessments
    )


def _comparison_rows(corpus: SustainabilityCorpus) -> tuple[dict[str, str], ...]:
    observations = {
        observation.observation_id: observation for observation in corpus.observations
    }
    return tuple(
        {
            "Comparison": item.comparison_id,
            "Status": item.status,
            "Scope 2 method": observations[item.left_observation_id].scope_2_method,
            "Unit": item.unit,
            "Boundary": item.organizational_boundary,
            "Restatement": item.restatement,
            "Assurance": item.assurance,
            "Rationale": " ".join(item.reasons),
        }
        for item in corpus.comparison_assessments
    )


def _document_rows(corpus: SustainabilityCorpus) -> tuple[dict[str, str | int], ...]:
    return tuple(
        {
            "Company": _issuer_label(document.issuer_id),
            "Document": document.title,
            "Period": (
                f"{document.reporting_period_start.isoformat()} → "
                f"{document.reporting_period_end.isoformat()}"
            ),
            "Publication": (
                document.publication_date.isoformat()
                if document.publication_date is not None
                else "unavailable"
            ),
            "Local path": document.local_path,
            "Pages": document.page_count,
            "SHA-256": document.sha256,
        }
        for document in corpus.documents
    )


def _issuer_label(issuer_id: str) -> str:
    labels = {
        "bachem-holding-ag": "Bachem",
        "siegfried-holding-ag": "Siegfried",
    }
    return labels[issuer_id]


def _render_metric_inspector(metrics: tuple[MetricValue, ...], *, key: str) -> None:
    with st.expander("Inspect source, calculation & technical provenance"):
        by_id = {metric.metric_id: metric for metric in metrics}
        selected_id = st.selectbox(
            "Metric to inspect",
            options=tuple(by_id),
            format_func=lambda metric_id: _inspection_label(by_id[metric_id]),
            key=key,
        )
        metric = by_id[selected_id]
        formula = metric.formula
        st.table(
            [
                {
                    "Company": COMPANY_LABELS[metric.company_id],
                    "Fiscal year": f"FY{metric.fiscal_year}",
                    "Metric": _METRIC_LABELS.get(metric.name, metric.name),
                    "Displayed value": format_metric(metric),
                    "Raw source value": (
                        str(metric.value) if metric.value is not None else "—"
                    ),
                    "Unit": metric.unit,
                    "Status": metric.status,
                    "Formula": formula.expression if formula else "—",
                    "Version": formula.version if formula else "—",
                    "Inputs": ", ".join(metric.input_metric_ids) or "—",
                    "Scope 2 method": metric.scope2_method or "not_applicable",
                    "Assurance": metric.assurance or "not_disclosed",
                    "Note": metric.note or "—",
                }
            ]
        )
        st.caption("Input provenance")
        if metric.sources:
            st.dataframe(
                tuple(_source_row(source) for source in metric.sources),
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("No provenance is available for this unavailable metric.")


def _metric_row(metric: MetricValue, label: str) -> dict[str, str]:
    formula = metric.formula
    return {
        "Company": COMPANY_LABELS[metric.company_id],
        "Fiscal year": f"FY{metric.fiscal_year}",
        "Metric": label,
        "Value": format_metric(metric),
        "Raw source value": str(metric.value) if metric.value is not None else "—",
        "Unit": metric.unit,
        "Status": metric.status,
        "Formula / version": (
            f"{formula.expression} · {formula.version}" if formula is not None else "—"
        ),
        "Provenance": _provenance_summary(metric),
    }


def _source_row(source: SourceReference) -> dict[str, str]:
    return {
        "Document": source.document,
        "Fiscal year": f"FY{source.fiscal_year}",
        "Source field": source.field,
        "Source unit": source.source_unit,
        "Method": source.method,
        "Page": str(source.page) if source.page is not None else "unavailable",
        "Source URI": source.source_uri,
        "SHA-256": source.document_sha256,
    }


def _provenance_summary(metric: MetricValue) -> str:
    if not metric.sources:
        return "unavailable"
    return " ; ".join(
        f"{source.document} · {source.field} · {source.method} · SHA-256 "
        f"{source.document_sha256}"
        for source in metric.sources
    )


def _inspection_label(metric: MetricValue) -> str:
    return (
        f"{COMPANY_LABELS[metric.company_id]} · FY{metric.fiscal_year} · "
        f"{_METRIC_LABELS.get(metric.name, metric.name)} · {metric.status}"
    )


def _periods_for(spec: MetricSpec, analysis: FundamentalAnalysis) -> tuple[int, ...]:
    if spec.name == "revenue_cagr_2021_2025":
        return (2025,)
    return analysis.periods


def _render_valuation_limit(repository: EquityRepository) -> None:
    blocked = tuple(repository.valuation_diagnostic["blocked_columns"]["SFZN.SW"])
    if repository.valuation_diagnostic.get("gate") == "pass" and not blocked:
        return
    if blocked != BLOCKED_SIEGFRIED_VALUATION_FIELDS:
        raise ValueError("Unexpected Siegfried valuation gate in embedded diagnostic.")
    fields = ", ".join(f"`{field}`" for field in blocked)
    st.warning(
        "Comparative Siegfried valuation is unavailable: the gate remains blocked for "
        f"{fields}. No market data is inferred, extrapolated, or displayed."
    )


def displayed_fundamental_metric_names() -> tuple[str, ...]:
    """Expose the stable UI scope for focused tests and future review."""

    return tuple(
        dict.fromkeys(spec.name for _, specs in FUNDAMENTAL_SECTIONS for spec in specs)
    )


def iter_displayed_metrics(
    analysis: FundamentalAnalysis,
) -> Iterable[MetricValue]:
    """Yield each fundamentals metric in deterministic UI order."""

    for _, specs in FUNDAMENTAL_SECTIONS:
        for company_id in COMPANY_ORDER:
            for spec in specs:
                for year in _periods_for(spec, analysis):
                    yield analysis.metric(company_id, year, spec.name)
