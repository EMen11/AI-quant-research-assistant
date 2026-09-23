"""Convert retrieved passages into server-owned, run-scoped evidence records."""

from __future__ import annotations

from ai_quant.retrieval.models import RetrievalResult
from ai_quant.trust.models import EvidenceRecord


def evidence_records_from_results(
    run_id: str,
    results: tuple[RetrievalResult, ...],
) -> tuple[EvidenceRecord, ...]:
    """Assign evidence IDs in Python while retaining complete official provenance."""

    return tuple(
        EvidenceRecord(
            evidence_id=f"evidence-{run_id}-retrieval-{index:02d}",
            run_id=run_id,
            document_id=result.passage.document_id,
            document_sha256=result.passage.document_sha256,
            page=result.passage.pdf_page,
            excerpt=result.passage.text,
            period=result.passage.period_label,
            unit=None,
            status="official_corpus_passage",
            passage_id=result.passage.passage_id,
            source_record_type=result.passage.source_record_type,
            source_record_id=result.passage.source_record_id,
            issuer_id=result.passage.issuer_id,
            publication_date=result.passage.publication_date,
            printed_page=result.passage.printed_page,
        )
        for index, result in enumerate(results, start=1)
    )
