"""Climate normalization kept separate from financial interpretation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ai_quant.equity.models import (
    AssuranceStatus,
    EquityValidationError,
    MetricValue,
    Scope2Method,
    SourceReference,
    calculated_metric,
    merged_sources,
    require_compatible_inputs,
    unavailable_metric,
)
from ai_quant.equity.repository import EquityRepository, load_equity_repository
from ai_quant.sustainability import SustainabilityCorpus, load_corpus

CLIMATE_FIXTURE_CUTOFF = date(2026, 12, 31)
ISSUER_TO_COMPANY = {
    "bachem-holding-ag": ("bachem", "BANB.SW"),
    "siegfried-holding-ag": ("siegfried", "SFZN.SW"),
}


def build_climate_metrics(
    repository: EquityRepository | None = None,
    corpus: SustainabilityCorpus | None = None,
) -> tuple[MetricValue, ...]:
    """Build FY2025 climate metrics from the committed offline corpus only."""

    repository = repository or load_equity_repository()
    corpus = corpus or load_corpus(CLIMATE_FIXTURE_CUTOFF)
    documents = {document.document_id: document for document in corpus.documents}
    by_company: dict[str, dict[str, MetricValue]] = {
        company_id: {} for company_id, _ in ISSUER_TO_COMPANY.values()
    }
    reported: list[MetricValue] = []

    for observation in corpus.observations:
        coordinates = ISSUER_TO_COMPANY.get(observation.issuer_id)
        if coordinates is None or observation.period_end.year != 2025:
            continue
        if observation.indicator_type not in {
            "scope_1_ghg_emissions",
            "scope_2_ghg_emissions",
        }:
            continue
        company_id, _ = coordinates
        document = documents[observation.document_id]
        if observation.indicator_type == "scope_1_ghg_emissions":
            name = "scope_1_emissions"
        else:
            name = f"scope_2_{observation.scope_2_method}_emissions"
        metric = MetricValue(
            metric_id=f"{company_id}-2025-{name.replace('_', '-')}",
            company_id=company_id,
            fiscal_year=2025,
            name=name,
            value=observation.value,
            unit=observation.unit or "tCO2e",
            status="reported",
            sources=(
                SourceReference(
                    source_id=f"{observation.observation_id}-source",
                    document=observation.document_title,
                    fiscal_year=2025,
                    field=observation.raw_metric_label,
                    source_unit=observation.unit or "not_disclosed",
                    method="reported",
                    source_uri=document.local_path,
                    document_sha256=observation.document_sha256,
                    page=observation.pdf_page,
                ),
            ),
            note=(
                f"{observation.methodology_or_standard} "
                f"Boundary: {observation.organizational_boundary} "
                f"Restatement: {observation.restatement}"
            ),
            scope2_method=(
                observation.scope_2_method
                if observation.indicator_type == "scope_2_ghg_emissions"
                else "not_applicable"
            ),
            assurance=_equity_assurance(observation.assurance_status),
        )
        by_company[company_id][name] = metric
        reported.append(metric)

    calculated: list[MetricValue] = []
    for company_id, ticker in ISSUER_TO_COMPANY.values():
        scope1 = normalize_emissions(by_company[company_id]["scope_1_emissions"])
        revenue = repository.metric(ticker, 2025, "revenue")
        for method in ("market_based", "location_based"):
            scope2 = normalize_emissions(
                by_company[company_id][f"scope_2_{method}_emissions"]
            )
            calculated.append(
                climate_intensity(
                    scope1,
                    scope2,
                    revenue,
                    scope2_method=method,
                    assurance=_combined_assurance(scope1, scope2),
                    name=f"scope_1_2_{method}_intensity",
                )
            )

    return tuple(sorted((*reported, *calculated), key=lambda item: item.metric_id))


def normalize_emissions(metric: MetricValue, *, target_unit: str = "tCO2e") -> MetricValue:
    """Normalize emissions between tonnes and kilotonnes without mutating source values."""

    if target_unit not in {"tCO2e", "ktCO2e"}:
        raise EquityValidationError("target emissions unit must be tCO2e or ktCO2e.")
    output_id = f"{metric.company_id}-{metric.fiscal_year}-{metric.name}-{target_unit}"
    if not metric.is_available:
        return unavailable_metric(
            metric_id=output_id,
            company_id=metric.company_id,
            fiscal_year=metric.fiscal_year,
            name=metric.name,
            unit=target_unit,
            note="Emissions cannot be normalized because the source metric is unavailable.",
            sources=metric.sources,
            input_metric_ids=(metric.metric_id,),
        )
    conversions = {
        ("tCO2e", "tCO2e"): Decimal("1"),
        ("ktCO2e", "ktCO2e"): Decimal("1"),
        ("ktCO2e", "tCO2e"): Decimal("1000"),
        ("tCO2e", "ktCO2e"): Decimal("0.001"),
    }
    try:
        factor = conversions[(metric.unit, target_unit)]
    except KeyError as error:
        raise EquityValidationError("source emissions unit must be tCO2e or ktCO2e.") from error
    return calculated_metric(
        metric_id=output_id,
        company_id=metric.company_id,
        fiscal_year=metric.fiscal_year,
        name=metric.name,
        value=metric.value * factor,
        unit=target_unit,
        formula_id="emissions-unit-normalization",
        expression=f"source_emissions * {factor}",
        inputs=(metric,),
        scope2_method=metric.scope2_method,
        assurance=metric.assurance,
    )


def climate_intensity(
    scope1: MetricValue,
    scope2: MetricValue,
    revenue: MetricValue,
    *,
    scope2_method: Scope2Method,
    assurance: AssuranceStatus,
    name: str = "scope1_2_intensity",
) -> MetricValue:
    """Calculate Scope 1+2 intensity with an explicit Scope 2 method and assurance."""

    require_compatible_inputs(scope1, scope2, revenue)
    if len({scope1.fiscal_year, scope2.fiscal_year, revenue.fiscal_year}) != 1:
        raise EquityValidationError("climate intensity inputs must use the same fiscal year.")
    if scope2_method not in {"location_based", "market_based"}:
        raise EquityValidationError("Climate intensity requires an explicit Scope 2 method.")
    if scope2.scope2_method not in {None, scope2_method}:
        raise EquityValidationError("Scope 2 input method does not match intensity method.")
    output_id = f"{scope1.company_id}-{scope1.fiscal_year}-{name.replace('_', '-')}"
    if not scope1.is_available or not scope2.is_available or not revenue.is_available:
        return unavailable_metric(
            metric_id=output_id,
            company_id=scope1.company_id,
            fiscal_year=scope1.fiscal_year,
            name=name,
            unit="tCO2e_per_CHF_million",
            note="Climate intensity requires Scope 1, Scope 2, and revenue.",
            sources=merged_sources((scope1, scope2, revenue)),
            input_metric_ids=(scope1.metric_id, scope2.metric_id, revenue.metric_id),
        )
    if scope1.unit != "tCO2e" or scope2.unit != "tCO2e":
        raise EquityValidationError("emissions must be normalized to tCO2e first.")
    if revenue.unit != "CHF_millions":
        raise EquityValidationError("climate intensity revenue must use CHF_millions.")
    if revenue.value <= 0:
        return unavailable_metric(
            metric_id=output_id,
            company_id=scope1.company_id,
            fiscal_year=scope1.fiscal_year,
            name=name,
            unit="tCO2e_per_CHF_million",
            note="Climate intensity requires positive revenue.",
            status="not_comparable",
            sources=merged_sources((scope1, scope2, revenue)),
            input_metric_ids=(scope1.metric_id, scope2.metric_id, revenue.metric_id),
        )
    return calculated_metric(
        metric_id=output_id,
        company_id=scope1.company_id,
        fiscal_year=scope1.fiscal_year,
        name=name,
        value=(scope1.value + scope2.value) / revenue.value,
        unit="tCO2e_per_CHF_million",
        formula_id="scope1-plus-scope2-intensity",
        expression="(scope1_tCO2e + scope2_tCO2e) / revenue_CHF_millions",
        inputs=(scope1, scope2, revenue),
        note=(
            "Financial and climate values are combined only for descriptive intensity; "
            f"Scope 2 method: {scope2_method}."
        ),
        scope2_method=scope2_method,
        assurance=assurance,
    )


def _equity_assurance(status: str) -> AssuranceStatus:
    if status == "verified_in_assurance_statement":
        return "limited"
    if status == "explicitly_not_assured":
        return "none"
    return "not_disclosed"


def _combined_assurance(scope1: MetricValue, scope2: MetricValue) -> AssuranceStatus:
    if scope1.assurance == scope2.assurance:
        return scope1.assurance or "not_disclosed"
    return "not_disclosed"
