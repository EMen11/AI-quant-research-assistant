"""Build retrievable passages from typed, committed sustainability artifacts."""

from __future__ import annotations

from datetime import date

from ai_quant.retrieval.models import PassageFilter, RetrievalPassage
from ai_quant.sustainability import load_corpus
from ai_quant.sustainability.models import (
    ClimateTarget,
    CoverageFinding,
    SourceDocumentManifest,
    SustainabilityObservation,
)


def build_retrieval_passages(cutoff_date: date) -> tuple[RetrievalPassage, ...]:
    """Build a canonical corpus without PDF, network or free-form limitation text."""

    corpus = load_corpus(cutoff_date)
    documents = {document.document_id: document for document in corpus.documents}
    passages = [
        *(_observation_passage(record, documents[record.document_id]) for record in corpus.observations),
        *(_target_passage(record, documents[record.document_id]) for record in corpus.targets),
        *(
            passage
            for finding in corpus.coverage_report.findings
            if (passage := _coverage_passage(finding, documents)) is not None
        ),
    ]
    return tuple(sorted(passages, key=lambda passage: passage.passage_id))


def filter_passages(
    passages: tuple[RetrievalPassage, ...], filters: PassageFilter
) -> tuple[RetrievalPassage, ...]:
    """Apply the same closed metadata filters for both retrieval baselines."""

    return tuple(
        passage
        for passage in passages
        if (not filters.issuer_ids or passage.issuer_id in filters.issuer_ids)
        and (not filters.document_ids or passage.document_id in filters.document_ids)
        and (not filters.years or set(passage.years).intersection(filters.years))
        and (
            not filters.source_record_types
            or passage.source_record_type in filters.source_record_types
        )
        and (
            not filters.indicator_types
            or passage.indicator_type in filters.indicator_types
        )
        and (
            filters.publication_cutoff is None
            or passage.publication_date <= filters.publication_cutoff
        )
    )


def _observation_passage(
    record: SustainabilityObservation,
    document: SourceDocumentManifest,
) -> RetrievalPassage:
    value = "missing" if record.value is None else str(record.value)
    unit = record.unit or "unit-not-applicable"
    text = (
        f"{record.raw_metric_label}. Indicator {record.indicator_type}. "
        f"Coverage status {record.coverage_status}. Reported value {value} {unit}. "
        f"Scope 2 method {record.scope_2_method}. Basis {record.basis}. "
        f"Period {record.period_start.isoformat()} to {record.period_end.isoformat()}. "
        f"Issuer excerpt: {record.short_exact_excerpt}"
    )
    return RetrievalPassage(
        schema_version="retrieval-passage.v1",
        passage_id=f"passage-{record.observation_id}",
        source_record_type="sustainability_observation",
        source_record_id=record.observation_id,
        issuer_id=record.issuer_id,
        document_id=record.document_id,
        document_sha256=record.document_sha256,
        document_title_or_type=document.title,
        years=_year_range(record.period_start.year, record.period_end.year),
        period_label=f"{record.period_start.isoformat()}/{record.period_end.isoformat()}",
        publication_date=record.publication_date,
        pdf_page=record.pdf_page,
        printed_page=record.printed_page,
        indicator_type=record.indicator_type,
        text=text,
    )


def _target_passage(
    record: ClimateTarget,
    document: SourceDocumentManifest,
) -> RetrievalPassage:
    scopes = ", ".join(record.covered_scopes)
    text = (
        f"Climate target for {scopes}. Target reduction {record.target_value}{record.unit}. "
        f"Base year {record.base_year}. Target year {record.target_year}. "
        f"Validation status {record.validation_status}. "
        f"Issuer excerpt: {record.short_exact_excerpt}"
    )
    return RetrievalPassage(
        schema_version="retrieval-passage.v1",
        passage_id=f"passage-{record.target_id}",
        source_record_type="climate_target",
        source_record_id=record.target_id,
        issuer_id=record.issuer_id,
        document_id=record.document_id,
        document_sha256=record.document_sha256,
        document_title_or_type=document.title,
        years=tuple(sorted({record.base_year, record.target_year})),
        period_label=f"base-year-{record.base_year}/target-year-{record.target_year}",
        publication_date=record.publication_date,
        pdf_page=record.pdf_page,
        printed_page=record.printed_page,
        indicator_type=record.indicator_type,
        text=text,
    )


def _coverage_passage(
    finding: CoverageFinding,
    documents: dict[str, SourceDocumentManifest],
) -> RetrievalPassage | None:
    """Index only findings with an exact page and excerpt, never report limitations."""

    if finding.pdf_page is None or finding.short_exact_excerpt is None:
        return None
    document_id = finding.searched_document_ids[0]
    document = documents[document_id]
    if document.publication_date is None:
        raise ValueError(
            f"Coverage finding {finding.finding_id} references a document "
            "without a known publication date."
        )
    text = (
        f"Coverage finding for {finding.indicator_type}. Status {finding.status}. "
        f"Period {finding.period_start.isoformat()} to {finding.period_end.isoformat()}. "
        f"Issuer excerpt: {finding.short_exact_excerpt}. Notes: {finding.notes}"
    )
    return RetrievalPassage(
        schema_version="retrieval-passage.v1",
        passage_id=f"passage-{finding.finding_id}",
        source_record_type="coverage_finding",
        source_record_id=finding.finding_id,
        issuer_id=finding.issuer_id,
        document_id=document_id,
        document_sha256=document.sha256,
        document_title_or_type=document.title,
        years=_year_range(finding.period_start.year, finding.period_end.year),
        period_label=f"{finding.period_start.isoformat()}/{finding.period_end.isoformat()}",
        publication_date=document.publication_date,
        pdf_page=finding.pdf_page,
        printed_page=finding.printed_page,
        indicator_type=finding.indicator_type,
        text=text,
    )


def _year_range(start_year: int, end_year: int) -> tuple[int, ...]:
    return tuple(range(start_year, end_year + 1))
