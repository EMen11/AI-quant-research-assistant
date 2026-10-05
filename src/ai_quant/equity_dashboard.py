"""Offline Streamlit presentation for deterministic Equity fundamentals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.formatting import format_metric
from ai_quant.equity.models import FundamentalAnalysis, MetricValue, SourceReference
from ai_quant.equity.repository import EquityRepository, load_equity_repository

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
    """Stable UI label for one canonical Phase 3 metric."""

    name: str
    label: str


SNAPSHOT_METRICS = (
    MetricSpec("revenue", "Chiffre d’affaires"),
    MetricSpec("revenue_yoy_growth", "Croissance annuelle du chiffre d’affaires"),
    MetricSpec("revenue_cagr_2021_2025", "CAGR du chiffre d’affaires FY2021–FY2025"),
    MetricSpec("ebitda_margin", "Marge EBITDA"),
    MetricSpec("ebit_margin", "Marge EBIT"),
    MetricSpec("net_margin", "Marge nette"),
    MetricSpec("operating_cash_flow", "Operating cash flow"),
    MetricSpec("operating_cash_flow_to_revenue", "Operating cash flow / CA"),
    MetricSpec("free_cash_flow_calculated", "FCF calculé dans la source"),
    MetricSpec("calculated_fcf_cash_conversion", "Cash conversion du FCF calculé"),
    MetricSpec("net_debt", "Dette nette"),
    MetricSpec("net_debt_to_ebitda", "Dette nette / EBITDA"),
    MetricSpec("return_on_period_end_equity", "ROE sur capitaux propres de clôture"),
    MetricSpec("equity_ratio_recomputed", "Equity ratio recalculé"),
)

FUNDAMENTAL_SECTIONS = (
    (
        "Chiffre d’affaires et croissance",
        (
            MetricSpec("revenue", "Chiffre d’affaires"),
            MetricSpec("revenue_yoy_growth", "Croissance annuelle"),
            MetricSpec("revenue_cagr_2021_2025", "CAGR FY2021–FY2025"),
        ),
    ),
    (
        "Marges",
        (
            MetricSpec("ebitda_margin", "Marge EBITDA"),
            MetricSpec("ebit_margin", "Marge EBIT"),
            MetricSpec("net_margin", "Marge nette"),
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
        "Capex / chiffre d’affaires",
        (
            MetricSpec("capex_reported_to_revenue", "Capex reported / CA"),
            MetricSpec("capex_calculated_to_revenue", "Capex calculated / CA"),
        ),
    ),
    (
        "Free cash flow et cash conversion",
        (
            MetricSpec("free_cash_flow_reported", "FCF reported"),
            MetricSpec("free_cash_flow_calculated", "FCF calculated dans la source"),
            MetricSpec("free_cash_flow_recomputed", "FCF recalculé par AI Quant"),
            MetricSpec("reported_fcf_cash_conversion", "Cash conversion du FCF reported"),
            MetricSpec(
                "calculated_fcf_cash_conversion",
                "Cash conversion du FCF calculated",
            ),
        ),
    ),
    (
        "Dette nette et levier",
        (
            MetricSpec("net_debt", "Dette nette"),
            MetricSpec("net_debt_to_ebitda", "Dette nette / EBITDA"),
        ),
    ),
    (
        "ROE",
        (MetricSpec("return_on_period_end_equity", "ROE sur capitaux propres de clôture"),),
    ),
    (
        "Equity ratio",
        (
            MetricSpec("equity_ratio", "Equity ratio reported"),
            MetricSpec("equity_ratio_recomputed", "Equity ratio recalculé"),
        ),
    ),
)

_METRIC_LABELS = {
    spec.name: spec.label
    for _, specs in FUNDAMENTAL_SECTIONS
    for spec in specs
} | {spec.name: spec.label for spec in SNAPSHOT_METRICS}


def render_equity_dashboard() -> None:
    """Render the two-tab Phase 4 scope from embedded offline fixtures only."""

    repository = load_equity_repository()
    analysis = build_fundamental_analysis(repository)

    st.title("Equity Research")
    st.caption(
        "Bachem (BANB.SW) / Siegfried (SFZN.SW) · FY2021–FY2025 · "
        "fixtures locales verrouillées"
    )
    st.info(
        "Statuts : `reported` = publié dans la source ; `calculated` = calcul déterministe ; "
        "`unavailable` = entrée absente ; `not_comparable` = base incompatible. "
        "Une valeur manquante reste vide et n’est jamais remplacée par zéro."
    )
    _render_valuation_limit(repository)

    snapshot_tab, fundamentals_tab = st.tabs(("Snapshot", "Fondamentaux"))
    with snapshot_tab:
        _render_snapshot(analysis)
    with fundamentals_tab:
        _render_fundamentals(analysis)


def snapshot_rows(analysis: FundamentalAnalysis) -> tuple[dict[str, str], ...]:
    """Build the FY2025 side-by-side comparison without valuation data."""

    rows: list[dict[str, str]] = []
    for spec in SNAPSHOT_METRICS:
        bachem = analysis.metric("bachem", 2025, spec.name)
        siegfried = analysis.metric("siegfried", 2025, spec.name)
        rows.append(
            {
                "Métrique": spec.label,
                "Bachem FY2025": format_metric(bachem),
                "Statut Bachem": bachem.status,
                "Siegfried FY2025": format_metric(siegfried),
                "Statut Siegfried": siegfried.status,
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


def _render_snapshot(analysis: FundamentalAnalysis) -> None:
    st.header("Snapshot FY2025")
    st.caption(
        "Comparaison descriptive des valeurs et ratios fondamentaux. Aucun classement, "
        "signal d’investissement ou multiple de valorisation n’est produit."
    )
    st.dataframe(snapshot_rows(analysis), hide_index=True, width="stretch")
    metrics = tuple(
        analysis.metric(company_id, 2025, spec.name)
        for company_id in COMPANY_ORDER
        for spec in SNAPSHOT_METRICS
    )
    _render_metric_inspector(metrics, key="snapshot-metric-inspector")


def _render_fundamentals(analysis: FundamentalAnalysis) -> None:
    st.header("Fondamentaux FY2021–FY2025")
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


def _render_metric_inspector(metrics: tuple[MetricValue, ...], *, key: str) -> None:
    st.subheader("Inspection d’une métrique")
    by_id = {metric.metric_id: metric for metric in metrics}
    selected_id = st.selectbox(
        "Métrique à inspecter",
        options=tuple(by_id),
        format_func=lambda metric_id: _inspection_label(by_id[metric_id]),
        key=key,
    )
    metric = by_id[selected_id]
    formula = metric.formula
    st.table(
        [
            {
                "Société": COMPANY_LABELS[metric.company_id],
                "Exercice": f"FY{metric.fiscal_year}",
                "Métrique": _METRIC_LABELS.get(metric.name, metric.name),
                "Valeur affichée": format_metric(metric),
                "Valeur source / non formatée": (
                    str(metric.value) if metric.value is not None else "—"
                ),
                "Unité": metric.unit,
                "Statut": metric.status,
                "Formule": formula.expression if formula else "—",
                "Version": formula.version if formula else "—",
                "Entrées": ", ".join(metric.input_metric_ids) or "—",
                "Note": metric.note or "—",
            }
        ]
    )
    st.caption("Provenance des entrées")
    if metric.sources:
        st.dataframe(
            tuple(_source_row(source) for source in metric.sources),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Aucune provenance disponible pour cette métrique indisponible.")


def _metric_row(metric: MetricValue, label: str) -> dict[str, str]:
    formula = metric.formula
    return {
        "Société": COMPANY_LABELS[metric.company_id],
        "Exercice": f"FY{metric.fiscal_year}",
        "Métrique": label,
        "Valeur": format_metric(metric),
        "Valeur source / non formatée": str(metric.value) if metric.value is not None else "—",
        "Unité": metric.unit,
        "Statut": metric.status,
        "Formule / version": (
            f"{formula.expression} · {formula.version}" if formula is not None else "—"
        ),
        "Provenance": _provenance_summary(metric),
    }


def _source_row(source: SourceReference) -> dict[str, str | int]:
    return {
        "Document": source.document,
        "Exercice": f"FY{source.fiscal_year}",
        "Champ source": source.field,
        "Unité source": source.source_unit,
        "Méthode": source.method,
        "Page": source.page if source.page is not None else "non disponible",
        "URI source": source.source_uri,
        "SHA-256": source.document_sha256,
    }


def _provenance_summary(metric: MetricValue) -> str:
    if not metric.sources:
        return "indisponible"
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
    if blocked != BLOCKED_SIEGFRIED_VALUATION_FIELDS:
        raise ValueError("Unexpected Siegfried valuation gate in embedded diagnostic.")
    fields = ", ".join(f"`{field}`" for field in blocked)
    st.warning(
        "Valorisation comparative Siegfried indisponible : le gate reste bloqué pour "
        f"{fields}. Aucune donnée de marché n’est inférée, extrapolée ou affichée."
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
