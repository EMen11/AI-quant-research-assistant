from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from ai_quant.api.app import create_app
from ai_quant.api.schemas import DataOrigin
from ai_quant.api.service import AnalysisService
from ai_quant.model_calls import ModelCallStatus, ModelResponseOrigin
from ai_quant.persistence.database import create_session_factory
from ai_quant.persistence.orm import (
    AutomatedAssessmentRow,
    DraftClaimEvidenceRefRow,
    DraftClaimMetricRefRow,
    DraftClaimRow,
    EvidenceRecordRow,
    GeneratedDraftRow,
    HumanReviewRow,
    MetricRecordRow,
    ModelCallRow,
    SourceDocumentRow,
    ValidationIssueRow,
)
from ai_quant.persistence.repositories import AnalysisRepositories, ArtifactRepository
from ai_quant.trust.models import (
    AssessmentReason,
    AssessmentStatus,
    ClaimType,
    EvidenceStatus,
    HumanDisposition,
    IssueCode,
    IssueSeverity,
    RunState,
)
from ai_quant.trust.workflow import DemoScenario


def _database_url() -> str:
    url = os.environ.get("BLOCK8_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("BLOCK8_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    if not any(
        marker in url
        for marker in ("block8_fix", "block8-fix", "block8_finalfix", "block8-finalfix")
    ):
        pytest.fail("review-fix tests require a dedicated block8 fix database")
    return url


@pytest.fixture()
def session_factory():  # type: ignore[no-untyped-def]
    factory = create_session_factory(_database_url())
    with factory() as session, session.begin():
        session.execute(
            text(
                "TRUNCATE evaluation_runs, model_calls, human_reviews, "
                "automated_assessments, validation_issues, draft_claim_metric_refs, "
                "draft_claim_evidence_refs, draft_claims, generated_drafts, "
                "evidence_records, source_documents, metric_records, market_snapshots, "
                "research_runs CASCADE"
            )
        )
    yield factory
    factory.kw["bind"].dispose()


@pytest.fixture()
def client(session_factory):  # type: ignore[no-untyped-def]
    return TestClient(create_app(AnalysisService(session_factory)), raise_server_exceptions=False)


def _create(client: TestClient, key: str, scenario: str = "valid") -> dict[str, object]:
    response = client.post(
        "/analyses",
        headers={"Idempotency-Key": key},
        json={"scenario": scenario, "data_mode": "frozen_offline_fixture"},
    )
    assert response.status_code == 201
    return response.json()


def _correction_payload(analysis: dict[str, object]) -> dict[str, object]:
    return {
        "draft_id": analysis["draft_id"],
        "draft_version": analysis["draft_version"],
        "reviewer": "entered reviewer",
        "disposition": "corrected",
        "comment": "Deterministic correction.",
        "corrected_summary": analysis["summary"],
        "corrected_claims": analysis["claims"],
    }


def test_relational_claim_references_enforce_same_run_unknowns_and_order(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    run_a = _create(client, "block8-fix-reference-a-0001")
    run_b = _create(client, "block8-fix-reference-b-0001")
    with session_factory() as session:
        metrics_a = list(
            session.scalars(
                select(MetricRecordRow.metric_id)
                .where(MetricRecordRow.run_id == run_a["analysis_id"])
                .order_by(MetricRecordRow.metric_id)
                .limit(2)
            )
        )
        metric_b = session.scalar(
            select(MetricRecordRow.metric_id)
            .where(MetricRecordRow.run_id == run_b["analysis_id"])
            .limit(1)
        )
        evidence_a = session.scalar(
            select(EvidenceRecordRow.evidence_id)
            .where(EvidenceRecordRow.run_id == run_a["analysis_id"])
            .limit(1)
        )
        evidence_b = session.scalar(
            select(EvidenceRecordRow.evidence_id)
            .where(EvidenceRecordRow.run_id == run_b["analysis_id"])
            .limit(1)
        )
    assert len(metrics_a) == 2 and metric_b and evidence_a and evidence_b
    claim_id = f"claim-{run_a['analysis_id']}-ordered-refs"
    with session_factory() as session, session.begin():
        session.add(
            DraftClaimRow(
                claim_id=claim_id,
                run_id=run_a["analysis_id"],
                draft_id=run_a["draft_id"],
                position=99,
                claim_type="limitation",
                text_template="Ordered same-run references.",
                declared_metric_ids=[metrics_a[1], metrics_a[0]],
                declared_evidence_ids=[evidence_a],
                uncertainty=None,
            )
        )
        session.flush()
        session.add_all(
            (
                DraftClaimMetricRefRow(
                    run_id=run_a["analysis_id"],
                    draft_id=run_a["draft_id"],
                    claim_id=claim_id,
                    metric_id=metrics_a[0],
                    position=2,
                ),
                DraftClaimMetricRefRow(
                    run_id=run_a["analysis_id"],
                    draft_id=run_a["draft_id"],
                    claim_id=claim_id,
                    metric_id=metrics_a[1],
                    position=1,
                ),
                DraftClaimEvidenceRefRow(
                    run_id=run_a["analysis_id"],
                    draft_id=run_a["draft_id"],
                    claim_id=claim_id,
                    evidence_id=evidence_a,
                    position=1,
                ),
            )
        )

    with session_factory() as session:
        reconstructed = next(
            claim
            for claim in AnalysisRepositories.for_session(session).artifacts.domain_claims(
                str(run_a["draft_id"])
            )
            if claim.claim_id == claim_id
        )
        assert reconstructed.metric_ids == (metrics_a[1], metrics_a[0])
        assert reconstructed.evidence_ids == (evidence_a,)

    invalid_rows = (
        DraftClaimMetricRefRow(
            run_id=run_a["analysis_id"],
            draft_id=run_a["draft_id"],
            claim_id=claim_id,
            metric_id=metric_b,
            position=3,
        ),
        DraftClaimEvidenceRefRow(
            run_id=run_a["analysis_id"],
            draft_id=run_a["draft_id"],
            claim_id=claim_id,
            evidence_id=evidence_b,
            position=2,
        ),
        DraftClaimMetricRefRow(
            run_id=run_a["analysis_id"],
            draft_id=run_a["draft_id"],
            claim_id=claim_id,
            metric_id="metric-unknown-reference",
            position=4,
        ),
        DraftClaimEvidenceRefRow(
            run_id=run_a["analysis_id"],
            draft_id=run_a["draft_id"],
            claim_id=claim_id,
            evidence_id="evidence-unknown-reference",
            position=3,
        ),
    )
    for row in invalid_rows:
        with session_factory() as session:
            session.add(row)
            with pytest.raises(IntegrityError):
                session.commit()


def test_two_concurrent_corrections_yield_201_and_409_without_partial_state(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    app = create_app(AnalysisService(session_factory))
    with TestClient(app, raise_server_exceptions=False) as setup_client:
        analysis = _create(setup_client, "block8-fix-concurrency-0001")
    payload = _correction_payload(analysis)

    def correct() -> tuple[int, dict[str, object]]:
        with TestClient(app, raise_server_exceptions=False) as request_client:
            response = request_client.post(
                f"/analyses/{analysis['analysis_id']}/reviews", json=payload
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: correct(), range(2)))

    assert sorted(status for status, _ in results) == [201, 409]
    conflict = next(body for status, body in results if status == 409)
    assert conflict == {
        "error": {
            "code": "conflict",
            "message": "review does not target the current draft version",
        }
    }
    assert "sql" not in json.dumps(conflict).lower()
    assert "traceback" not in json.dumps(conflict).lower()
    with session_factory() as session:
        versions = list(
            session.scalars(
                select(GeneratedDraftRow.version)
                .where(GeneratedDraftRow.run_id == analysis["analysis_id"])
                .order_by(GeneratedDraftRow.version)
            )
        )
        reviews = list(
            session.scalars(
                select(HumanReviewRow).where(
                    HumanReviewRow.run_id == analysis["analysis_id"]
                )
            )
        )
        assert versions == [1, 2]
        assert len(reviews) == 1
        assert reviews[0].draft_version == 1
        assert reviews[0].disposition == "corrected"

    with TestClient(app, raise_server_exceptions=False) as verification_client:
        current = verification_client.get(
            f"/analyses/{analysis['analysis_id']}"
        ).json()
        assert current["draft_version"] == 2
        assert current["automated_status"] == "eligible_for_review"
        assert current["findings"] == []
        with session_factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(HumanReviewRow)
                    .where(
                        HumanReviewRow.run_id == analysis["analysis_id"],
                        HumanReviewRow.draft_version == 2,
                        HumanReviewRow.disposition == "approved",
                    )
                )
                == 0
            )
        approval = verification_client.post(
            f"/analyses/{analysis['analysis_id']}/reviews",
            json={
                "draft_id": current["draft_id"],
                "draft_version": 2,
                "reviewer": "entered approver",
                "disposition": "approved",
                "comment": "Explicit approval of v2 only.",
            },
        )
        assert approval.status_code == 201


def test_invalid_correction_is_revalidated_and_cannot_be_approved(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client, "block8-fix-invalid-correction-0001")
    with session_factory() as session:
        claims = AnalysisRepositories.for_session(session).artifacts.domain_claims(
            str(analysis["draft_id"])
        )
    invalid_claims = list(analysis["claims"])
    quantitative_index = next(
        index for index, claim in enumerate(claims) if claim.claim_type == "quantitative"
    )
    invalid_claims[quantitative_index] += " Unsupported value 123."
    payload = _correction_payload(analysis)
    payload["corrected_claims"] = invalid_claims
    correction = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews", json=payload
    )

    assert correction.status_code == 201
    current = client.get(f"/analyses/{analysis['analysis_id']}").json()
    repeated = client.get(f"/analyses/{analysis['analysis_id']}").json()
    assert current == repeated
    assert current["draft_version"] == 2
    assert current["automated_status"] == "review_required"
    assert current["reliable"] is False
    assert "free_numeric_literal" in {item["code"] for item in current["findings"]}
    approval = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json={
            "draft_id": current["draft_id"],
            "draft_version": 2,
            "reviewer": "entered approver",
            "disposition": "approved",
            "comment": "Must remain blocked.",
        },
    )
    assert approval.status_code == 409


def test_correction_validation_failure_rolls_back_every_related_row(
    client: TestClient, session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client, "block8-fix-correction-rollback-0001")
    table_types = (
        GeneratedDraftRow,
        DraftClaimRow,
        DraftClaimMetricRefRow,
        DraftClaimEvidenceRefRow,
        ValidationIssueRow,
        AutomatedAssessmentRow,
        HumanReviewRow,
    )
    with session_factory() as session:
        before = {
            table.__tablename__: session.scalar(select(func.count()).select_from(table))
            for table in table_types
        }

    def fail_validation(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("private deterministic validator detail")

    monkeypatch.setattr(
        "ai_quant.persistence.repositories.validate_draft", fail_validation
    )
    response = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json=_correction_payload(analysis),
    )
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error."}
    }
    assert "private deterministic validator detail" not in response.text
    with session_factory() as session:
        after = {
            table.__tablename__: session.scalar(select(func.count()).select_from(table))
            for table in table_types
        }
    assert after == before


SqlVocabulary = tuple[str, str, str, tuple[str, ...]]


def _sql_vocabularies(ids: dict[str, str]) -> tuple[SqlVocabulary, ...]:
    return (
        ("research_runs.scenario", "research_runs", "scenario", get_args(DemoScenario)),
        ("research_runs.state", "research_runs", "state", get_args(RunState)),
        ("research_runs.data_origin", "research_runs", "data_origin", get_args(DataOrigin)),
        (
            "source_documents.source_kind",
            "source_documents",
            "source_kind",
            get_args(EvidenceStatus),
        ),
        ("evidence_records.status", "evidence_records", "status", get_args(EvidenceStatus)),
        ("draft_claims.claim_type", "draft_claims", "claim_type", get_args(ClaimType)),
        ("validation_issues.code", "validation_issues", "code", get_args(IssueCode)),
        (
            "validation_issues.severity",
            "validation_issues",
            "severity",
            get_args(IssueSeverity),
        ),
        (
            "human_reviews.disposition",
            "human_reviews",
            "disposition",
            get_args(HumanDisposition),
        ),
        ("model_calls.status", "model_calls", "status", get_args(ModelCallStatus)),
        (
            "model_calls.response_origin",
            "model_calls",
            "response_origin",
            get_args(ModelResponseOrigin),
        ),
    )


def test_all_closed_sql_vocabularies_accept_domain_values_and_reject_invalids(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    valid = _create(client, "block8-fix-vocabulary-valid-0001")
    blocked = _create(client, "block8-fix-vocabulary-blocked-0001", scenario="blocked")
    approval = client.post(
        f"/analyses/{valid['analysis_id']}/reviews",
        json={
            "draft_id": valid["draft_id"],
            "draft_version": 1,
            "reviewer": "entered reviewer",
            "disposition": "approved",
            "comment": "Create a constrained review row.",
        },
    )
    assert approval.status_code == 201
    with session_factory() as session:
        ids = {
            "research_runs": str(valid["analysis_id"]),
            "source_documents": session.scalar(select(SourceDocumentRow.document_id)),
            "evidence_records": session.scalar(
                select(EvidenceRecordRow.evidence_id).where(
                    EvidenceRecordRow.run_id == valid["analysis_id"]
                )
            ),
            "draft_claims": session.scalar(
                select(DraftClaimRow.claim_id).where(
                    DraftClaimRow.run_id == valid["analysis_id"]
                )
            ),
            "validation_issues": session.scalar(
                select(ValidationIssueRow.issue_id).where(
                    ValidationIssueRow.run_id == blocked["analysis_id"]
                )
            ),
            "automated_assessments": session.scalar(
                select(AutomatedAssessmentRow.assessment_id).where(
                    AutomatedAssessmentRow.run_id == valid["analysis_id"]
                )
            ),
            "human_reviews": approval.json()["review_id"],
            "model_calls": session.scalar(
                select(ModelCallRow.call_id).where(
                    ModelCallRow.run_id == valid["analysis_id"]
                )
            ),
        }
    assert all(ids.values())

    id_columns = {
        "research_runs": "run_id",
        "source_documents": "document_id",
        "evidence_records": "evidence_id",
        "draft_claims": "claim_id",
        "validation_issues": "issue_id",
        "automated_assessments": "assessment_id",
        "human_reviews": "review_id",
        "model_calls": "call_id",
    }
    vocabularies = _sql_vocabularies(ids)
    with session_factory() as session:
        for _label, table, column, values in vocabularies:
            for value in values:
                session.execute(
                    text(
                        f"UPDATE {table} SET {column} = :value "  # noqa: S608
                        f"WHERE {id_columns[table]} = :row_id"
                    ),
                    {"value": value, "row_id": ids[table]},
                )
        session.rollback()

    invalid_checks: list[tuple[str, str, str]] = [
        (table, column, id_columns[table]) for _, table, column, _ in vocabularies
    ]
    for table, column, id_column in invalid_checks:
        with session_factory() as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    text(
                        f"UPDATE {table} SET {column} = 'invalid-value' "  # noqa: S608
                        f"WHERE {id_column} = :row_id"
                    ),
                    {"row_id": ids[table]},
                )
                session.commit()
def test_metadata_contains_exact_minimum_and_association_tables() -> None:
    from ai_quant.persistence.orm import Base

    minimum = {
        "research_runs",
        "market_snapshots",
        "metric_records",
        "source_documents",
        "evidence_records",
        "generated_drafts",
        "draft_claims",
        "validation_issues",
        "automated_assessments",
        "human_reviews",
        "model_calls",
        "evaluation_runs",
    }
    assert minimum <= set(Base.metadata.tables)
    assert {
        "draft_claim_metric_refs",
        "draft_claim_evidence_refs",
    } <= set(Base.metadata.tables)
    assert {
        constraint.name
        for constraint in Base.metadata.tables["automated_assessments"].constraints
    } >= {"ck_assessment_status_reason_exact"}
    assert {
        constraint.name for constraint in Base.metadata.tables["draft_claims"].constraints
    } >= {
        "ck_claim_declared_metric_ids_string_array",
        "ck_claim_declared_evidence_ids_string_array",
    }


def test_blocked_correction_without_replacements_preserves_declared_audit(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client, "block8-finalfix-blocked-preserve-0001", scenario="blocked")
    fetched_v1 = client.get(f"/analyses/{analysis['analysis_id']}")
    assert fetched_v1.status_code == 200
    audit_v1 = fetched_v1.json()["claim_references"]
    assert audit_v1
    assert all(item["reference_status"] == "declared_untrusted" for item in audit_v1)
    assert any(item["declared_metric_ids"] for item in audit_v1)
    assert any(item["declared_evidence_ids"] for item in audit_v1)
    assert all(not item["accepted_metric_ids"] for item in audit_v1)
    assert all(not item["accepted_evidence_ids"] for item in audit_v1)

    with session_factory() as session:
        before = tuple(
            (
                row.claim_id,
                row.text_template,
                tuple(row.declared_metric_ids),
                tuple(row.declared_evidence_ids),
            )
            for row in session.scalars(
                select(DraftClaimRow)
                .where(DraftClaimRow.draft_id == analysis["draft_id"])
                .order_by(DraftClaimRow.position)
            )
        )

    correction = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json=_correction_payload(analysis),
    )
    assert correction.status_code == 201
    assert correction.json()["resulting_draft_version"] == 2
    current = client.get(f"/analyses/{analysis['analysis_id']}").json()
    assert current["draft_version"] == 2
    assert current["automated_status"] == "review_required"
    assert current["reliable"] is False
    assert {item["code"] for item in current["findings"]} == {
        "cross_run_reference",
        "free_numeric_literal",
    }
    assert all(
        item["reference_status"] == "declared_untrusted"
        for item in current["claim_references"]
    )

    with session_factory() as session:
        after = tuple(
            (
                row.claim_id,
                row.text_template,
                tuple(row.declared_metric_ids),
                tuple(row.declared_evidence_ids),
            )
            for row in session.scalars(
                select(DraftClaimRow)
                .where(DraftClaimRow.draft_id == analysis["draft_id"])
                .order_by(DraftClaimRow.position)
            )
        )
        assert after == before
        resulting_id = correction.json()["resulting_draft_id"]
        assert session.scalar(
            select(func.count())
            .select_from(DraftClaimMetricRefRow)
            .where(DraftClaimMetricRefRow.draft_id == resulting_id)
        ) == 0
        assert session.scalar(
            select(func.count())
            .select_from(DraftClaimEvidenceRefRow)
            .where(DraftClaimEvidenceRefRow.draft_id == resulting_id)
        ) == 0


def test_blocked_correction_with_same_run_replacements_is_eligible_not_approved(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client, "block8-finalfix-blocked-replace-0001", scenario="blocked")
    with session_factory() as session:
        metric_id = session.scalar(
            select(MetricRecordRow.metric_id)
            .where(MetricRecordRow.run_id == analysis["analysis_id"])
            .order_by(MetricRecordRow.metric_id)
        )
        evidence_id = session.scalar(
            select(EvidenceRecordRow.evidence_id)
            .where(EvidenceRecordRow.run_id == analysis["analysis_id"])
            .order_by(EvidenceRecordRow.evidence_id)
        )
        claim_types = tuple(
            session.scalars(
                select(DraftClaimRow.claim_type)
                .where(DraftClaimRow.draft_id == analysis["draft_id"])
                .order_by(DraftClaimRow.position)
            )
        )
    assert metric_id and evidence_id
    corrected_claims: list[str] = []
    corrected_references: list[dict[str, list[str]]] = []
    for claim_type in claim_types:
        if claim_type == "quantitative":
            corrected_claims.append(f"The server-owned return is {{{{metric:{metric_id}}}}}.")
            corrected_references.append(
                {"declared_metric_ids": [metric_id], "declared_evidence_ids": []}
            )
        elif claim_type == "evidence":
            corrected_claims.append(
                f"Methodology is supported by {{{{evidence:{evidence_id}}}}}."
            )
            corrected_references.append(
                {"declared_metric_ids": [], "declared_evidence_ids": [evidence_id]}
            )
        else:
            corrected_claims.append("A limitation remains explicitly documented.")
            corrected_references.append(
                {"declared_metric_ids": [], "declared_evidence_ids": []}
            )

    payload = _correction_payload(analysis)
    payload["corrected_claims"] = corrected_claims
    payload["corrected_references"] = corrected_references
    correction = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews", json=payload
    )
    assert correction.status_code == 201
    current = client.get(f"/analyses/{analysis['analysis_id']}").json()
    assert current["draft_version"] == 2
    assert current["automated_status"] == "eligible_for_review"
    assert current["findings"] == []
    assert all(
        item["reference_status"] == "accepted"
        and item["declared_metric_ids"] == item["accepted_metric_ids"]
        and item["declared_evidence_ids"] == item["accepted_evidence_ids"]
        for item in current["claim_references"]
    )
    with session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(HumanReviewRow)
            .where(
                HumanReviewRow.run_id == analysis["analysis_id"],
                HumanReviewRow.draft_version == 2,
                HumanReviewRow.disposition == "approved",
            )
        ) == 0


def test_unrepresentable_reference_replacement_is_closed_public_conflict(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client, "block8-finalfix-unrepresentable-0001", scenario="blocked")
    payload = _correction_payload(analysis)
    payload["corrected_references"] = []
    response = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews", json=payload
    )
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "correction_unrepresentable",
            "message": "corrected_references must contain exactly one entry per claim",
        }
    }
    with session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(GeneratedDraftRow)
            .where(GeneratedDraftRow.run_id == analysis["analysis_id"])
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(HumanReviewRow)
            .where(HumanReviewRow.run_id == analysis["analysis_id"])
        ) == 0


def test_declared_reference_json_is_string_array_and_empty_is_allowed(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client, "block8-finalfix-declared-json-0001")
    with session_factory() as session:
        claim_id = session.scalar(
            select(DraftClaimRow.claim_id)
            .where(DraftClaimRow.run_id == analysis["analysis_id"])
            .order_by(DraftClaimRow.position)
        )
    assert claim_id
    with session_factory() as session:
        session.execute(
            text(
                "UPDATE draft_claims SET declared_metric_ids = '[]'::jsonb, "
                "declared_evidence_ids = '[]'::jsonb WHERE claim_id = :claim_id"
            ),
            {"claim_id": claim_id},
        )
        session.commit()
    for invalid in ("{}", '["valid", 1]'):
        with session_factory() as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    text(
                        "UPDATE draft_claims SET declared_metric_ids = CAST(:value AS jsonb) "
                        "WHERE claim_id = :claim_id"
                    ),
                    {"value": invalid, "claim_id": claim_id},
                )
                session.commit()


def test_assessment_status_reason_exact_pairs_and_defense_in_depth(
    client: TestClient, session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client, "block8-finalfix-assessment-pairs-0001")
    with session_factory() as session:
        assessment_id = session.scalar(
            select(AutomatedAssessmentRow.assessment_id).where(
                AutomatedAssessmentRow.run_id == analysis["analysis_id"]
            )
        )
    assert assessment_id
    exact_pairs = {
        "eligible_for_review": "validated_references",
        "review_required": "blocking_validation_issues",
        "abstain": "insufficient_trusted_inputs",
    }
    for status in get_args(AssessmentStatus):
        for reason in get_args(AssessmentReason):
            with session_factory() as session:
                if exact_pairs[status] == reason:
                    session.execute(
                        text(
                            "UPDATE automated_assessments SET status = :status, "
                            "reason_codes = CAST(:reasons AS jsonb) "
                            "WHERE assessment_id = :assessment_id"
                        ),
                        {
                            "status": status,
                            "reasons": json.dumps([reason]),
                            "assessment_id": assessment_id,
                        },
                    )
                    session.commit()
                else:
                    with pytest.raises(IntegrityError):
                        session.execute(
                            text(
                                "UPDATE automated_assessments SET status = :status, "
                                "reason_codes = CAST(:reasons AS jsonb) "
                                "WHERE assessment_id = :assessment_id"
                            ),
                            {
                                "status": status,
                                "reasons": json.dumps([reason]),
                                "assessment_id": assessment_id,
                            },
                        )
                        session.commit()
    for reasons in ([], ["validated_references", "blocking_validation_issues"], ["unknown"]):
        with session_factory() as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    text(
                        "UPDATE automated_assessments SET status = 'eligible_for_review', "
                        "reason_codes = CAST(:reasons AS jsonb) "
                        "WHERE assessment_id = :assessment_id"
                    ),
                    {"reasons": json.dumps(reasons), "assessment_id": assessment_id},
                )
                session.commit()

    monkeypatch.setattr(
        ArtifactRepository,
        "assessment",
        lambda _repository, _draft_id: SimpleNamespace(
            run_id=analysis["analysis_id"],
            status="eligible_for_review",
            reason_codes=["blocking_validation_issues"],
        ),
    )
    approval = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json={
            "draft_id": analysis["draft_id"],
            "draft_version": 1,
            "reviewer": "entered reviewer",
            "disposition": "approved",
            "comment": "An incoherent assessment must never authorize this.",
        },
    )
    assert approval.status_code == 409
    assert approval.json() == {
        "error": {
            "code": "persistence_conflict",
            "message": "Persistent state conflict.",
        }
    }
