"""Strict contract and structured-generation tests for Block 3."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from ai_quant.trust import (
    AutomatedAssessment,
    DraftProposal,
    DraftSchemaError,
    FixtureDraftGenerator,
    GeneratedDraft,
    GenerationBudget,
    GenerationController,
    HumanReview,
    InMemoryTrustWorkflow,
    MetricRecord,
)


def test_valid_fixture_json_matches_closed_schema() -> None:
    proposal, _ = GenerationController(
        FixtureDraftGenerator.valid(), GenerationBudget()
    ).generate(allowed_metric_ids=(), allowed_evidence_ids=())

    assert isinstance(proposal, DraftProposal)
    assert len(proposal.claims) == 2


def test_invalid_json_is_rejected_with_clear_boundary_error(tmp_path) -> None:
    fixture = tmp_path / "invalid.json"
    fixture.write_text("{not-json", encoding="utf-8")
    controller = GenerationController(
        FixtureDraftGenerator(fixture, response_id="response-invalid-v1"),
        GenerationBudget(),
    )

    with pytest.raises(DraftSchemaError, match="failed validation"):
        controller.generate(allowed_metric_ids=(), allowed_evidence_ids=())


def test_unknown_proposal_field_is_forbidden() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DraftProposal.model_validate(
            {
                "summary": "summary",
                "claims": (
                    {
                        "text_template": "A limitation only.",
                        "claim_type": "limitation",
                        "metric_ids": (),
                        "evidence_ids": (),
                    },
                ),
                "limitations": ("Synthetic fixture.",),
                "approval": "approved",
            }
        )


def test_empty_claim_collection_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DraftProposal(
            summary="summary",
            claims=(),
            limitations=("Synthetic fixture.",),
        )


def test_invalid_automated_assessment_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AutomatedAssessment.model_validate(
            {
                "run_id": "run-demo-valid",
                "status": "approved",
                "reason_codes": ("validated_references",),
            }
        )


def test_malformed_metric_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MetricRecord(
            metric_id="NOT VALID",
            run_id="run-demo-valid",
            metric_name="cumulative-return",
            value=0.1,
            unit="decimal return",
            horizon_or_frequency="daily",
            formula_version="formula_v1",
            snapshot_id="snapshot-valid-v1",
        )


def test_generated_draft_cannot_carry_approval() -> None:
    draft_data = InMemoryTrustWorkflow().run("valid").draft.model_dump(mode="json")
    draft_data["approved"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GeneratedDraft.model_validate_json(json.dumps(draft_data))


def test_generated_draft_rejects_claim_from_another_run() -> None:
    draft_data = InMemoryTrustWorkflow().run("valid").draft.model_dump(mode="json")
    draft_data["claims"][0]["run_id"] = "run-demo-foreign"

    with pytest.raises(ValidationError, match="Every claim must belong"):
        GeneratedDraft.model_validate_json(json.dumps(draft_data))


def test_fake_generator_has_no_human_review_capability() -> None:
    fake = FixtureDraftGenerator.valid()
    response = fake.generate(allowed_metric_ids=(), allowed_evidence_ids=())

    assert not hasattr(fake, "create_human_review")
    assert "human_review" not in response.payload_json
    assert "approved" not in response.payload_json


def test_human_review_requires_explicit_utc_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        HumanReview(
            run_id="run-demo-valid",
            reviewer_id="reviewer-demo",
            comment="Explicit review.",
            reviewed_at=datetime(2026, 9, 23),
            disposition="approved",
        )
