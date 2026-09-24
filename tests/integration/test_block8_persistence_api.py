from __future__ import annotations

import os
import socket
import threading
import time
from datetime import UTC, datetime

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from ai_quant.api.app import create_app
from ai_quant.api.service import AnalysisService
from ai_quant.live_dashboard import api_request
from ai_quant.persistence.database import create_session_factory
from ai_quant.persistence.orm import (
    DraftClaimRow,
    EvaluationRunRow,
    GeneratedDraftRow,
    HumanReviewRow,
    ResearchRunRow,
)


def _database_url() -> str:
    url = os.environ.get("BLOCK8_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("BLOCK8_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    markers = (
        "block8_test",
        "block8-test",
        "block8_fix",
        "block8-fix",
        "block8_finalfix",
        "block8-finalfix",
    )
    if not any(marker in url for marker in markers):
        pytest.fail("PostgreSQL integration database must contain a block8 test/fix marker")
    return url


@pytest.fixture()
def session_factory():  # type: ignore[no-untyped-def]
    factory = create_session_factory(_database_url())
    with factory() as session, session.begin():
        session.execute(
            text(
                "TRUNCATE evaluation_runs, model_calls, human_reviews, "
                "automated_assessments, validation_issues, draft_claim_metric_refs, "
                "draft_claim_evidence_refs, draft_claims, "
                "generated_drafts, evidence_records, source_documents, metric_records, "
                "market_snapshots, research_runs CASCADE"
            )
        )
    yield factory
    factory.kw["bind"].dispose()


@pytest.fixture()
def client(session_factory):  # type: ignore[no-untyped-def]
    return TestClient(create_app(AnalysisService(session_factory)), raise_server_exceptions=False)


def _create(client: TestClient, key: str = "postgres-idempotency-0001", scenario: str = "valid"):
    return client.post(
        "/analyses",
        headers={"Idempotency-Key": key},
        json={"scenario": scenario, "data_mode": "frozen_offline_fixture"},
    )


def test_postgres_repositories_persist_complete_run_and_no_duplicates(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    first = _create(client)
    second = _create(client)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()
    run_id = first.json()["analysis_id"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ResearchRunRow)) == 1
        assert session.scalar(select(func.count()).select_from(GeneratedDraftRow)) == 1
        assert session.scalar(select(func.count()).select_from(DraftClaimRow)) >= 1
        row = session.get(ResearchRunRow, run_id)
        assert row is not None and row.data_origin == "frozen_offline_fixture"


def test_same_idempotency_key_with_different_payload_is_409(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    assert _create(client, scenario="valid").status_code == 201
    conflict = _create(client, scenario="blocked")

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ResearchRunRow)) == 1


def test_workflow_failure_rolls_back_atomically(session_factory) -> None:  # type: ignore[no-untyped-def]
    class FailingWorkflow:
        def run(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            raise RuntimeError("private workflow detail")

    service = AnalysisService(session_factory, workflow=FailingWorkflow())  # type: ignore[arg-type]
    failing_client = TestClient(create_app(service), raise_server_exceptions=False)
    response = _create(failing_client, key="postgres-rollback-0001")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error."}
    }
    assert "private workflow detail" not in response.text
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ResearchRunRow)) == 0


def test_reviews_are_append_only_and_wrong_version_or_run_cannot_be_approved(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client).json()
    base = {
        "draft_id": analysis["draft_id"],
        "draft_version": 1,
        "reviewer": "entered reviewer",
        "disposition": "approved",
        "comment": "Explicit local approval.",
    }
    first = client.post(f"/analyses/{analysis['analysis_id']}/reviews", json=base)
    second = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json={**base, "comment": "Second independent row."},
    )
    wrong_version = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json={**base, "draft_version": 2},
    )
    wrong_run = client.post("/analyses/run-local-missing/reviews", json=base)

    assert first.status_code == second.status_code == 201
    assert first.json()["review_id"] != second.json()["review_id"]
    assert wrong_version.status_code == 409
    assert wrong_run.status_code == 404
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(HumanReviewRow)) == 2


def test_correction_creates_v2_without_overwriting_v1_and_old_version_cannot_approve(
    client: TestClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    analysis = _create(client).json()
    with session_factory() as session:
        claim_count = session.scalar(select(func.count()).select_from(DraftClaimRow))
    correction = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json={
            "draft_id": analysis["draft_id"],
            "draft_version": 1,
            "reviewer": "entered reviewer",
            "disposition": "corrected",
            "comment": "Creates a new historical version.",
            "corrected_summary": "Human correction awaiting deterministic revalidation.",
            "corrected_claims": [f"Corrected claim {index}." for index in range(claim_count)],
        },
    )

    assert correction.status_code == 201
    assert correction.json()["resulting_draft_version"] == 2
    current = client.get(f"/analyses/{analysis['analysis_id']}").json()
    assert current["draft_version"] == 2
    assert current["automated_status"] == "review_required"
    old_approval = client.post(
        f"/analyses/{analysis['analysis_id']}/reviews",
        json={
            "draft_id": analysis["draft_id"],
            "draft_version": 1,
            "reviewer": "entered reviewer",
            "disposition": "approved",
            "comment": "Must not approve stale content.",
        },
    )
    assert old_approval.status_code == 409
    with session_factory() as session:
        versions = list(
            session.scalars(
                select(GeneratedDraftRow.version)
                .where(GeneratedDraftRow.run_id == analysis["analysis_id"])
                .order_by(GeneratedDraftRow.version)
            )
        )
        assert versions == [1, 2]


def test_database_constraints_reject_duplicate_business_version(session_factory) -> None:  # type: ignore[no-untyped-def]
    service = AnalysisService(session_factory)
    response, _ = service.create_analysis(
        __import__("ai_quant.api.schemas", fromlist=["AnalysisCreate"]).AnalysisCreate(
            scenario="valid"
        ),
        "postgres-constraint-0001",
    )
    with session_factory() as session:
        original = session.scalar(
            select(GeneratedDraftRow).where(GeneratedDraftRow.run_id == response.analysis_id)
        )
        assert original is not None
        duplicate = GeneratedDraftRow(
            draft_id=f"{original.draft_id}-duplicate",
            run_id=original.run_id,
            version=original.version,
            summary=original.summary,
            limitations=original.limitations,
            generation_payload=original.generation_payload,
            created_at=datetime.now(UTC),
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()


def test_evaluation_latest_and_all_read_endpoints(client: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    created = _create(client)
    run_id = created.json()["analysis_id"]
    assert client.get(f"/analyses/{run_id}").status_code == 200
    assert client.get(f"/analyses/{run_id}/evidence").json()
    seeded = client.get("/evaluations/latest")
    assert seeded.status_code == 200
    assert seeded.json()["schema_version"] == "workflow-evaluation-report.v2"
    with session_factory() as session, session.begin():
        session.add(
            EvaluationRunRow(
                evaluation_id="evaluation-block8-test",
                schema_version="workflow-evaluation-report.v2",
                dataset_sha256="2" * 64,
                case_count=27,
                report_payload={"scope": "versioned fixture only"},
                created_at=datetime.now(UTC),
            )
        )
    latest = client.get("/evaluations/latest")
    assert latest.status_code == 200
    assert latest.json()["evaluation_id"] == "evaluation-block8-test"
    assert client.get("/health").status_code == 200


def test_streamlit_api_adapter_reaches_fastapi_and_postgres(session_factory) -> None:  # type: ignore[no-untyped-def]
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = uvicorn.Config(
        create_app(AnalysisService(session_factory)),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    try:
        response = api_request(
            f"http://127.0.0.1:{port}",
            "POST",
            "/analyses",
            payload={"scenario": "valid", "data_mode": "frozen_offline_fixture"},
            headers={"Idempotency-Key": "streamlit-postgres-smoke-0001"},
        )
        assert isinstance(response, dict)
        with session_factory() as session:
            assert session.get(ResearchRunRow, response["analysis_id"]) is not None
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert not thread.is_alive()
