from __future__ import annotations

import hashlib
import json
import socket
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ai_quant.analyst_dashboard import (
    METHODOLOGY_LINKS,
    PROJECT_ROOT,
    SESSION_STATE_KEY,
    SessionReview,
    SessionReviewRepository,
    add_human_review,
    approval_allowed,
    build_analyst_dashboard,
    climate_evidence_groups,
    create_corrected_revision,
    decide_export,
    methodology_links_are_backed_by_files,
    metric_views,
    workflow_evidence_views,
)
from ai_quant.config import Settings


@pytest.fixture(scope="module")
def dashboard():
    return build_analyst_dashboard(Settings.from_env({"APP_MODE": "demo"}))


FIXED_REVIEW_TIME = datetime(2026, 9, 24, tzinfo=UTC)


def _approved_session(dashboard):
    session = SessionReviewRepository({}, dashboard.scenarios).get("admissible")
    return add_human_review(
        session,
        disposition="approved",
        comment="Explicit current-version approval.",
        clock=lambda: FIXED_REVIEW_TIME,
    )


def _replace_review(session, binding: SessionReview):
    return replace(session, reviews=(binding,))


def _assert_export_blocked(session) -> None:
    decision = decide_export(session)
    assert decision.allowed is False
    assert decision.payload is None


def _canonical_draft_sha256(draft) -> str:
    canonical_json = json.dumps(
        draft.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def test_admissible_scenario_loads_complete_owned_inputs(dashboard) -> None:
    result = dashboard.scenarios["admissible"]

    assert result.run_id == "run-demo-valid"
    assert result.assessment.status == "eligible_for_review"
    assert result.rendered_draft.reliable is True
    assert result.human_review is None
    assert all(record.run_id == result.run_id for record in result.metric_records)
    assert all(record.run_id == result.run_id for record in result.evidence_records)


def test_blocked_scenario_exposes_findings_and_no_reliable_text(dashboard) -> None:
    result = dashboard.scenarios["blocked"]

    assert result.run_id == "run-demo-blocked"
    assert result.assessment.status == "review_required"
    assert result.validation_report.has_blocking_issues
    assert result.validation_report.issues
    assert result.rendered_draft.reliable is False
    assert result.rendered_draft.final_text is None
    assert result.human_review is None


def test_both_scenarios_are_deterministic_across_two_complete_builds(dashboard) -> None:
    second = build_analyst_dashboard(Settings.from_env({"APP_MODE": "demo"}))

    assert set(dashboard.scenarios) == {"admissible", "blocked"}
    assert len({result.run_id for result in dashboard.scenarios.values()}) == 2
    for key in ("admissible", "blocked"):
        first_result = dashboard.scenarios[key]
        second_result = second.scenarios[key]
        assert first_result.run_id == second_result.run_id
        assert first_result.metric_records == second_result.metric_records
        assert first_result.evidence_records == second_result.evidence_records
        assert first_result.validation_report == second_result.validation_report
        assert first_result.assessment == second_result.assessment


def test_presentation_metric_projection_contains_only_metric_record_values(dashboard) -> None:
    result = dashboard.scenarios["admissible"]
    views = metric_views(result)

    assert len(views) == len(result.metric_records)
    for view, record in zip(views, result.metric_records, strict=True):
        assert view.metric_id == record.metric_id
        assert view.value == record.value
        assert view.unit == record.unit
        assert view.formula_version == record.formula_version
        assert view.snapshot_id == record.snapshot_id


def test_evidence_views_keep_ids_pages_excerpts_and_provenance(dashboard) -> None:
    result = dashboard.scenarios["admissible"]
    view = workflow_evidence_views(result, dashboard.climate_corpus)[0]
    record = result.evidence_records[0]

    assert view.evidence_id == record.evidence_id
    assert view.pdf_page == record.page
    assert view.printed_page == record.printed_page
    assert view.excerpt == record.excerpt
    assert record.document_sha256 in view.source
    assert view.record_type == "sustainability_observation"
    assert view.coverage_status == "reported_zero"
    assert view.scope_2_method == "not_applicable"


def test_workflow_market_based_evidence_is_not_displayed_as_not_applicable(dashboard) -> None:
    result = dashboard.scenarios["admissible"]
    market_observation = next(
        item
        for item in dashboard.climate_corpus.observations
        if item.scope_2_method == "market_based"
    )
    record = result.evidence_records[0].model_copy(
        update={"source_record_id": market_observation.observation_id}
    )
    market_result = replace(result, evidence_records=(record,))

    view = workflow_evidence_views(market_result, dashboard.climate_corpus)[0]

    assert view.record_type == "sustainability_observation"
    assert view.coverage_status == market_observation.coverage_status
    assert view.scope_2_method == "market_based"


def test_scope_two_location_and_market_records_are_never_coalesced(dashboard) -> None:
    groups = climate_evidence_groups(dashboard.climate_corpus)
    location = groups["observed_scope2_location"]
    market = groups["observed_scope2_market"]

    assert location and market
    assert all(item.scope_2_method == "location_based" for item in location)
    assert all(item.scope_2_method == "market_based" for item in market)
    assert {item.evidence_id for item in location}.isdisjoint(
        {item.evidence_id for item in market}
    )


def test_climate_groups_separate_targets_zero_missing_and_not_applicable(dashboard) -> None:
    groups = climate_evidence_groups(dashboard.climate_corpus)

    assert groups["climate_targets"]
    assert groups["explicitly_reported_zero"]
    assert groups["missing_or_ambiguous"]
    assert groups["observed_other_method_not_applicable"]
    assert all(
        item.scope_2_method == "not_applicable"
        for item in groups["observed_other_method_not_applicable"]
    )


def test_automated_assessment_and_human_review_are_separate(dashboard) -> None:
    session = SessionReviewRepository({}, dashboard.scenarios).get("admissible")

    assert session.current.assessment.status == "eligible_for_review"
    assert session.current_review is None
    reviewed = add_human_review(
        session,
        disposition="approved",
        comment="Explicit demo decision.",
        clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
    )
    assert reviewed.current.assessment.status == "eligible_for_review"
    assert reviewed.current_review is not None
    assert reviewed.current_review.review.disposition == "approved"


def test_demo_review_repository_writes_only_supplied_session_mapping(dashboard, tmp_path) -> None:
    state: dict[str, object] = {}
    before = tuple(tmp_path.iterdir())
    repository = SessionReviewRepository(state, dashboard.scenarios)
    reviewed = add_human_review(
        repository.get("admissible"),
        disposition="rejected",
        comment="Session only.",
        clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
    )
    repository.put("admissible", reviewed)

    assert SESSION_STATE_KEY in state
    assert repository.get("admissible").current_review is not None
    assert tuple(tmp_path.iterdir()) == before


@pytest.mark.parametrize("scenario", ("blocked",))
def test_approval_is_blocked_for_review_required(dashboard, scenario) -> None:
    session = SessionReviewRepository({}, dashboard.scenarios).get(scenario)

    assert approval_allowed(session.current) is False
    with pytest.raises(ValueError, match="Approval is forbidden"):
        add_human_review(
            session,
            disposition="approved",
            comment="Must fail.",
            clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
        )


def test_approval_is_blocked_for_abstain(dashboard) -> None:
    session = SessionReviewRepository({}, dashboard.scenarios).get("admissible")
    revision = session.current
    abstain = revision.assessment.model_copy(
        update={
            "status": "abstain",
            "reason_codes": ("insufficient_trusted_inputs",),
        }
    )
    abstaining_revision = revision.__class__(
        version=revision.version,
        draft=revision.draft,
        validation_report=revision.validation_report,
        assessment=abstain,
        rendered_draft=revision.rendered_draft,
        content_origin=revision.content_origin,
        source_generation_origin=revision.source_generation_origin,
    )
    abstaining_session = session.__class__(revisions=(abstaining_revision,))

    assert approval_allowed(abstaining_revision) is False
    assert decide_export(abstaining_session).allowed is False
    with pytest.raises(ValueError, match="Approval is forbidden"):
        add_human_review(
            abstaining_session,
            disposition="approved",
            comment="Must fail.",
            clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
        )


def test_export_requires_approved_review_for_current_version(dashboard) -> None:
    session = SessionReviewRepository({}, dashboard.scenarios).get("admissible")

    no_review = decide_export(session)
    assert no_review.allowed is False
    assert "no HumanReview" in no_review.reason

    rejected = add_human_review(
        session,
        disposition="rejected",
        comment="Rejected.",
        clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
    )
    assert decide_export(rejected).allowed is False

    approved = add_human_review(
        session,
        disposition="approved",
        comment="Approved explicitly.",
        clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
    )
    decision = decide_export(approved)
    assert decision.allowed is True
    assert decision.payload is not None
    payload = json.loads(decision.payload)
    assert payload["human_review_status"] == "approved"
    assert payload["draft_id"] == session.current.draft.draft_id


def test_export_integrity_positive_current_review(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None

    decision = decide_export(session)

    assert decision.allowed is True
    assert decision.payload is not None
    payload = json.loads(decision.payload)
    expected_hash = hashlib.sha256(
        session.current.rendered_draft.final_text.encode("utf-8")
    ).hexdigest()
    expected_draft_hash = _canonical_draft_sha256(session.current.draft)
    assert payload["schema_version"] == "analyst-approved-export.v3"
    assert payload["revision_number"] == session.current.version
    assert payload["approved_draft_sha256"] == expected_draft_hash
    assert payload["approved_final_text_sha256"] == expected_hash
    assert binding.approved_draft_sha256 == expected_draft_hash
    assert binding.approved_final_text_sha256 == expected_hash


def test_draft_hash_blocks_summary_change_with_same_id_and_old_rendering(dashboard) -> None:
    session = _approved_session(dashboard)
    mutated_draft = session.current.draft.model_copy(
        update={"summary": session.current.draft.summary + " Mutated after approval."}
    )

    _assert_export_blocked(
        replace(session, revisions=(replace(session.current, draft=mutated_draft),))
    )


def test_draft_hash_blocks_claim_change_with_same_draft_id(dashboard) -> None:
    session = _approved_session(dashboard)
    first_claim = session.current.draft.claims[0]
    mutated_claim = first_claim.model_copy(
        update={"text_template": first_claim.text_template + " Mutated claim."}
    )
    mutated_draft = session.current.draft.model_copy(
        update={"claims": (mutated_claim, *session.current.draft.claims[1:])}
    )

    _assert_export_blocked(
        replace(session, revisions=(replace(session.current, draft=mutated_draft),))
    )


def test_draft_hash_blocks_added_or_removed_limitation(dashboard) -> None:
    session = _approved_session(dashboard)
    limitations = session.current.draft.limitations
    added = session.current.draft.model_copy(
        update={"limitations": (*limitations, "Mutation after approval.")}
    )
    removed = session.current.draft.model_copy(update={"limitations": limitations[:-1]})

    for mutated_draft in (added, removed):
        _assert_export_blocked(
            replace(session, revisions=(replace(session.current, draft=mutated_draft),))
        )


def test_draft_hash_blocks_reference_change(dashboard) -> None:
    session = _approved_session(dashboard)
    first_claim = session.current.draft.claims[0]
    mutated_claim = first_claim.model_copy(
        update={"metric_ids": ("metric-forged-reference",)}
    )
    mutated_draft = session.current.draft.model_copy(
        update={"claims": (mutated_claim, *session.current.draft.claims[1:])}
    )

    _assert_export_blocked(
        replace(session, revisions=(replace(session.current, draft=mutated_draft),))
    )


def test_draft_hash_blocks_forged_hash(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None

    _assert_export_blocked(
        _replace_review(session, replace(binding, approved_draft_sha256="0" * 64))
    )


def test_draft_hash_blocks_absent_or_invalid_hash(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None

    for invalid_hash in (None, "not-a-sha256"):
        _assert_export_blocked(
            _replace_review(
                session,
                replace(binding, approved_draft_sha256=invalid_hash),
            )
        )


def test_draft_hash_allows_unchanged_legitimately_approved_draft(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None

    decision = decide_export(session)

    assert decision.allowed is True
    assert decision.payload is not None
    expected_hash = _canonical_draft_sha256(session.current.draft)
    assert binding.approved_draft_sha256 == expected_hash
    assert json.loads(decision.payload)["approved_draft_sha256"] == expected_hash


def test_export_blocks_review_from_another_run_with_same_draft(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None
    forged_human = binding.review.model_copy(update={"run_id": "run-foreign-review"})

    _assert_export_blocked(_replace_review(session, replace(binding, review=forged_human)))


def test_export_blocks_validation_report_from_another_run(dashboard) -> None:
    session = _approved_session(dashboard)
    forged_report = session.current.validation_report.model_copy(
        update={"run_id": "run-foreign-validation"}
    )
    forged_revision = replace(session.current, validation_report=forged_report)

    _assert_export_blocked(replace(session, revisions=(forged_revision,)))


def test_export_blocks_validation_report_for_another_draft(dashboard) -> None:
    session = _approved_session(dashboard)
    forged_report = session.current.validation_report.model_copy(
        update={"draft_id": "draft-foreign-validation"}
    )
    forged_revision = replace(session.current, validation_report=forged_report)

    _assert_export_blocked(replace(session, revisions=(forged_revision,)))


def test_export_blocks_review_of_previous_version(dashboard) -> None:
    result = dashboard.scenarios["admissible"]
    session = _approved_session(dashboard)
    corrected = create_corrected_revision(
        session,
        result,
        summary=result.draft.summary + " Previous-version review test.",
        claim_templates=tuple(claim.text_template for claim in result.draft.claims),
        comment="Create a later version.",
        clock=lambda: FIXED_REVIEW_TIME,
    )

    _assert_export_blocked(corrected)


def test_export_blocks_forged_revision_number(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None

    _assert_export_blocked(
        _replace_review(session, replace(binding, revision_number=binding.revision_number + 1))
    )


@pytest.mark.parametrize("reviewer_id", ("", "   "))
def test_export_blocks_empty_or_whitespace_reviewer(dashboard, reviewer_id) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None
    forged_human = binding.review.model_copy(update={"reviewer_id": reviewer_id})

    _assert_export_blocked(_replace_review(session, replace(binding, review=forged_human)))


def test_export_blocks_naive_review_timestamp(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None
    forged_human = binding.review.model_copy(
        update={"reviewed_at": datetime(2026, 9, 24)}
    )

    _assert_export_blocked(_replace_review(session, replace(binding, review=forged_human)))


def test_export_blocks_non_utc_review_timestamp(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None
    forged_human = binding.review.model_copy(
        update={
            "reviewed_at": datetime(
                2026,
                9,
                24,
                tzinfo=timezone(timedelta(hours=2)),
            )
        }
    )

    _assert_export_blocked(_replace_review(session, replace(binding, review=forged_human)))


def test_export_blocks_unknown_disposition(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None
    forged_human = binding.review.model_copy(update={"disposition": "silently-approved"})

    _assert_export_blocked(_replace_review(session, replace(binding, review=forged_human)))


def test_export_blocks_final_text_changed_after_approval(dashboard) -> None:
    session = _approved_session(dashboard)
    rendered = session.current.rendered_draft
    assert rendered.final_text is not None
    forged_rendered = rendered.model_copy(
        update={"final_text": rendered.final_text + " Mutated after approval."}
    )
    forged_revision = replace(session.current, rendered_draft=forged_rendered)

    _assert_export_blocked(replace(session, revisions=(forged_revision,)))


def test_export_blocks_forged_final_text_hash(dashboard) -> None:
    session = _approved_session(dashboard)
    binding = session.current_review
    assert binding is not None

    _assert_export_blocked(
        _replace_review(
            session,
            replace(binding, approved_final_text_sha256="0" * 64),
        )
    )


def test_export_blocks_corrected_revision_not_yet_reviewed(dashboard) -> None:
    result = dashboard.scenarios["admissible"]
    corrected = create_corrected_revision(
        _approved_session(dashboard),
        result,
        summary=result.draft.summary + " Human correction awaiting review.",
        claim_templates=tuple(claim.text_template for claim in result.draft.claims),
        comment="Correction is not approval.",
        clock=lambda: FIXED_REVIEW_TIME,
    )

    assert corrected.current.content_origin == "human-edited-session-revision"
    _assert_export_blocked(corrected)


def test_export_blocks_review_after_scenario_change(dashboard) -> None:
    valid = _approved_session(dashboard)
    valid_binding = valid.current_review
    assert valid_binding is not None
    blocked = SessionReviewRepository({}, dashboard.scenarios).get("blocked")
    forged = replace(blocked, reviews=(valid_binding,))

    _assert_export_blocked(forged)


def test_export_blocks_forged_approval_for_review_required(dashboard) -> None:
    valid = _approved_session(dashboard)
    valid_binding = valid.current_review
    assert valid_binding is not None
    blocked = SessionReviewRepository({}, dashboard.scenarios).get("blocked")
    blocked_revision = blocked.current
    forged_human = valid_binding.review.model_copy(
        update={"run_id": blocked_revision.draft.run_id}
    )
    forged_binding = SessionReview(
        run_id=blocked_revision.draft.run_id,
        draft_id=blocked_revision.draft.draft_id,
        revision_number=blocked_revision.version,
        approved_draft_sha256="0" * 64,
        approved_final_text_sha256="0" * 64,
        review=forged_human,
    )

    _assert_export_blocked(replace(blocked, reviews=(forged_binding,)))


def test_export_blocks_forged_approval_for_abstain(dashboard) -> None:
    session = _approved_session(dashboard)
    abstain = session.current.assessment.model_copy(
        update={
            "status": "abstain",
            "reason_codes": ("insufficient_trusted_inputs",),
        }
    )
    forged_revision = replace(session.current, assessment=abstain)

    _assert_export_blocked(replace(session, revisions=(forged_revision,)))


def test_correction_creates_new_version_revalidates_and_invalidates_old_review(dashboard) -> None:
    result = dashboard.scenarios["admissible"]
    session = SessionReviewRepository({}, dashboard.scenarios).get("admissible")
    approved = add_human_review(
        session,
        disposition="approved",
        comment="Approval for v1.",
        clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
    )
    corrected = create_corrected_revision(
        approved,
        result,
        summary=result.draft.summary + " Editorial clarification only.",
        claim_templates=tuple(claim.text_template for claim in result.draft.claims),
        comment="Create v2.",
        clock=lambda: datetime(2026, 9, 24, 0, 1, tzinfo=UTC),
    )

    assert len(corrected.revisions) == 2
    assert corrected.current.version == 2
    assert corrected.current.draft.draft_id.endswith("-v02")
    assert corrected.current.validation_report.draft_id == corrected.current.draft.draft_id
    assert corrected.current.assessment.status == "eligible_for_review"
    assert corrected.current_review is None
    assert {review.draft_id for review in corrected.reviews} == {
        corrected.revisions[0].draft.draft_id
    }
    assert decide_export(corrected).allowed is False


def test_blocked_correction_revalidates_and_remains_blocked_when_references_are_unchanged(
    dashboard,
) -> None:
    result = dashboard.scenarios["blocked"]
    session = SessionReviewRepository({}, dashboard.scenarios).get("blocked")
    corrected = create_corrected_revision(
        session,
        result,
        summary=result.draft.summary + " Corrected editorial wording.",
        claim_templates=tuple(claim.text_template for claim in result.draft.claims),
        comment="Correction does not waive findings.",
        clock=lambda: datetime(2026, 9, 24, tzinfo=UTC),
    )

    assert corrected.current.assessment.status == "review_required"
    assert corrected.current.validation_report.issues
    assert corrected.current.rendered_draft.final_text is None
    assert decide_export(corrected).allowed is False


def test_quality_values_are_backed_by_exact_artifacts(dashboard) -> None:
    retrieval_payload = json.loads(
        (PROJECT_ROOT / dashboard.quality.retrieval.source_path).read_text(encoding="utf-8")
    )
    workflow_payload = json.loads(
        (PROJECT_ROOT / dashboard.quality.workflow.source_path).read_text(encoding="utf-8")
    )

    assert dashboard.quality.retrieval.question_count == retrieval_payload["case_type_counts"][
        "total"
    ]
    assert dashboard.quality.retrieval.gold_set_sha256 == retrieval_payload[
        "gold_set_sha256"
    ]
    assert dashboard.quality.workflow.case_count == workflow_payload["case_count"]
    assert dashboard.quality.workflow.dataset_sha256 == workflow_payload["versions"][
        "dataset_sha256"
    ]
    assert dict(dashboard.quality.workflow.confusion_matrix) == workflow_payload[
        "confusion_matrix"
    ]


def test_methodology_links_have_valid_public_shape_and_existing_targets() -> None:
    assert methodology_links_are_backed_by_files()
    assert all(link.url.startswith("https://") for link in METHODOLOGY_LINKS)
    for link in METHODOLOGY_LINKS:
        if link.local_path is not None:
            assert (PROJECT_ROOT / link.local_path).is_file()


def test_dashboard_startup_has_no_network_anthropic_or_postgres(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("External dependency initialized during demo startup")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    import ai_quant.llm.anthropic as anthropic_module

    monkeypatch.setattr(anthropic_module.AnthropicSDKTransport, "__init__", forbidden)

    dashboard = build_analyst_dashboard(Settings.from_env({"APP_MODE": "demo"}))

    assert dashboard.scenarios["admissible"].generation_calls == 1
    assert dashboard.scenarios["blocked"].generation_calls == 1
    source_paths = {path.as_posix() for path in Path("src/ai_quant").rglob("*.py")}
    assert not any("postgres" in path.lower() for path in source_paths)
