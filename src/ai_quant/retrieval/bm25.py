"""Small deterministic BM25 baseline with metadata filtering."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from ai_quant.retrieval.corpus import filter_passages
from ai_quant.retrieval.models import (
    BM25Parameters,
    PassageFilter,
    RetrievalPassage,
    RetrievalResult,
)

_TOKEN = re.compile(r"[a-z0-9]+")


class RetrievalQueryError(ValueError):
    """Raised when a retrieval query cannot be evaluated."""


def tokenize(text: str) -> tuple[str, ...]:
    """Normalize Unicode, remove accents, lowercase and keep alphanumeric tokens."""

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return tuple(_TOKEN.findall(ascii_text.lower()))


class BM25Retriever:
    """Exact in-memory BM25 over a small immutable passage tuple."""

    def __init__(
        self,
        passages: tuple[RetrievalPassage, ...],
        parameters: BM25Parameters | None = None,
    ) -> None:
        if any(not passage.text.strip() for passage in passages):
            raise ValueError("BM25 cannot index an empty passage.")
        self.passages = passages
        self.parameters = parameters or BM25Parameters()

    def search(
        self,
        query: str,
        *,
        filters: PassageFilter | None = None,
        top_k: int = 3,
    ) -> tuple[RetrievalResult, ...]:
        """Filter first, then rank by score with passage ID as stable tie-breaker."""

        query_tokens = tokenize(query)
        if not query_tokens:
            raise RetrievalQueryError("Retrieval query must contain at least one token.")
        if top_k < 1:
            raise ValueError("top_k must be at least one.")

        candidates = filter_passages(self.passages, filters or PassageFilter())
        if not candidates:
            return ()
        tokenized = {passage.passage_id: tokenize(passage.text) for passage in candidates}
        average_length = sum(len(tokens) for tokens in tokenized.values()) / len(candidates)
        document_frequency = Counter(
            token
            for tokens in tokenized.values()
            for token in set(tokens)
        )
        scored = [
            (
                self._score(
                    query_tokens,
                    tokenized[passage.passage_id],
                    document_frequency,
                    len(candidates),
                    average_length,
                ),
                passage,
            )
            for passage in candidates
        ]
        ranked = sorted(scored, key=lambda item: (-item[0], item[1].passage_id))[:top_k]
        return tuple(
            RetrievalResult(
                schema_version="retrieval-result.v1",
                baseline="bm25",
                rank=rank,
                score=score,
                passage=passage,
            )
            for rank, (score, passage) in enumerate(ranked, start=1)
        )

    def _score(
        self,
        query_tokens: tuple[str, ...],
        document_tokens: tuple[str, ...],
        document_frequency: Counter[str],
        document_count: int,
        average_length: float,
    ) -> float:
        frequencies = Counter(document_tokens)
        score = 0.0
        for token in query_tokens:
            term_frequency = frequencies[token]
            if term_frequency == 0:
                continue
            frequency = document_frequency[token]
            inverse_document_frequency = math.log(
                1 + (document_count - frequency + 0.5) / (frequency + 0.5)
            )
            length_ratio = len(document_tokens) / average_length if average_length else 0.0
            denominator = term_frequency + self.parameters.k1 * (
                1 - self.parameters.b + self.parameters.b * length_ratio
            )
            score += inverse_document_frequency * (
                term_frequency * (self.parameters.k1 + 1) / denominator
            )
        return score
