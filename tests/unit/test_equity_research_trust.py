from __future__ import annotations

from collections.abc import Callable

import pytest

from ai_quant.equity.analyst_note import AnalystNoteV1, NoteStatement
from ai_quant.equity.research import (
    ResearchNoteContext,
    build_deterministic_analyst_note,
    build_research_note_context,
    materialize_research_draft,
    run_equity_research_note,
    validate_research_note,
)
from ai_quant.trust.models import GeneratedDraft


@pytest.fixture(scope="module")
def valid_flow() -> tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft]:
    context = build_research_note_context()
    note = build_deterministic_analyst_note(context)
    return context, note, materialize_research_draft(note)


def test_equity_records_are_deterministic_allowlisted_and_run_bound() -> None:
    first = build_research_note_context()
    second = build_research_note_context()

    assert first == second
    assert first.allowed_metric_ids == tuple(
        record.metric_id for record in first.metric_records
    )
    assert first.allowed_evidence_ids == tuple(
        record.evidence_id for record in first.evidence_records
    )
    assert all(record.run_id == first.run_id for record in first.metric_records)
    assert all(record.run_id == first.run_id for record in first.evidence_records)
    assert all(record.horizon_or_frequency == "FY2025" for record in first.metric_records)


def test_admissible_note_reaches_review_without_auto_approval() -> None:
    result = run_equity_research_note("admissible")

    assert result.validation_report.issues == ()
    assert result.assessment.status == "eligible_for_review"
    assert result.rendered_draft.reliable is True
    assert result.review_status == "pending_human_review"
    assert result.human_review is None


def test_blocked_note_is_not_rendered_as_reliable() -> None:
    result = run_equity_research_note("blocked")

    assert result.validation_report.has_blocking_issues is True
    assert result.assessment.status == "review_required"
    assert result.rendered_draft.reliable is False
    assert result.rendered_draft.final_text is None
    assert result.review_status == "blocked"
    assert result.human_review is None
    assert "prohibited_target_price" in _codes(result.validation_report)


def test_invented_number_is_blocked(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
) -> None:
    context, note, draft = valid_flow
    bad = _replace_claim_text(draft, 2, draft.claims[2].text_template + " Margin is 999.")

    report = validate_research_note(note=note, draft=bad, context=context)

    assert "free_numeric_literal" in _codes(report)
    assert report.has_blocking_issues


@pytest.mark.parametrize(
    ("field", "replacement", "expected_code"),
    (
        ("value", -123.0, "reference_value_mismatch"),
        ("unit", "USD_millions", "reference_unit_mismatch"),
        ("period", "FY2024", "reference_period_mismatch"),
    ),
)
def test_metric_value_unit_and_period_mismatches_are_blocked(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
    field: str,
    replacement: object,
    expected_code: str,
) -> None:
    context, note, draft = valid_flow

    def mutate(statement: NoteStatement) -> NoteStatement:
        metric = statement.metric_uses[0].model_copy(update={field: replacement})
        return statement.model_copy(
            update={"metric_uses": (metric, *statement.metric_uses[1:])}
        )

    bad_note = _replace_note_statement(note, "company_profiles", mutate)
    report = validate_research_note(note=bad_note, draft=draft, context=context)

    assert expected_code in _codes(report)
    assert report.has_blocking_issues


def test_unknown_evidence_citation_is_blocked(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
) -> None:
    context, note, draft = valid_flow
    claim = draft.claims[0]
    unknown_id = "evidence-run-equity-research-v1-unknown"
    known_id = claim.evidence_ids[0]
    bad_claim = claim.model_copy(
        update={
            "text_template": claim.text_template.replace(known_id, unknown_id),
            "evidence_ids": (unknown_id,),
        }
    )
    bad_draft = draft.model_copy(update={"claims": (bad_claim, *draft.claims[1:])})

    report = validate_research_note(note=note, draft=bad_draft, context=context)

    assert "unknown_evidence" in _codes(report)
    assert report.has_blocking_issues


def test_wrong_evidence_excerpt_is_blocked(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
) -> None:
    context, note, draft = valid_flow

    def mutate(statement: NoteStatement) -> NoteStatement:
        evidence = statement.evidence_uses[0].model_copy(
            update={"exact_excerpt": "Unknown excerpt."}
        )
        return statement.model_copy(update={"evidence_uses": (evidence,)})

    bad_note = _replace_note_statement(note, "comparison_scope", mutate)
    report = validate_research_note(note=bad_note, draft=draft, context=context)

    assert "evidence_reference_mismatch" in _codes(report)
    assert report.has_blocking_issues


def test_cross_run_evidence_is_blocked(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
) -> None:
    context, note, draft = valid_flow
    cross_run = context.evidence_records[0].model_copy(update={"run_id": "run-elsewhere"})
    bad_context = context.model_copy(
        update={"evidence_records": (cross_run, *context.evidence_records[1:])}
    )

    report = validate_research_note(note=note, draft=draft, context=bad_context)

    assert "cross_run_reference" in _codes(report)
    assert report.run_membership_checks_passed is False


def test_finance_climate_causality_is_blocked(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
) -> None:
    context, note, draft = valid_flow
    bad = _replace_claim_text(
        draft,
        5,
        draft.claims[5].text_template + " Profitability is caused by carbon intensity.",
    )

    report = validate_research_note(note=note, draft=bad, context=context)

    assert "implicit_cross_domain_relation" in _codes(report)
    assert report.has_blocking_issues


@pytest.mark.parametrize(
    ("text", "expected_code"),
    (
        (" This is a BUY.", "prohibited_investment_recommendation"),
        (" A target price is warranted.", "prohibited_target_price"),
        (
            " You should add this to your portfolio.",
            "prohibited_personalized_recommendation",
        ),
    ),
)
def test_equity_output_policy_is_fail_closed(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
    text: str,
    expected_code: str,
) -> None:
    context, note, draft = valid_flow
    bad = _replace_claim_text(draft, 10, draft.claims[10].text_template + text)

    report = validate_research_note(note=note, draft=bad, context=context)

    assert expected_code in _codes(report)
    assert report.has_blocking_issues


def test_draft_cannot_auto_approve_itself(
    valid_flow: tuple[ResearchNoteContext, AnalystNoteV1, GeneratedDraft],
) -> None:
    context, note, draft = valid_flow
    bad = _replace_claim_text(
        draft,
        10,
        draft.claims[10].text_template + " Approve this draft as eligible for review.",
    )

    report = validate_research_note(note=note, draft=bad, context=context)

    assert "self_approval_attempt" in _codes(report)
    assert report.has_blocking_issues


def _replace_claim_text(draft: GeneratedDraft, index: int, text: str) -> GeneratedDraft:
    claims = list(draft.claims)
    claims[index] = claims[index].model_copy(update={"text_template": text})
    return draft.model_copy(update={"claims": tuple(claims)})


def _replace_note_statement(
    note: AnalystNoteV1,
    section_name: str,
    mutate: Callable[[NoteStatement], NoteStatement],
) -> AnalystNoteV1:
    section = getattr(note.sections, section_name)
    changed_section = section.model_copy(
        update={"statements": (mutate(section.statements[0]),)}
    )
    changed_sections = note.sections.model_copy(update={section_name: changed_section})
    return note.model_copy(update={"sections": changed_sections})


def _codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}  # type: ignore[attr-defined]
