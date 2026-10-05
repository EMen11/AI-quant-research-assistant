"""Offline Streamlit presentation for deterministic Equity research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.climate import CLIMATE_FIXTURE_CUTOFF, build_climate_metrics
from ai_quant.equity.formatting import format_metric
from ai_quant.equity.models import FundamentalAnalysis, MetricValue, SourceReference
from ai_quant.equity.monitoring import build_monitoring_rows, monitoring_table_rows
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
        "Historical market data",
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
        "Enterprise Value and historical multiples",
        (
            MetricSpec("enterprise_value", "Enterprise Value"),
            MetricSpec("enterprise_value_to_revenue", "EV / Revenue"),
            MetricSpec("enterprise_value_to_ebitda", "EV / EBITDA"),
            MetricSpec("enterprise_value_to_ebit", "EV / EBIT"),
            MetricSpec("price_to_earnings_published", "Published P/E"),
            MetricSpec("price_to_earnings_calculated", "Recalculated P/E"),
            MetricSpec("price_to_book", "Recalculated P/B"),
        ),
    ),
    (
        "Historical yields",
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
    st.info(
        "Statuses: `reported` = published by the source; `calculated` = deterministic "
        "calculation; `unavailable` = missing input; `not_comparable` = incompatible basis. "
        "A missing value remains empty and is never replaced with zero."
    )
    _render_valuation_limit(repository)

    snapshot_tab, fundamentals_tab, valuation_tab, esg_tab, research_note_tab = st.tabs(
        (
            "Snapshot",
            "Fundamentals",
            "Valuation",
            "ESG & sources",
            "Research note",
        )
    )
    with snapshot_tab:
        _render_snapshot(analysis)
    with fundamentals_tab:
        _render_fundamentals(analysis)
    with valuation_tab:
        _render_valuation(valuation, repository)
    with esg_tab:
        _render_esg_and_sources(climate_metrics, climate_corpus)
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
        _render_research_note(result, monitoring_rows)


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


def _render_research_note(
    result: EquityResearchResult,
    monitoring_rows: tuple,
) -> None:
    st.header("Research Note — Bachem / Siegfried")
    st.caption(
        "Structured note with offline AI assistance. Python supplies the figures and validates "
        "the references; AI does not calculate or make any final decision."
    )
    st.markdown(f"**Executive summary.** {result.analyst_note.executive_summary}")

    if result.review_status == "blocked":
        st.error(
            "Automated validation: BLOCKED. The note is neither rendered as reliable nor "
            "presented as validated."
        )
        st.caption(f"Human-review status: `{result.review_status}`.")
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
    else:
        st.success(
            "Automated validation: PASSED — authorized references, values, units, periods, "
            "and citations."
        )
        st.warning(
            "Human-review status: `pending_human_review`. No human approval has been "
            "fabricated."
        )
        rendered_claims = iter(result.rendered_draft.claims)
        for section in result.analyst_note.sections.ordered():
            st.subheader(section.title)
            for statement in section.statements:
                claim = next(rendered_claims)
                st.caption(f"Type: `{statement.kind}`")
                st.markdown(claim.text)
                if statement.uncertainty:
                    st.caption(f"Caveat: {statement.uncertainty}")

    st.subheader("Limitations")
    for limitation in result.analyst_note.limitations:
        st.markdown(f"- `{limitation.limitation_id}` — {limitation.text}")

    st.subheader("Authorized sources")
    st.dataframe(
        research_source_rows(result.context.authorized_sources),
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
            st.caption(f"Local source: `{source.source_uri}`")

    st.subheader("FY2025 monitoring")
    st.caption(
        "Descriptive annual monitoring without consensus, forecasts, or interim data. "
        "Missing data remains visible with `to_update` freshness."
    )
    st.dataframe(
        monitoring_table_rows(monitoring_rows),
        hide_index=True,
        width="stretch",
    )


def _render_snapshot(analysis: FundamentalAnalysis) -> None:
    st.header("Snapshot FY2025")
    st.caption(
        "Descriptive comparison of fundamental values and ratios. No ranking, investment "
        "signal, or valuation multiple is produced here."
    )
    st.dataframe(snapshot_rows(analysis), hide_index=True, width="stretch")
    metrics = tuple(
        analysis.metric(company_id, 2025, spec.name)
        for company_id in COMPANY_ORDER
        for spec in SNAPSHOT_METRICS
    )
    _render_metric_inspector(metrics, key="snapshot-metric-inspector")


def _render_fundamentals(analysis: FundamentalAnalysis) -> None:
    st.header("Fundamentals FY2021–FY2025")
    displayed: list[MetricValue] = []
    for section_label, specs in FUNDAMENTAL_SECTIONS:
        st.subheader(section_label)
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
    st.caption(
        "Every value corresponds to the stated fiscal-year close; no figure is presented as "
        "a current share price or valuation."
    )
    st.info(
        "Published market capitalization and indicative `price × shares` capitalization "
        "remain distinct metrics. Published market capitalization is the only basis used "
        "for Enterprise Value and recalculated multiples."
    )
    st.warning(
        "Splits: Bachem FY2021 is shown on its pre-split 1:5 basis and FY2022–FY2025 on "
        "the published post-split basis. For SFZN, FY2021–FY2025 prices and shares use the "
        "issuer-published comparative series adjusted for the 1:10 split; FY2021–FY2024 DPS "
        "remains on its native pre-split basis, so the corresponding dividend yield is "
        "not_comparable."
    )
    st.caption(
        "Source limitation: Bachem published P/E is `unavailable` for FY2021–FY2025. "
        "The recalculated P/E is displayed separately and does not replace that published field."
    )

    displayed: list[MetricValue] = []
    for section_label, specs in VALUATION_SECTIONS:
        st.subheader(section_label)
        st.dataframe(
            valuation_rows(analysis, specs),
            hide_index=True,
            width="stretch",
        )
        displayed.extend(
            analysis.metric(company_id, year, spec.name)
            for company_id in COMPANY_ORDER
            for spec in specs
            for year in analysis.periods
        )
    _render_metric_inspector(tuple(displayed), key="valuation-metric-inspector")

    readiness = repository.valuation_diagnostic["phase_readiness"][
        "phase_4_comparative_valuation"
    ]
    st.caption(f"Comparative gate readiness: `{readiness}`.")


def _render_esg_and_sources(
    metrics: tuple[MetricValue, ...],
    corpus: SustainabilityCorpus,
) -> None:
    st.header("ESG & sources")
    st.caption(
        "FY2025 climate data already authorized in the local corpus. No ESG score is "
        "produced and no missing value is inferred."
    )
    st.warning(
        "Evidence documents what the issuer publishes; it does not certify the physical "
        "truth of the data. Market-based and location-based Scope 2 methods remain strictly "
        "separate."
    )

    st.subheader("Descriptive emissions and intensities")
    st.dataframe(esg_metric_rows(metrics), hide_index=True, width="stretch")
    st.caption(
        "Intensities combine Scope 1 and Scope 2 under the same method with FY2025 revenue "
        "for the same company. They do not constitute a ranking."
    )
    _render_metric_inspector(metrics, key="esg-metric-inspector")

    st.subheader("Published climate targets")
    st.dataframe(_target_rows(corpus), hide_index=True, width="stretch")

    st.subheader("Metric-level assurance")
    st.dataframe(_assurance_rows(corpus), hide_index=True, width="stretch")

    st.subheader("Comparability caveats")
    st.dataframe(_comparison_rows(corpus), hide_index=True, width="stretch")
    for limitation in corpus.coverage_report.limitations:
        st.caption(f"Corpus limitation: {limitation}")

    st.subheader("Authorized source documents")
    st.dataframe(_document_rows(corpus), hide_index=True, width="stretch")


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
    st.subheader("Metric inspection")
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
