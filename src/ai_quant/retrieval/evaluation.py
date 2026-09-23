"""Reproducible evaluation for BM25 and canonical long-context baselines."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_quant.retrieval.bm25 import BM25Retriever
from ai_quant.retrieval.corpus import build_retrieval_passages, filter_passages
from ai_quant.retrieval.long_context import LongContextBuilder
from ai_quant.retrieval.models import (
    BM25Parameters,
    RetrievalGoldCase,
    RetrievalPassage,
)
from ai_quant.sustainability.corpus import fixture_directory
from ai_quant.trust.models import Identifier, NonEmptyText, Sha256, StrictModel

DEFAULT_CUTOFF = date(2026, 3, 12)
DEFAULT_LONG_CONTEXT_LIMIT = 50_000
CaseType = Literal["filter_only", "ranking"]


class SourceArtifactHash(StrictModel):
    path: NonEmptyText
    schema_version: NonEmptyText
    sha256: Sha256


class BaselineQuestionResult(StrictModel):
    baseline: Literal["bm25", "long_context"]
    question_id: Identifier
    returned_passage_ids: tuple[Identifier, ...]
    relevant_passage_ids: tuple[Identifier, ...]
    candidate_count_after_filters: int = Field(ge=1)
    case_type: CaseType
    recall_at_1: bool
    recall_at_3: bool
    first_relevant_rank: int | None = Field(default=None, ge=1)
    context_characters: int = Field(ge=0)
    failure: str | None = None


class BaselineAggregate(StrictModel):
    baseline: Literal["bm25", "long_context"]
    question_count: int = Field(ge=1)
    recall_at_1: float = Field(ge=0, le=1)
    recall_at_3: float = Field(ge=0, le=1)
    missing_question_ids: tuple[Identifier, ...]
    mean_context_characters: float = Field(ge=0)
    max_context_characters: int = Field(ge=0)
    latency_ms: None = None
    latency_note: Literal["runtime latency intentionally excluded from deterministic artifact"]


class CaseTypeCounts(StrictModel):
    filter_only: int = Field(ge=0)
    ranking: int = Field(ge=1)
    total: int = Field(ge=1)

    @model_validator(mode="after")
    def counts_sum_to_total(self) -> CaseTypeCounts:
        if self.filter_only + self.ranking != self.total:
            raise ValueError("Retrieval case-type counts must sum to total.")
        return self


class RetrievalEvaluationArtifact(StrictModel):
    schema_version: Literal["retrieval-baselines.v1"]
    generation_convention: Literal[
        "no runtime timestamp; deterministic content from versioned inputs"
    ]
    cutoff_date: date
    gold_set_path: NonEmptyText
    gold_set_sha256: Sha256
    source_artifacts: Annotated[tuple[SourceArtifactHash, ...], Field(min_length=1)]
    corpus_size: int = Field(ge=1)
    indexed_record_types: tuple[str, ...]
    excluded_free_text: tuple[str, ...]
    filter_definition: NonEmptyText
    bm25_parameters: BM25Parameters
    long_context_limit_characters: int = Field(ge=1)
    long_context_interpretation: NonEmptyText
    question_results: Annotated[tuple[BaselineQuestionResult, ...], Field(min_length=1)]
    aggregates: Annotated[tuple[BaselineAggregate, ...], Field(min_length=2, max_length=2)]
    case_type_counts: CaseTypeCounts
    ranking_aggregates: Annotated[
        tuple[BaselineAggregate, ...], Field(min_length=2, max_length=2)
    ]
    observed_failures: tuple[NonEmptyText, ...]
    regeneration_command: NonEmptyText


def load_gold_cases(path: Path) -> tuple[RetrievalGoldCase, ...]:
    cases = tuple(
        RetrievalGoldCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(cases) != 10:
        raise ValueError(f"Retrieval gold set must contain exactly 10 cases; found {len(cases)}.")
    if len({case.question_id for case in cases}) != len(cases):
        raise ValueError("Retrieval gold question IDs must be unique.")
    return cases


def evaluate_retrieval(gold_path: Path) -> RetrievalEvaluationArtifact:
    """Evaluate both baselines without network, LLM or runtime-dependent fields."""

    passages = build_retrieval_passages(DEFAULT_CUTOFF)
    cases = load_gold_cases(gold_path)
    _validate_gold_references(cases, passages)
    parameters = BM25Parameters()
    bm25 = BM25Retriever(passages, parameters)
    long_context = LongContextBuilder(
        passages, max_characters=DEFAULT_LONG_CONTEXT_LIMIT
    )

    results: list[BaselineQuestionResult] = []
    case_types: dict[str, tuple[int, CaseType]] = {}
    for case in cases:
        candidates = filter_passages(passages, case.filters)
        candidate_ids = tuple(passage.passage_id for passage in candidates)
        case_type: CaseType = (
            "filter_only"
            if len(candidate_ids) == 1
            and candidate_ids[0] in set(case.relevant_passage_ids)
            else "ranking"
        )
        case_types[case.question_id] = (len(candidates), case_type)
        bm25_results = bm25.search(case.question, filters=case.filters, top_k=3)
        bm25_ids = tuple(result.passage.passage_id for result in bm25_results)
        bm25_characters = sum(len(result.passage.text) for result in bm25_results)
        results.append(
            _question_result(
                baseline="bm25",
                case=case,
                returned_ids=bm25_ids,
                context_characters=bm25_characters,
                candidate_count_after_filters=len(candidates),
                case_type=case_type,
            )
        )

        context = long_context.build(case.filters)
        results.append(
            _question_result(
                baseline="long_context",
                case=case,
                returned_ids=context.passage_ids,
                context_characters=context.character_count,
                candidate_count_after_filters=len(candidates),
                case_type=case_type,
            )
        )

    result_tuple = tuple(results)
    aggregates = (
        _aggregate("bm25", result_tuple),
        _aggregate("long_context", result_tuple),
    )
    ranking_aggregates = (
        _aggregate("bm25", result_tuple, case_type="ranking"),
        _aggregate("long_context", result_tuple, case_type="ranking"),
    )
    failures = tuple(
        f"{result.baseline}:{result.question_id}: {result.failure}"
        for result in result_tuple
        if result.failure is not None
    )
    return RetrievalEvaluationArtifact(
        schema_version="retrieval-baselines.v1",
        generation_convention=(
            "no runtime timestamp; deterministic content from versioned inputs"
        ),
        cutoff_date=DEFAULT_CUTOFF,
        gold_set_path=gold_path.as_posix(),
        gold_set_sha256=_sha256(gold_path),
        source_artifacts=_source_artifact_hashes(),
        corpus_size=len(passages),
        indexed_record_types=(
            "sustainability_observation",
            "climate_target",
            "coverage_finding_with_page_and_excerpt",
        ),
        excluded_free_text=(
            "coverage report limitations",
            "administrative human-review comments",
            "coverage findings without an exact page and excerpt",
        ),
        filter_definition=(
            "Conjunctive across issuer, document, year, source record type, indicator "
            "type and publication cutoff; disjunctive within each populated field."
        ),
        bm25_parameters=parameters,
        long_context_limit_characters=DEFAULT_LONG_CONTEXT_LIMIT,
        long_context_interpretation=(
            "All filtered passages are supplied in canonical order. recall@1, recall@3 "
            "and first rank use canonical position only and are not probabilistic lexical "
            "ranking metrics for this baseline."
        ),
        question_results=result_tuple,
        aggregates=aggregates,
        case_type_counts=CaseTypeCounts(
            filter_only=sum(case_type == "filter_only" for _, case_type in case_types.values()),
            ranking=sum(case_type == "ranking" for _, case_type in case_types.values()),
            total=len(case_types),
        ),
        ranking_aggregates=ranking_aggregates,
        observed_failures=failures,
        regeneration_command=(
            "uv run --frozen python -m ai_quant.retrieval.cli evaluate "
            "--output reports/evaluation/retrieval_baselines.v1.json"
        ),
    )


def write_evaluation_artifact(artifact: RetrievalEvaluationArtifact, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(artifact.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _question_result(
    *,
    baseline: Literal["bm25", "long_context"],
    case: RetrievalGoldCase,
    returned_ids: tuple[str, ...],
    context_characters: int,
    candidate_count_after_filters: int,
    case_type: CaseType,
) -> BaselineQuestionResult:
    relevant = set(case.relevant_passage_ids)
    first_rank = next(
        (rank for rank, passage_id in enumerate(returned_ids, start=1) if passage_id in relevant),
        None,
    )
    return BaselineQuestionResult(
        baseline=baseline,
        question_id=case.question_id,
        returned_passage_ids=returned_ids,
        relevant_passage_ids=case.relevant_passage_ids,
        candidate_count_after_filters=candidate_count_after_filters,
        case_type=case_type,
        recall_at_1=any(passage_id in relevant for passage_id in returned_ids[:1]),
        recall_at_3=any(passage_id in relevant for passage_id in returned_ids[:3]),
        first_relevant_rank=first_rank,
        context_characters=context_characters,
        failure=(
            "no relevant passage returned"
            if first_rank is None
            else (
                f"first relevant passage is at rank {first_rank}, outside top 3"
                if first_rank > 3
                else None
            )
        ),
    )


def _aggregate(
    baseline: Literal["bm25", "long_context"],
    results: tuple[BaselineQuestionResult, ...],
    *,
    case_type: CaseType | None = None,
) -> BaselineAggregate:
    selected = tuple(
        result
        for result in results
        if result.baseline == baseline
        and (case_type is None or result.case_type == case_type)
    )
    return BaselineAggregate(
        baseline=baseline,
        question_count=len(selected),
        recall_at_1=sum(result.recall_at_1 for result in selected) / len(selected),
        recall_at_3=sum(result.recall_at_3 for result in selected) / len(selected),
        missing_question_ids=tuple(
            result.question_id for result in selected if result.first_relevant_rank is None
        ),
        mean_context_characters=(
            sum(result.context_characters for result in selected) / len(selected)
        ),
        max_context_characters=max(result.context_characters for result in selected),
        latency_ms=None,
        latency_note="runtime latency intentionally excluded from deterministic artifact",
    )


def _validate_gold_references(
    cases: tuple[RetrievalGoldCase, ...], passages: tuple[RetrievalPassage, ...]
) -> None:
    passages_by_id = {passage.passage_id: passage for passage in passages}
    for case in cases:
        unknown = set(case.relevant_passage_ids) - passages_by_id.keys()
        if unknown:
            raise ValueError(f"Gold case {case.question_id} has unknown passages: {sorted(unknown)}.")
        relevant = tuple(passages_by_id[passage_id] for passage_id in case.relevant_passage_ids)
        if {passage.document_id for passage in relevant} != set(case.expected_document_ids):
            raise ValueError(f"Gold case {case.question_id} document oracle is inconsistent.")
        if {passage.pdf_page for passage in relevant} != set(case.expected_pdf_pages):
            raise ValueError(f"Gold case {case.question_id} page oracle is inconsistent.")
        eligible_ids = {
            passage.passage_id for passage in filter_passages(passages, case.filters)
        }
        if not set(case.relevant_passage_ids) <= eligible_ids:
            raise ValueError(f"Gold case {case.question_id} filters exclude its oracle.")


def _source_artifact_hashes() -> tuple[SourceArtifactHash, ...]:
    fixture_dir = fixture_directory()
    definitions = (
        ("manifest.v1.json", "climate-source-manifest.v1"),
        ("observations.v1.jsonl", "sustainability-observation.v1"),
        ("targets.v1.json", "climate-targets.v1"),
        ("coverage_report.v1.json", "climate-coverage-report.v1"),
    )
    return tuple(
        SourceArtifactHash(
            path=f"src/ai_quant/fixtures/sustainability/{filename}",
            schema_version=schema_version,
            sha256=_sha256(fixture_dir / filename),
        )
        for filename, schema_version in definitions
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
