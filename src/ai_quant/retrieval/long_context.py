"""Canonical full-context baseline for the small filtered corpus."""

from __future__ import annotations

from ai_quant.retrieval.corpus import filter_passages
from ai_quant.retrieval.models import LongContextResult, PassageFilter, RetrievalPassage


class LongContextLimitError(ValueError):
    """Raised before an oversized context can be used."""


class LongContextBuilder:
    """Assemble every eligible passage without lexical or probabilistic ranking."""

    def __init__(
        self,
        passages: tuple[RetrievalPassage, ...],
        *,
        max_characters: int = 50_000,
    ) -> None:
        if max_characters < 1:
            raise ValueError("max_characters must be positive.")
        self.passages = passages
        self.max_characters = max_characters

    def build(self, filters: PassageFilter | None = None) -> LongContextResult:
        eligible = sorted(
            filter_passages(self.passages, filters or PassageFilter()),
            key=lambda passage: (
                passage.publication_date,
                passage.document_id,
                passage.pdf_page,
                passage.passage_id,
            ),
        )
        sections = tuple(_format_section(passage) for passage in eligible)
        context = "\n\n".join(sections)
        if len(context) > self.max_characters:
            raise LongContextLimitError(
                f"Long context requires {len(context)} characters; "
                f"limit is {self.max_characters}."
            )
        return LongContextResult(
            schema_version="long-context-result.v1",
            baseline="long_context",
            ordering="publication-document-page-passage-v1",
            passage_ids=tuple(passage.passage_id for passage in eligible),
            context=context,
            character_count=len(context),
            max_characters=self.max_characters,
        )


def _format_section(passage: RetrievalPassage) -> str:
    printed = "none" if passage.printed_page is None else str(passage.printed_page)
    header = (
        f"=== passage_id={passage.passage_id} "
        f"source_record_type={passage.source_record_type} "
        f"source_record_id={passage.source_record_id} "
        f"issuer_id={passage.issuer_id} document_id={passage.document_id} "
        f"document_sha256={passage.document_sha256} "
        f"pdf_page={passage.pdf_page} printed_page={printed} ==="
    )
    return f"{header}\n{passage.text}"
