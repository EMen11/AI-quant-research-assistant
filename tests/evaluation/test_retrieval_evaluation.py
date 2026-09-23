"""Evaluation contract tests for the frozen ten-question retrieval gold set."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_quant.retrieval import (
    RetrievalEvaluationArtifact,
    evaluate_retrieval,
    load_gold_cases,
)

GOLD = Path("tests/evaluation/retrieval_gold.v1.jsonl")
ARTIFACT = Path("reports/evaluation/retrieval_baselines.v1.json")


def test_gold_set_has_exactly_ten_valid_unique_cases() -> None:
    cases = load_gold_cases(GOLD)

    assert len(cases) == 10
    assert len({case.question_id for case in cases}) == 10


def test_retrieval_metrics_capture_recall_and_first_rank() -> None:
    artifact = evaluate_retrieval(GOLD)
    results = {
        (result.baseline, result.question_id): result for result in artifact.question_results
    }

    easy = results[("bm25", "retrieval-bachem-scope-one-value")]
    difficult = results[("bm25", "retrieval-siegfried-supplier-instruments")]
    long_context = results[("long_context", "retrieval-siegfried-energy-unit")]
    assert easy.recall_at_1 and easy.recall_at_3 and easy.first_relevant_rank == 1
    assert not difficult.recall_at_1 and difficult.recall_at_3
    assert difficult.first_relevant_rank == 2
    assert not long_context.recall_at_3 and long_context.first_relevant_rank == 6


def test_evaluation_separates_filter_only_cases_from_ranking_quality() -> None:
    artifact = evaluate_retrieval(GOLD)
    bm25_results = tuple(
        result for result in artifact.question_results if result.baseline == "bm25"
    )

    assert artifact.case_type_counts.filter_only == 6
    assert artifact.case_type_counts.ranking == 4
    assert artifact.case_type_counts.total == 10
    assert sum(result.case_type == "filter_only" for result in bm25_results) == 6
    assert sum(result.case_type == "ranking" for result in bm25_results) == 4
    assert all(
        result.candidate_count_after_filters == 1
        for result in bm25_results
        if result.case_type == "filter_only"
    )
    assert all(
        result.candidate_count_after_filters >= 2
        for result in bm25_results
        if result.case_type == "ranking"
    )

    ranking = {aggregate.baseline: aggregate for aggregate in artifact.ranking_aggregates}
    assert ranking["bm25"].question_count == 4
    assert ranking["bm25"].recall_at_1 == pytest.approx(0.75)
    assert ranking["bm25"].recall_at_3 == pytest.approx(1.0)
    assert ranking["long_context"].question_count == 4
    assert ranking["long_context"].recall_at_1 == pytest.approx(0.25)
    assert ranking["long_context"].recall_at_3 == pytest.approx(0.75)


def test_evaluation_artifact_is_byte_deterministic() -> None:
    first = evaluate_retrieval(GOLD).model_dump_json(indent=2)
    second = evaluate_retrieval(GOLD).model_dump_json(indent=2)

    assert first == second


def test_committed_evaluation_artifact_matches_regeneration() -> None:
    committed = RetrievalEvaluationArtifact.model_validate_json(
        ARTIFACT.read_text(encoding="utf-8")
    )

    assert committed == evaluate_retrieval(GOLD)
