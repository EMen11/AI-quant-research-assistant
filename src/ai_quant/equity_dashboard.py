"""Offline Streamlit presentation for deterministic Equity research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.climate import CLIMATE_FIXTURE_CUTOFF, build_climate_metrics
from ai_quant.equity.formatting import format_metric
from ai_quant.equity.models import FundamentalAnalysis, MetricValue, SourceReference
from ai_quant.equity.repository import EquityRepository, load_equity_repository
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

VALUATION_SECTIONS = (
    (
        "Données de marché historiques",
        (
            MetricSpec("year_end_share_price", "Cours de clôture historique"),
            MetricSpec("registered_shares", "Actions enregistrées"),
            MetricSpec(
                "market_capitalization_published",
                "Capitalisation boursière publiée",
            ),
            MetricSpec(
                "market_capitalization_calculated",
                "Capitalisation indicative cours × actions",
            ),
        ),
    ),
    (
        "Enterprise Value et multiples historiques",
        (
            MetricSpec("enterprise_value", "Enterprise Value"),
            MetricSpec("enterprise_value_to_revenue", "EV / Revenue"),
            MetricSpec("enterprise_value_to_ebitda", "EV / EBITDA"),
            MetricSpec("enterprise_value_to_ebit", "EV / EBIT"),
            MetricSpec("price_to_earnings_published", "P/E publié"),
            MetricSpec("price_to_earnings_calculated", "P/E recalculé"),
            MetricSpec("price_to_book", "P/B recalculé"),
        ),
    ),
    (
        "Rendements historiques",
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
        "Intensité Scope 1+2 · market-based",
    ),
    MetricSpec(
        "scope_1_2_location_based_intensity",
        "Intensité Scope 1+2 · location-based",
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
    """Render the four-tab Phase 4 scope from embedded offline fixtures only."""

    repository = load_equity_repository()
    analysis = build_fundamental_analysis(repository)
    valuation = build_valuation_analysis(repository, analysis)
    climate_corpus = load_corpus(CLIMATE_FIXTURE_CUTOFF)
    climate_metrics = build_climate_metrics(repository, climate_corpus)

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

    snapshot_tab, fundamentals_tab, valuation_tab, esg_tab = st.tabs(
        ("Snapshot", "Fondamentaux", "Valorisation", "ESG & sources")
    )
    with snapshot_tab:
        _render_snapshot(analysis)
    with fundamentals_tab:
        _render_fundamentals(analysis)
    with valuation_tab:
        _render_valuation(valuation, repository)
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
            row["Méthode Scope 2"] = metric.scope2_method or "not_applicable"
            row["Assurance"] = metric.assurance or "not_disclosed"
            rows.append(row)
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


def _render_valuation(
    analysis: ValuationAnalysis,
    repository: EquityRepository,
) -> None:
    st.header("Valorisation historique FY2021–FY2025")
    st.caption(
        "Toutes les valeurs correspondent à la clôture de l’exercice indiqué ; aucune "
        "donnée n’est présentée comme un cours ou une valorisation actuelle."
    )
    st.info(
        "Capitalisation publiée et capitalisation indicative `cours × actions` restent "
        "deux métriques distinctes. La capitalisation publiée est la seule base utilisée "
        "pour l’Enterprise Value et les multiples recalculés."
    )
    st.warning(
        "Splits : Bachem FY2021 est présenté sur sa base pré-split 1:5 et FY2022–FY2025 "
        "sur la base post-split publiée. Pour SFZN, cours et actions FY2021–FY2025 sont "
        "la série comparative publiée ajustée du split 1:10 ; le DPS FY2021–FY2024 "
        "reste natif pré-split, donc le dividend yield correspondant est not_comparable."
    )
    st.caption(
        "Limitation source : le P/E publié Bachem est `unavailable` pour FY2021–FY2025. "
        "Le P/E recalculé est affiché séparément et ne remplace pas ce champ publié."
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
    st.caption(f"Readiness du gate comparatif : `{readiness}`.")


def _render_esg_and_sources(
    metrics: tuple[MetricValue, ...],
    corpus: SustainabilityCorpus,
) -> None:
    st.header("ESG & sources")
    st.caption(
        "Données climat FY2025 déjà autorisées dans le corpus local. Aucun score ESG "
        "n’est produit et aucune absence n’est imputée."
    )
    st.warning(
        "Une preuve documente ce que l’émetteur publie ; elle ne certifie pas la réalité "
        "physique de la donnée. Les méthodes Scope 2 market-based et location-based "
        "restent strictement séparées."
    )

    st.subheader("Émissions et intensités descriptives")
    st.dataframe(esg_metric_rows(metrics), hide_index=True, width="stretch")
    st.caption(
        "Les intensités combinent Scope 1 et Scope 2 d’une même méthode avec le chiffre "
        "d’affaires FY2025 de la même société. Elles ne constituent pas un classement."
    )
    _render_metric_inspector(metrics, key="esg-metric-inspector")

    st.subheader("Objectifs climatiques publiés")
    st.dataframe(_target_rows(corpus), hide_index=True, width="stretch")

    st.subheader("Assurance au niveau de la métrique")
    st.dataframe(_assurance_rows(corpus), hide_index=True, width="stretch")

    st.subheader("Caveats de comparabilité")
    st.dataframe(_comparison_rows(corpus), hide_index=True, width="stretch")
    for limitation in corpus.coverage_report.limitations:
        st.caption(f"Limitation du corpus : {limitation}")

    st.subheader("Documents sources autorisés")
    st.dataframe(_document_rows(corpus), hide_index=True, width="stretch")


def _target_rows(corpus: SustainabilityCorpus) -> tuple[dict[str, str | int], ...]:
    documents = {document.document_id: document for document in corpus.documents}
    return tuple(
        {
            "Société": _issuer_label(target.issuer_id),
            "Objectif publié": f"{target.target_value}%",
            "Période": f"{target.base_year} → {target.target_year}",
            "Scopes couverts": ", ".join(target.covered_scopes),
            "Statut": "reported",
            "Validation déclarée": target.validation_status,
            "Assurance": target.assurance_status,
            "Méthode / standard": target.methodology_or_standard,
            "Document": documents[target.document_id].title,
            "Page PDF": target.pdf_page,
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
            "Société": _issuer_label(observations[item.observation_id].issuer_id),
            "Métrique": observations[item.observation_id].raw_metric_label,
            "Statut d’assurance": item.status,
            "Niveau": item.level,
            "Portée confirmée": "oui" if item.assurance_scope_confirmed else "non",
            "Document": documents[item.document_id].title,
            "Page PDF": item.pdf_page,
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
            "Comparaison": item.comparison_id,
            "Statut": item.status,
            "Méthode Scope 2": observations[item.left_observation_id].scope_2_method,
            "Unité": item.unit,
            "Périmètre": item.organizational_boundary,
            "Restatement": item.restatement,
            "Assurance": item.assurance,
            "Justification": " ".join(item.reasons),
        }
        for item in corpus.comparison_assessments
    )


def _document_rows(corpus: SustainabilityCorpus) -> tuple[dict[str, str | int], ...]:
    return tuple(
        {
            "Société": _issuer_label(document.issuer_id),
            "Document": document.title,
            "Période": (
                f"{document.reporting_period_start.isoformat()} → "
                f"{document.reporting_period_end.isoformat()}"
            ),
            "Publication": (
                document.publication_date.isoformat()
                if document.publication_date is not None
                else "indisponible"
            ),
            "Chemin local": document.local_path,
            "Page(s)": document.page_count,
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
                "Méthode Scope 2": metric.scope2_method or "not_applicable",
                "Assurance": metric.assurance or "not_disclosed",
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


def _source_row(source: SourceReference) -> dict[str, str]:
    return {
        "Document": source.document,
        "Exercice": f"FY{source.fiscal_year}",
        "Champ source": source.field,
        "Unité source": source.source_unit,
        "Méthode": source.method,
        "Page": str(source.page) if source.page is not None else "non disponible",
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
    if repository.valuation_diagnostic.get("gate") == "pass" and not blocked:
        return
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
