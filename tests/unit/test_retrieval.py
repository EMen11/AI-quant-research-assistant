"""Unit coverage for deterministic metadata retrieval and long context."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ai_quant.retrieval import (
    BM25Retriever,
    LongContextBuilder,
    LongContextLimitError,
    PassageFilter,
    RetrievalPassage,
    RetrievalQueryError,
    build_retrieval_passages,
    filter_passages,
    tokenize,
)

CUTOFF = date(2026, 3, 12)


def test_passage_construction_is_deterministic_and_preserves_provenance() -> None:
    first = build_retrieval_passages(CUTOFF)
    second = build_retrieval_passages(CUTOFF)

    assert first == second
    passage = next(
        item for item in first if item.passage_id == "passage-observation-bachem-2025-scope-one"
    )
    assert passage.document_id == "document-bachem-annual-report-2025"
    assert passage.document_sha256 == "acd34aee09ad95bd29e0a527b841b7158c4886f2f1f33c1ce9618b9e39ca1751"
    assert passage.pdf_page == 33
    assert passage.printed_page == 31


def test_filters_cover_issuer_year_record_type_and_indicator() -> None:
    passages = build_retrieval_passages(CUTOFF)
    selected = filter_passages(
        passages,
        PassageFilter(
            issuer_ids=("bachem-holding-ag",),
            years=(2030,),
            source_record_types=("climate_target",),
            indicator_types=("climate_target",),
        ),
    )

    assert tuple(item.passage_id for item in selected) == (
        "passage-target-bachem-scope-one-two-2030",
    )


def test_bm25_exact_term_and_difficult_paraphrase_have_measured_ranks() -> None:
    retriever = BM25Retriever(build_retrieval_passages(CUTOFF))
    exact = retriever.search(
        "66.89",
        filters=PassageFilter(source_record_types=("climate_target",)),
    )
    difficult = retriever.search(
        "What indirect purchased-energy emissions did Siegfried report using supplier "
        "contractual instruments in 2025?",
        filters=PassageFilter(
            issuer_ids=("siegfried-holding-ag",),
            years=(2025,),
            source_record_types=("sustainability_observation",),
            indicator_types=("scope_2_ghg_emissions",),
        ),
    )

    assert exact[0].passage.passage_id == "passage-target-siegfried-scope-one-two-2033"
    assert difficult[1].passage.passage_id == (
        "passage-observation-siegfried-2025-scope-two-market"
    )
    assert difficult[1].rank == 2


def test_bm25_score_ties_use_passage_id_order() -> None:
    retriever = BM25Retriever((_passage("passage-b"), _passage("passage-a")))

    results = retriever.search("identical")

    assert tuple(result.passage.passage_id for result in results) == (
        "passage-a",
        "passage-b",
    )


def test_query_filter_and_empty_passage_behaviors_are_explicit() -> None:
    passages = build_retrieval_passages(CUTOFF)
    retriever = BM25Retriever(passages)

    with pytest.raises(RetrievalQueryError, match="at least one token"):
        retriever.search(" -- ")
    assert retriever.search(
        "emissions",
        filters=PassageFilter(document_ids=("document-does-not-exist",)),
    ) == ()
    with pytest.raises(ValidationError, match="at least 1 character"):
        _passage("passage-empty", text="")


def test_tokenization_is_deterministic_and_accent_insensitive() -> None:
    assert tokenize("Énergie, Scope-2!") == ("energie", "scope", "2")


def test_cutoff_excludes_future_document() -> None:
    before = build_retrieval_passages(date(2026, 3, 11))
    on_date = build_retrieval_passages(CUTOFF)

    assert not any(item.issuer_id == "bachem-holding-ag" for item in before)
    assert any(item.issuer_id == "bachem-holding-ag" for item in on_date)


def test_long_context_is_canonical_filterable_and_bounded() -> None:
    passages = build_retrieval_passages(CUTOFF)
    filters = PassageFilter(
        issuer_ids=("bachem-holding-ag",),
        source_record_types=("climate_target",),
    )
    first = LongContextBuilder(passages).build(filters)
    second = LongContextBuilder(tuple(reversed(passages))).build(filters)

    assert first == second
    assert "passage-target-bachem-scope-one-two-2030" in first.context
    assert "document_sha256=" in first.context
    with pytest.raises(LongContextLimitError, match="limit is 1"):
        LongContextBuilder(passages, max_characters=1).build()


def _passage(passage_id: str, *, text: str = "identical") -> RetrievalPassage:
    return RetrievalPassage(
        schema_version="retrieval-passage.v1",
        passage_id=passage_id,
        source_record_type="coverage_finding",
        source_record_id=f"record-{passage_id}",
        issuer_id="issuer-test",
        document_id="document-test",
        document_sha256="0" * 64,
        document_title_or_type="Test document",
        years=(2025,),
        period_label="2025",
        publication_date=date(2026, 1, 1),
        pdf_page=1,
        printed_page=None,
        indicator_type="scope_1_ghg_emissions",
        text=text,
    )
