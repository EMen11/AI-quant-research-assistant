"""Strict contracts for deterministic offline retrieval."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ai_quant.sustainability.models import IndicatorType
from ai_quant.trust.models import Identifier, NonEmptyText, Sha256, StrictModel

PassageRecordType = Literal[
    "sustainability_observation",
    "climate_target",
    "coverage_finding",
]
RetrievalCategory = Literal[
    "exact_value",
    "unit",
    "scope_2_market_based",
    "scope_2_location_based",
    "energy",
    "reported_zero",
    "climate_target",
    "target_year",
    "cross_issuer",
    "explicit_non_publication",
]


class RetrievalPassage(StrictModel):
    """One traceable passage built only from a typed committed corpus record."""

    schema_version: Literal["retrieval-passage.v1"]
    passage_id: Identifier
    source_record_type: PassageRecordType
    source_record_id: Identifier
    issuer_id: Identifier
    document_id: Identifier
    document_sha256: Sha256
    document_title_or_type: NonEmptyText
    years: Annotated[tuple[int, ...], Field(min_length=1)]
    period_label: NonEmptyText
    publication_date: date
    pdf_page: int = Field(ge=1)
    printed_page: int | None = Field(default=None, ge=1)
    indicator_type: IndicatorType
    text: Annotated[str, Field(min_length=1, max_length=4_000)]

    @field_validator("text")
    @classmethod
    def text_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Retrieval passage text must not be blank.")
        return value

    @model_validator(mode="after")
    def years_are_canonical(self) -> RetrievalPassage:
        if self.years != tuple(sorted(set(self.years))):
            raise ValueError("Passage years must be sorted and unique.")
        return self


class PassageFilter(StrictModel):
    """Deterministic metadata constraints applied before either baseline."""

    issuer_ids: tuple[Identifier, ...] = ()
    document_ids: tuple[Identifier, ...] = ()
    years: tuple[int, ...] = ()
    source_record_types: tuple[PassageRecordType, ...] = ()
    indicator_types: tuple[IndicatorType, ...] = ()
    publication_cutoff: date | None = None

    @model_validator(mode="after")
    def filters_are_unique(self) -> PassageFilter:
        for field_name in (
            "issuer_ids",
            "document_ids",
            "years",
            "source_record_types",
            "indicator_types",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} filter values must be unique.")
        return self


class BM25Parameters(StrictModel):
    schema_version: Literal["bm25-parameters.v1"] = "bm25-parameters.v1"
    k1: float = Field(default=1.5, gt=0)
    b: float = Field(default=0.75, ge=0, le=1)
    tokenizer_version: Literal["unicode-alnum-lower-v1"] = "unicode-alnum-lower-v1"


class RetrievalResult(StrictModel):
    schema_version: Literal["retrieval-result.v1"]
    baseline: Literal["bm25"]
    rank: int = Field(ge=1)
    score: float = Field(ge=0)
    passage: RetrievalPassage

    @field_validator("score")
    @classmethod
    def score_is_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Retrieval score must be finite.")
        return value


class LongContextResult(StrictModel):
    schema_version: Literal["long-context-result.v1"]
    baseline: Literal["long_context"]
    ordering: Literal["publication-document-page-passage-v1"]
    passage_ids: tuple[Identifier, ...]
    context: str
    character_count: int = Field(ge=0)
    max_characters: int = Field(ge=1)

    @model_validator(mode="after")
    def size_matches_context(self) -> LongContextResult:
        if self.character_count != len(self.context):
            raise ValueError("Long-context character_count does not match context.")
        if self.character_count > self.max_characters:
            raise ValueError("Long context exceeds its declared maximum size.")
        return self


class RetrievalGoldCase(StrictModel):
    """One frozen retrieval oracle backed by committed corpus records."""

    schema_version: Literal["retrieval-gold-case.v1"]
    question_id: Identifier
    question: NonEmptyText
    filters: PassageFilter
    relevant_passage_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    expected_document_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    expected_pdf_pages: Annotated[tuple[int, ...], Field(min_length=1)]
    category: RetrievalCategory
    justification: NonEmptyText

    @model_validator(mode="after")
    def oracle_values_are_unique(self) -> RetrievalGoldCase:
        for field_name in (
            "relevant_passage_ids",
            "expected_document_ids",
            "expected_pdf_pages",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} values must be unique.")
        return self
