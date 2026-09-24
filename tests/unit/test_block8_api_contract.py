from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ai_quant.api.app import create_app
from ai_quant.api.schemas import (
    AnalysisResponse,
    EvaluationResponse,
    EvidenceResponse,
    ReviewResponse,
)
from ai_quant.api.service import BusinessConflict, ResourceNotFound


class StubService:
    def __init__(self) -> None:
        self.created = False

    def create_analysis(self, request, idempotency_key):  # type: ignore[no-untyped-def]
        assert idempotency_key == "local-key-0001"
        response = AnalysisResponse(
            analysis_id="run-local-contract",
            state="pending_review",
            scenario=request.scenario,
            data_origin="frozen_offline_fixture",
            draft_id="draft-run-local-contract",
            draft_version=1,
            summary="Fixture summary.",
            claims=("Fixture claim.",),
            claim_references=(),
            automated_status="eligible_for_review",
            reliable=True,
            final_text="Validated fixture text.",
            findings=(),
            created_at=datetime(2026, 9, 24, tzinfo=UTC),
        )
        was_created = not self.created
        self.created = True
        return response, was_created

    def get_analysis(self, run_id):  # type: ignore[no-untyped-def]
        if run_id == "missing":
            raise ResourceNotFound("analysis not found")
        return self.create_analysis(
            type("Request", (), {"scenario": "valid"})(), "local-key-0001"
        )[0]

    def get_evidence(self, run_id):  # type: ignore[no-untyped-def]
        if run_id == "missing":
            raise ResourceNotFound("analysis not found")
        return (
            EvidenceResponse(
                evidence_id="evidence-run-local-contract-one",
                document_id="document-contract",
                document_sha256="0" * 64,
                status="synthetic_demo_evidence",
                payload={"label": "offline"},
            ),
        )

    def create_review(self, run_id, request):  # type: ignore[no-untyped-def]
        if request.draft_version != 1:
            raise BusinessConflict("review does not target the current draft version")
        return ReviewResponse(
            review_id="review-contract",
            analysis_id=run_id,
            draft_id=request.draft_id,
            draft_version=request.draft_version,
            reviewer_entered=request.reviewer,
            reviewer_identity="entered_unverified_unauthenticated",
            disposition=request.disposition,
            comment=request.comment,
            reviewed_at=datetime(2026, 9, 24, tzinfo=UTC),
        )

    def latest_evaluation(self):  # type: ignore[no-untyped-def]
        return EvaluationResponse(
            evaluation_id="evaluation-contract",
            schema_version="workflow-evaluation-report.v2",
            dataset_sha256="1" * 64,
            case_count=27,
            report={"scope": "versioned fixture only"},
            created_at=datetime(2026, 9, 24, tzinfo=UTC),
        )

    def health(self) -> None:
        return None


def _client() -> TestClient:
    return TestClient(create_app(StubService()))  # type: ignore[arg-type]


def test_all_six_fastapi_endpoints_and_statuses() -> None:
    client = _client()
    payload = {"scenario": "valid", "data_mode": "frozen_offline_fixture"}
    headers = {"Idempotency-Key": "local-key-0001"}

    assert client.post("/analyses", json=payload, headers=headers).status_code == 201
    assert client.post("/analyses", json=payload, headers=headers).status_code == 200
    assert client.get("/analyses/run-local-contract").status_code == 200
    assert client.get("/analyses/run-local-contract/evidence").status_code == 200
    review = client.post(
        "/analyses/run-local-contract/reviews",
        json={
            "draft_id": "draft-run-local-contract",
            "draft_version": 1,
            "reviewer": "entered reviewer",
            "disposition": "approved",
            "comment": "Explicit test decision.",
        },
    )
    assert review.status_code == 201
    assert review.json()["reviewer_identity"] == "entered_unverified_unauthenticated"
    assert client.get("/evaluations/latest").status_code == 200
    assert client.get("/health").json() == {"status": "ok", "database": "reachable"}


def test_public_errors_are_stable_and_sanitized() -> None:
    client = _client()
    missing = client.get("/analyses/missing")
    invalid = client.post("/analyses", json={"scenario": "other"})
    conflict = client.post(
        "/analyses/run-local-contract/reviews",
        json={
            "draft_id": "draft-run-local-contract",
            "draft_version": 9,
            "reviewer": "entered reviewer",
            "disposition": "approved",
            "comment": "Wrong version.",
        },
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert conflict.status_code == 409
    for response in (missing, invalid, conflict):
        assert set(response.json()) == {"error"}
        rendered = response.text.lower()
        assert "traceback" not in rendered
        assert "select " not in rendered
        assert "database_url" not in rendered


def test_openapi_exposes_no_orm_or_internal_error_model() -> None:
    schema = _client().get("/openapi.json").json()
    names = set(schema["components"]["schemas"])

    assert not any(name.endswith("Row") for name in names)
    assert "ResearchRunRow" not in names


def test_openapi_exposes_closed_business_vocabularies() -> None:
    schemas = _client().get("/openapi.json").json()["components"]["schemas"]

    analysis = schemas["AnalysisResponse"]["properties"]
    assert set(analysis["state"]["enum"]) == {
        "created",
        "generated",
        "validated",
        "pending_review",
        "finalized",
    }
    assert set(analysis["automated_status"]["enum"]) == {
        "eligible_for_review",
        "review_required",
        "abstain",
    }
    assert analysis["data_origin"]["const"] == "frozen_offline_fixture"
    finding = schemas["FindingResponse"]["properties"]
    assert "cross_run_reference" in finding["code"]["enum"]
    assert set(finding["severity"]["enum"]) == {
        "info",
        "warning",
        "error",
        "critical",
    }
    assert set(schemas["EvidenceResponse"]["properties"]["status"]["enum"]) == {
        "synthetic_demo_evidence",
        "official_corpus_passage",
    }
    assert set(schemas["ReviewResponse"]["properties"]["disposition"]["enum"]) == {
        "approved",
        "corrected",
        "rejected",
        "escalated",
    }
    assert set(schemas["ErrorBody"]["properties"]["code"]["enum"]) == {
        "invalid_request",
        "not_found",
        "conflict",
        "correction_unrepresentable",
        "persistence_conflict",
        "internal_error",
    }
