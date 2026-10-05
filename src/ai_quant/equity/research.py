"""Offline Equity Research Note workflow built on the existing trust controls."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.analyst_note import (
    REQUIRED_LIMITATION_IDS,
    AnalystNoteSections,
    AnalystNoteV1,
    EvidenceUse,
    MetricUse,
    NoteLimitation,
    NoteSection,
    NoteStatement,
    prohibited_output_reason,
)
from ai_quant.equity.climate import CLIMATE_FIXTURE_CUTOFF, build_climate_metrics
from ai_quant.equity.models import FundamentalAnalysis, MetricValue
from ai_quant.equity.records import (
    create_equity_evidence_records,
    create_equity_metric_records,
    metric_record_name,
)
from ai_quant.equity.repository import EquityRepository, load_equity_repository
from ai_quant.equity.valuation import ValuationAnalysis, build_valuation_analysis
from ai_quant.sustainability import SustainabilityCorpus, load_corpus
from ai_quant.trust.models import (
    AutomatedAssessment,
    ClaimProposal,
    DraftProposal,
    EvidenceRecord,
    GeneratedDraft,
    GenerationMetadata,
    HumanReview,
    Identifier,
    MetricRecord,
    NonEmptyText,
    RenderedDraft,
    StrictModel,
    ValidationIssue,
    ValidationReport,
)
from ai_quant.trust.records import materialize_generated_draft
from ai_quant.trust.validation import (
    assess_draft,
    build_validation_report,
    render_validated_draft,
    validate_draft,
)

RESEARCH_RUN_ID = "run-equity-research-v1"
RESEARCH_COMPARISON_DATE = date(2026, 3, 12)
OutputRule = Literal[
    "authorized-metrics-only",
    "authorized-evidence-only",
    "no-free-numbers",
    "no-finance-climate-causality",
    "no-investment-recommendation",
    "no-target-price",
    "no-price-prediction",
    "human-decision-required",
]
RESEARCH_OUTPUT_RULES: tuple[OutputRule, ...] = (
    "authorized-metrics-only",
    "authorized-evidence-only",
    "no-free-numbers",
    "no-finance-climate-causality",
    "no-investment-recommendation",
    "no-target-price",
    "no-price-prediction",
    "human-decision-required",
)


class AuthorizedSource(StrictModel):
    """Openable source metadata attached to one authorized Evidence record."""

    evidence_id: Identifier
    title: NonEmptyText
    source_uri: NonEmptyText
    page: int = Field(ge=1)


class ResearchNoteContext(StrictModel):
    """Closed generator context exposing only server-approved research inputs."""

    schema_version: Literal["research-note-context.v1"] = "research-note-context.v1"
    run_id: Identifier
    metric_records: Annotated[tuple[MetricRecord, ...], Field(min_length=1)]
    evidence_records: Annotated[tuple[EvidenceRecord, ...], Field(min_length=1)]
    authorized_sources: Annotated[tuple[AuthorizedSource, ...], Field(min_length=1)]
    allowed_metric_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    allowed_evidence_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    required_limitation_ids: tuple[Identifier, ...]
    output_rules: tuple[OutputRule, ...]

    @model_validator(mode="after")
    def context_is_closed_and_run_bound(self) -> ResearchNoteContext:
        if any(record.run_id != self.run_id for record in self.metric_records):
            raise ValueError("Every context metric must belong to the active run.")
        if any(record.run_id != self.run_id for record in self.evidence_records):
            raise ValueError("Every context Evidence record must belong to the active run.")
        metric_ids = tuple(record.metric_id for record in self.metric_records)
        evidence_ids = tuple(record.evidence_id for record in self.evidence_records)
        if self.allowed_metric_ids != metric_ids:
            raise ValueError("Metric allowlist must exactly match context records.")
        if self.allowed_evidence_ids != evidence_ids:
            raise ValueError("Evidence allowlist must exactly match context records.")
        if tuple(source.evidence_id for source in self.authorized_sources) != evidence_ids:
            raise ValueError("Every Evidence record requires exactly one authorized source.")
        if self.required_limitation_ids != REQUIRED_LIMITATION_IDS:
            raise ValueError("Context must expose the complete required limitation policy.")
        if self.output_rules != RESEARCH_OUTPUT_RULES:
            raise ValueError("Context output rules must match the versioned policy.")
        return self

    def metric(self, company_id: str, metric_name: str, period: str = "FY2025") -> MetricRecord:
        """Resolve exactly one allowlisted metric by business coordinates."""

        expected_name = metric_record_name(company_id, metric_name)
        matches = tuple(
            record
            for record in self.metric_records
            if record.metric_name == expected_name
            and record.horizon_or_frequency == period
        )
        if len(matches) != 1:
            raise KeyError(f"Context metric not found: {company_id} {period} {metric_name}")
        return matches[0]


@dataclass(frozen=True, slots=True)
class EquityResearchResult:
    """Complete offline result with automated routing and human review separated."""

    run_id: str
    scenario: Literal["admissible", "blocked"]
    context: ResearchNoteContext
    analyst_note: AnalystNoteV1
    draft: GeneratedDraft
    validation_report: ValidationReport
    assessment: AutomatedAssessment
    rendered_draft: RenderedDraft
    review_status: Literal["pending_human_review", "blocked"]
    human_review: HumanReview | None


_FUNDAMENTAL_NAMES = (
    "revenue",
    "revenue_yoy_growth",
    "revenue_cagr_2021_2025",
    "ebitda_margin",
    "ebit_margin",
    "operating_cash_flow",
    "calculated_fcf_cash_conversion",
    "capex_calculated_to_revenue",
    "net_debt_to_ebitda",
    "return_on_period_end_equity",
    "equity_ratio_recomputed",
)
_VALUATION_NAMES = (
    "enterprise_value_to_ebitda",
    "price_to_earnings_calculated",
    "price_to_book",
    "free_cash_flow_yield",
)


def build_research_note_context(
    *,
    run_id: str = RESEARCH_RUN_ID,
    repository: EquityRepository | None = None,
    fundamentals: FundamentalAnalysis | None = None,
    valuation: ValuationAnalysis | None = None,
    climate_metrics: tuple[MetricValue, ...] | None = None,
    corpus: SustainabilityCorpus | None = None,
) -> ResearchNoteContext:
    """Build the minimum allowlisted context from committed offline artifacts."""

    repository = repository or load_equity_repository()
    fundamentals = fundamentals or build_fundamental_analysis(repository)
    valuation = valuation or build_valuation_analysis(repository, fundamentals)
    corpus = corpus or load_corpus(CLIMATE_FIXTURE_CUTOFF)
    climate_metrics = climate_metrics or build_climate_metrics(repository, corpus)

    selected: list[MetricValue] = []
    for company_id in ("bachem", "siegfried"):
        selected.extend(
            fundamentals.metric(company_id, 2025, name)
            for name in _FUNDAMENTAL_NAMES
        )
        selected.extend(
            valuation.metric(company_id, 2025, name)
            for name in _VALUATION_NAMES
        )
        selected.extend(
            metric
            for metric in climate_metrics
            if metric.company_id == company_id
            and metric.name == "scope_1_2_market_based_intensity"
        )

    metric_records = create_equity_metric_records(run_id, tuple(selected))
    evidence_records = create_equity_evidence_records(run_id, corpus)
    documents = {document.document_id: document for document in corpus.documents}
    authorized_sources = (
        AuthorizedSource(
            evidence_id=evidence_records[0].evidence_id,
            title="V4.1 bounded Equity research scope",
            source_uri="docs/plans/PLAN_V4_1_EQUITY_RESEARCH_COPILOT.md",
            page=1,
        ),
        *(
            AuthorizedSource(
                evidence_id=record.evidence_id,
                title=documents[record.document_id].title,
                source_uri=documents[record.document_id].official_page_url,
                page=record.page,
            )
            for record in evidence_records[1:]
        ),
    )
    return ResearchNoteContext(
        run_id=run_id,
        metric_records=metric_records,
        evidence_records=evidence_records,
        authorized_sources=authorized_sources,
        allowed_metric_ids=tuple(record.metric_id for record in metric_records),
        allowed_evidence_ids=tuple(record.evidence_id for record in evidence_records),
        required_limitation_ids=REQUIRED_LIMITATION_IDS,
        output_rules=RESEARCH_OUTPUT_RULES,
    )


def build_deterministic_analyst_note(context: ResearchNoteContext) -> AnalystNoteV1:
    """Create the versioned offline note proposal without network or live LLM calls."""

    scope_evidence = context.evidence_records[0]
    climate_evidence = context.evidence_records[1:]
    def bachem(name: str) -> MetricUse:
        return _metric_use(context.metric("bachem", name))

    def siegfried(name: str) -> MetricUse:
        return _metric_use(context.metric("siegfried", name))

    sections = AnalystNoteSections(
        comparison_scope=_section(
            "Objet de la comparaison et date des données",
            _statement(
                "statement-equity-scope",
                "sourced_fact",
                "The bounded comparison covers Bachem and Siegfried as Swiss CDMOs "
                f"{{{{evidence:{scope_evidence.evidence_id}}}}}.",
                evidence=(_evidence_use(scope_evidence),),
            ),
        ),
        company_profiles=_section(
            "Profils des sociétés et modèles économiques",
            _statement(
                "statement-equity-profiles",
                "analyst_interpretation",
                "The annual dataset presents different operating scale: Bachem revenue is "
                f"{{{{metric:{bachem('revenue').metric_id}}}}} and Siegfried revenue is "
                f"{{{{metric:{siegfried('revenue').metric_id}}}}}.",
                metrics=(bachem("revenue"), siegfried("revenue")),
            ),
        ),
        growth_profitability=_section(
            "Qualité de la croissance et de la rentabilité",
            _statement(
                "statement-equity-growth-profitability",
                "analyst_interpretation",
                "Bachem combines revenue CAGR "
                f"{{{{metric:{bachem('revenue_cagr_2021_2025').metric_id}}}}} with EBITDA "
                f"margin {{{{metric:{bachem('ebitda_margin').metric_id}}}}}; Siegfried records "
                f"revenue CAGR {{{{metric:{siegfried('revenue_cagr_2021_2025').metric_id}}}}} "
                f"and EBITDA margin {{{{metric:{siegfried('ebitda_margin').metric_id}}}}}.",
                metrics=(
                    bachem("revenue_cagr_2021_2025"),
                    bachem("ebitda_margin"),
                    siegfried("revenue_cagr_2021_2025"),
                    siegfried("ebitda_margin"),
                ),
            ),
        ),
        cash_balance_capital_allocation=_section(
            "Cash-flow bilan et allocation du capital",
            _statement(
                "statement-equity-cash-balance",
                "analyst_interpretation",
                "Bachem cash conversion is "
                f"{{{{metric:{bachem('calculated_fcf_cash_conversion').metric_id}}}}} with "
                f"leverage {{{{metric:{bachem('net_debt_to_ebitda').metric_id}}}}}; Siegfried "
                f"cash conversion is {{{{metric:{siegfried('calculated_fcf_cash_conversion').metric_id}}}}} "
                f"with leverage {{{{metric:{siegfried('net_debt_to_ebitda').metric_id}}}}}.",
                metrics=(
                    bachem("calculated_fcf_cash_conversion"),
                    bachem("net_debt_to_ebitda"),
                    siegfried("calculated_fcf_cash_conversion"),
                    siegfried("net_debt_to_ebitda"),
                ),
            ),
        ),
        relative_historical_valuation=_section(
            "Valorisation relative et historique",
            _statement(
                "statement-equity-valuation",
                "calculated_metric",
                "At the historical fiscal close, Bachem EV to EBITDA is "
                f"{{{{metric:{bachem('enterprise_value_to_ebitda').metric_id}}}}} and Siegfried "
                f"EV to EBITDA is {{{{metric:{siegfried('enterprise_value_to_ebitda').metric_id}}}}}.",
                metrics=(
                    bachem("enterprise_value_to_ebitda"),
                    siegfried("enterprise_value_to_ebitda"),
                ),
            ),
        ),
        sustainability_comparability=_section(
            "Durabilité et limites de comparabilité",
            _statement(
                "statement-equity-sustainability",
                "analyst_interpretation",
                "Market-based carbon intensity is "
                f"{{{{metric:{bachem('scope_1_2_market_based_intensity').metric_id}}}}} for Bachem "
                f"and {{{{metric:{siegfried('scope_1_2_market_based_intensity').metric_id}}}}} for "
                f"Siegfried; issuer passages remain separate {{{{evidence:{climate_evidence[0].evidence_id}}}}} "
                f"{{{{evidence:{climate_evidence[1].evidence_id}}}}}.",
                metrics=(
                    bachem("scope_1_2_market_based_intensity"),
                    siegfried("scope_1_2_market_based_intensity"),
                ),
                evidence=tuple(_evidence_use(item) for item in climate_evidence),
                uncertainty="Different assurance statuses limit direct interpretation.",
            ),
        ),
        favorable_arguments=_section(
            "Arguments favorables",
            _statement(
                "statement-equity-favorable",
                "analyst_interpretation",
                "Bachem shows EBITDA margin "
                f"{{{{metric:{bachem('ebitda_margin').metric_id}}}}}; Siegfried shows return on "
                f"period-end equity {{{{metric:{siegfried('return_on_period_end_equity').metric_id}}}}}.",
                metrics=(
                    bachem("ebitda_margin"),
                    siegfried("return_on_period_end_equity"),
                ),
            ),
        ),
        risks_attention=_section(
            "Risques et points d attention",
            _statement(
                "statement-equity-risks",
                "analyst_interpretation",
                "Bachem capex to revenue is "
                f"{{{{metric:{bachem('capex_calculated_to_revenue').metric_id}}}}}; Siegfried "
                f"net debt to EBITDA is {{{{metric:{siegfried('net_debt_to_ebitda').metric_id}}}}}.",
                metrics=(
                    bachem("capex_calculated_to_revenue"),
                    siegfried("net_debt_to_ebitda"),
                ),
            ),
        ),
        catalysts=_section(
            "Catalyseurs",
            _statement(
                "statement-equity-catalysts",
                "analyst_interpretation",
                "Later reported improvement would be observable through Bachem cash conversion "
                f"{{{{metric:{bachem('calculated_fcf_cash_conversion').metric_id}}}}} and Siegfried "
                f"cash conversion {{{{metric:{siegfried('calculated_fcf_cash_conversion').metric_id}}}}}.",
                metrics=(
                    bachem("calculated_fcf_cash_conversion"),
                    siegfried("calculated_fcf_cash_conversion"),
                ),
                uncertainty="This is a monitoring condition, not a forecast.",
            ),
        ),
        monitoring_indicators=_section(
            "Indicateurs à suivre",
            _statement(
                "statement-equity-monitoring",
                "calculated_metric",
                "The monitoring baseline includes Bachem EBIT margin "
                f"{{{{metric:{bachem('ebit_margin').metric_id}}}}} and Siegfried EBIT margin "
                f"{{{{metric:{siegfried('ebit_margin').metric_id}}}}}.",
                metrics=(bachem("ebit_margin"), siegfried("ebit_margin")),
            ),
        ),
        comparative_conclusion=_section(
            "Conclusion comparative",
            _statement(
                "statement-equity-conclusion",
                "analyst_interpretation",
                "Bachem has the higher EBITDA margin at "
                f"{{{{metric:{bachem('ebitda_margin').metric_id}}}}}, while Siegfried has the "
                f"lower historical EV to EBITDA at {{{{metric:{siegfried('enterprise_value_to_ebitda').metric_id}}}}}; "
                "the profiles involve different trade-offs and require human judgment.",
                metrics=(
                    bachem("ebitda_margin"),
                    siegfried("enterprise_value_to_ebitda"),
                ),
            ),
        ),
    )
    limitation_texts = (
        "The comparison universe contains only Bachem and Siegfried.",
        "Only annual data are included; interim periods are outside the pipeline.",
        "Valuation observations are historical fiscal closing values, not current prices.",
        "No market consensus is included.",
        "No forecast or price prediction is produced.",
        "Bachem published price to earnings data are unavailable and are not invented.",
    )
    return AnalystNoteV1(
        note_id="analyst-note-bachem-siegfried-v1",
        run_id=context.run_id,
        comparison_as_of=RESEARCH_COMPARISON_DATE,
        data_period="FY2021-FY2025",
        executive_summary=(
            "Bachem and Siegfried show distinct growth, profitability, cash, balance-sheet, "
            "valuation and sustainability profiles; the comparison remains nuanced."
        ),
        sections=sections,
        limitations=tuple(
            NoteLimitation(limitation_id=limitation_id, text=text)
            for limitation_id, text in zip(
                REQUIRED_LIMITATION_IDS, limitation_texts, strict=True
            )
        ),
        ai_assistance_disclosure=(
            "AI assistance is limited to deterministic note structuring. Python owns all "
            "calculations and checks; final analytical judgment belongs to a human reviewer."
        ),
    )


def materialize_research_draft(note: AnalystNoteV1) -> GeneratedDraft:
    """Adapt analyst_note.v1 to the historical GeneratedDraft contract."""

    claims = tuple(
        ClaimProposal(
            text_template=statement.text_template,
            claim_type=_claim_type(statement),
            metric_ids=tuple(item.metric_id for item in statement.metric_uses),
            evidence_ids=tuple(item.evidence_id for item in statement.evidence_uses),
            uncertainty=statement.uncertainty,
        )
        for statement in note.statements
    )
    proposal = DraftProposal(
        summary=note.executive_summary,
        claims=claims,
        limitations=tuple(item.text for item in note.limitations),
    )
    metadata = GenerationMetadata(
        provider="offline-fixture",
        model_id="equity-note-structure-v1",
        parameters=(),
        prompt_version="analyst-note-v1",
        response_id="response-equity-note-v1",
        generated_at=datetime(2026, 3, 12, tzinfo=UTC),
    )
    return materialize_generated_draft(note.run_id, proposal, metadata)


def validate_research_note(
    *,
    note: AnalystNoteV1,
    draft: GeneratedDraft,
    context: ResearchNoteContext,
) -> ValidationReport:
    """Apply historical trust validation plus Equity-specific structured checks."""

    base = validate_draft(
        run_id=context.run_id,
        draft=draft,
        metrics=context.metric_records,
        evidence=context.evidence_records,
    )
    issues = list(base.issues)
    metric_by_id = {record.metric_id: record for record in context.metric_records}
    evidence_by_id = {record.evidence_id: record for record in context.evidence_records}

    for statement, claim in zip(note.statements, draft.claims, strict=False):
        for use in statement.metric_uses:
            record = metric_by_id.get(use.metric_id)
            if record is None:
                continue
            if not math.isclose(use.value, record.value, rel_tol=0.0, abs_tol=1e-12):
                issues.append(
                    ValidationIssue(
                        code="reference_value_mismatch",
                        severity="critical",
                        claim_id=claim.claim_id,
                        message=f"Metric value does not match {use.metric_id}.",
                    )
                )
            if use.unit != record.unit:
                issues.append(
                    ValidationIssue(
                        code="reference_unit_mismatch",
                        severity="critical",
                        claim_id=claim.claim_id,
                        message=f"Metric unit does not match {use.metric_id}.",
                    )
                )
            if use.period != record.horizon_or_frequency:
                issues.append(
                    ValidationIssue(
                        code="reference_period_mismatch",
                        severity="critical",
                        claim_id=claim.claim_id,
                        message=f"Metric period does not match {use.metric_id}.",
                    )
                )
        for use in statement.evidence_uses:
            record = evidence_by_id.get(use.evidence_id)
            if record is not None and use.exact_excerpt != record.excerpt:
                issues.append(
                    ValidationIssue(
                        code="evidence_reference_mismatch",
                        severity="critical",
                        claim_id=claim.claim_id,
                        message=f"Evidence excerpt does not match {use.evidence_id}.",
                    )
                )

    limitation_ids = tuple(item.limitation_id for item in note.limitations)
    if limitation_ids != context.required_limitation_ids:
        issues.append(
            ValidationIssue(
                code="missing_required_limitation",
                severity="critical",
                message="The note omits at least one mandatory source or scope limitation.",
            )
        )
    for claim in draft.claims:
        for text in filter(None, (claim.text_template, claim.uncertainty)):
            reason = prohibited_output_reason(text)
            issue_code = {
                "recommendation": "prohibited_investment_recommendation",
                "target_price": "prohibited_target_price",
                "prediction": "prohibited_price_prediction",
                "personalized_recommendation": "prohibited_personalized_recommendation",
            }.get(reason)
            if issue_code is not None:
                issues.append(
                    ValidationIssue(
                        code=issue_code,
                        severity="critical",
                        claim_id=claim.claim_id,
                        message=f"Equity output policy violation: {reason}.",
                    )
                )

    return build_validation_report(
        run_id=context.run_id,
        draft_id=draft.draft_id,
        issues=tuple(issues),
        trusted_input_count=len(context.metric_records) + len(context.evidence_records),
    )


def run_equity_research_note(
    scenario: Literal["admissible", "blocked"] = "admissible",
) -> EquityResearchResult:
    """Run the complete deterministic note flow and stop before human approval."""

    context = build_research_note_context()
    note = build_deterministic_analyst_note(context)
    draft = materialize_research_draft(note)
    if scenario == "blocked":
        last_claim = draft.claims[-1].model_copy(
            update={
                "text_template": draft.claims[-1].text_template
                + " A target price is warranted."
            }
        )
        draft = draft.model_copy(update={"claims": (*draft.claims[:-1], last_claim)})
    report = validate_research_note(note=note, draft=draft, context=context)
    assessment = assess_draft(report=report)
    rendered = render_validated_draft(
        draft=draft,
        report=report,
        metrics=context.metric_records,
        evidence=context.evidence_records,
    )
    review_status: Literal["pending_human_review", "blocked"] = (
        "pending_human_review"
        if assessment.status == "eligible_for_review" and rendered.reliable
        else "blocked"
    )
    return EquityResearchResult(
        run_id=context.run_id,
        scenario=scenario,
        context=context,
        analyst_note=note,
        draft=draft,
        validation_report=report,
        assessment=assessment,
        rendered_draft=rendered,
        review_status=review_status,
        human_review=None,
    )


def _metric_use(record: MetricRecord) -> MetricUse:
    return MetricUse(
        metric_id=record.metric_id,
        value=record.value,
        unit=record.unit,
        period=record.horizon_or_frequency,
    )


def _evidence_use(record: EvidenceRecord) -> EvidenceUse:
    return EvidenceUse(evidence_id=record.evidence_id, exact_excerpt=record.excerpt)


def _statement(
    statement_id: str,
    kind: Literal[
        "sourced_fact",
        "calculated_metric",
        "analyst_interpretation",
        "limitation",
    ],
    text_template: str,
    *,
    metrics: tuple[MetricUse, ...] = (),
    evidence: tuple[EvidenceUse, ...] = (),
    uncertainty: str | None = None,
) -> NoteStatement:
    return NoteStatement(
        statement_id=statement_id,
        kind=kind,
        text_template=text_template,
        metric_uses=metrics,
        evidence_uses=evidence,
        uncertainty=uncertainty,
    )


def _section(title: str, statement: NoteStatement) -> NoteSection:
    return NoteSection(title=title, statements=(statement,))


def _claim_type(statement: NoteStatement) -> Literal[
    "quantitative", "evidence", "limitation"
]:
    if statement.kind == "sourced_fact":
        return "evidence"
    if statement.metric_uses:
        return "quantitative"
    if statement.evidence_uses:
        return "evidence"
    return "limitation"
