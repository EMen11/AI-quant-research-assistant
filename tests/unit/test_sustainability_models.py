"""Closed-contract tests for the Block 4 sustainability corpus."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ai_quant.sustainability import (
    AssuranceAssessment,
    ClimateTarget,
    SustainabilityObservation,
    convert_value,
    documents_at_cutoff,
    load_assurance_assessments,
    load_comparison_assessments,
    load_manifest,
    load_observations,
    load_targets,
    units_compatible,
)


def _observation_payload(observation_id: str) -> dict[str, object]:
    observation = next(
        item for item in load_observations() if item.observation_id == observation_id
    )
    return observation.model_dump()


def test_sustainability_observation_schema_is_closed() -> None:
    payload = _observation_payload("observation-bachem-2025-scope-one")
    payload["llm_confidence"] = Decimal("0.99")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SustainabilityObservation.model_validate(payload)


def test_reported_zero_is_distinct_from_not_found() -> None:
    zero = next(
        item
        for item in load_observations()
        if item.observation_id == "observation-bachem-2025-renewable-fuel"
    )
    missing_payload = zero.model_dump()
    missing_payload.update(coverage_status="not_found", value=None, unit=None)
    missing = SustainabilityObservation.model_validate(missing_payload)

    assert zero.coverage_status == "reported_zero"
    assert zero.value == Decimal("0")
    assert missing.coverage_status == "not_found"
    assert missing.value is None


def test_reported_zero_rejects_a_missing_value() -> None:
    payload = _observation_payload("observation-bachem-2025-renewable-fuel")
    payload["value"] = None

    with pytest.raises(ValidationError, match="reported_zero"):
        SustainabilityObservation.model_validate(payload)


def test_scope_two_methods_are_explicit_and_distinct() -> None:
    observations = load_observations()
    location = next(
        item
        for item in observations
        if item.observation_id == "observation-bachem-2025-scope-two-location"
    )
    market = next(
        item
        for item in observations
        if item.observation_id == "observation-bachem-2025-scope-two-market"
    )

    assert location.scope_2_method == "location_based"
    assert market.scope_2_method == "market_based"
    assert location.scope_2_method != market.scope_2_method


def test_actual_observation_and_target_are_separate_contracts() -> None:
    observation = load_observations()[0]
    target = load_targets()[0]
    observation_payload = observation.model_dump()
    observation_payload["value_kind"] = "target"
    target_payload = target.model_dump()
    target_payload["value_kind"] = "actual"

    with pytest.raises(ValidationError):
        SustainabilityObservation.model_validate(observation_payload)
    with pytest.raises(ValidationError):
        ClimateTarget.model_validate(target_payload)


def test_issuer_reported_and_code_derived_origins_are_distinct() -> None:
    payload = _observation_payload("observation-bachem-2025-scope-one")
    payload["value_origin"] = "code_derived"
    derived = SustainabilityObservation.model_validate(payload)

    assert load_observations()[0].value_origin == "issuer_reported"
    assert derived.value_origin == "code_derived"


def test_assurance_present_absent_and_ambiguous_are_explicit() -> None:
    assessments = load_assurance_assessments()
    present = assessments[0]
    absent = assessments[-1]
    ambiguous_payload = absent.model_dump()
    ambiguous_payload.update(
        assessment_id="assurance-siegfried-scope-one-ambiguous",
        status="ambiguous",
        level="unknown",
    )
    ambiguous = AssuranceAssessment.model_validate(ambiguous_payload)

    assert present.assurance_scope_confirmed
    assert present.level == "limited"
    assert absent.status == "explicitly_not_assured"
    assert ambiguous.status == "ambiguous"


def test_unit_compatibility_and_exact_decimal_conversion() -> None:
    assert units_compatible("ktCO2e", "tCO2e")
    assert units_compatible("TJ", "GJ")
    assert not units_compatible("GJ", "tCO2e")
    assert convert_value(Decimal("52"), "ktCO2e", "tCO2e") == Decimal("52000")
    assert convert_value(Decimal("217336"), "GJ", "TJ") == Decimal("217.336")

    with pytest.raises(ValueError, match="Incompatible units"):
        convert_value(Decimal("1"), "GJ", "tCO2e")


def test_publication_cutoff_uses_document_publication_date() -> None:
    documents = load_manifest()

    before_both = documents_at_cutoff(documents, date(2026, 2, 19))
    siegfried_only = documents_at_cutoff(documents, date(2026, 2, 20))
    before_bachem_release = documents_at_cutoff(documents, date(2026, 3, 11))
    on_bachem_release = documents_at_cutoff(documents, date(2026, 3, 12))

    assert before_both == ()
    assert tuple(item.issuer_id for item in siegfried_only) == ("siegfried-holding-ag",)
    assert tuple(item.issuer_id for item in before_bachem_release) == (
        "siegfried-holding-ag",
    )
    assert len(on_bachem_release) == 2


def test_bachem_publication_date_uses_official_release_evidence() -> None:
    bachem = next(
        document
        for document in load_manifest()
        if document.issuer_id == "bachem-holding-ag"
    )

    assert bachem.publication_date == date(2026, 3, 12)
    assert bachem.publication_date_status == "exact"
    assert bachem.publication_date_evidence_url.endswith(
        "/Media-Release-Financial-Year-2025_final.pdf"
    )


def test_pdf_and_printed_page_numbers_are_preserved_separately() -> None:
    bachem = load_observations()[0]
    siegfried = next(
        item
        for item in load_observations()
        if item.observation_id == "observation-siegfried-2025-scope-one"
    )

    assert (bachem.pdf_page, bachem.printed_page) == (33, 31)
    assert (siegfried.pdf_page, siegfried.printed_page) == (57, 57)


def test_comparison_artifact_records_all_required_dimensions() -> None:
    comparison = load_comparison_assessments()[0]

    assert comparison.organizational_boundary == "different"
    assert comparison.period == "same"
    assert comparison.unit == "convertible"
    assert comparison.scope_2_method == "not_applicable"
    assert comparison.basis == "same"
    assert comparison.restatement == "different"
    assert comparison.assurance == "different"
    assert comparison.definition_or_methodology == "unknown"
