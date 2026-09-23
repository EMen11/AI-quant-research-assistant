"""Offline artifact loading, cutoff filtering and comparability primitives."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import Field

from ai_quant.sustainability.models import (
    AssuranceAssessment,
    ClimateTarget,
    ComparisonAssessment,
    CoverageFinding,
    MeasurementUnit,
    SourceDocumentManifest,
    SustainabilityObservation,
)
from ai_quant.trust.models import Identifier, NonEmptyText, StrictModel


class CorpusReferenceError(ValueError):
    """Raised when a corpus record references an unknown or changed source."""


class ManifestArtifact(StrictModel):
    schema_version: Literal["climate-source-manifest.v1"]
    documents: tuple[SourceDocumentManifest, ...]


class TargetArtifact(StrictModel):
    schema_version: Literal["climate-targets.v1"]
    targets: tuple[ClimateTarget, ...]


class AssuranceArtifact(StrictModel):
    schema_version: Literal["climate-assurance.v1"]
    assessments: tuple[AssuranceAssessment, ...]


class ComparisonArtifact(StrictModel):
    schema_version: Literal["climate-comparisons.v1"]
    assessments: tuple[ComparisonAssessment, ...]


class CoverageReport(StrictModel):
    schema_version: Literal["climate-coverage-report.v1"]
    manual_verification_status: Literal["pending", "completed"]
    document_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    observations_by_issuer: tuple[tuple[Identifier, int], ...]
    findings: tuple[CoverageFinding, ...]
    limitations: tuple[NonEmptyText, ...]


class SustainabilityCorpus(StrictModel):
    """Validated offline view after applying a publication cutoff."""

    cutoff_date: date
    documents: tuple[SourceDocumentManifest, ...]
    observations: tuple[SustainabilityObservation, ...]
    targets: tuple[ClimateTarget, ...]
    assurance_assessments: tuple[AssuranceAssessment, ...]
    comparison_assessments: tuple[ComparisonAssessment, ...]
    coverage_report: CoverageReport


_UNIT_FACTORS: dict[MeasurementUnit, tuple[str, Decimal]] = {
    "tCO2e": ("emissions", Decimal("1")),
    "ktCO2e": ("emissions", Decimal("1000")),
    "GJ": ("energy", Decimal("1")),
    "TJ": ("energy", Decimal("1000")),
    "%": ("share", Decimal("1")),
}


def units_compatible(left: MeasurementUnit, right: MeasurementUnit) -> bool:
    """Return whether two explicitly supported units share a physical dimension."""

    return _UNIT_FACTORS[left][0] == _UNIT_FACTORS[right][0]


def convert_value(
    value: Decimal,
    from_unit: MeasurementUnit,
    to_unit: MeasurementUnit,
) -> Decimal:
    """Convert compatible units with exact Decimal factors."""

    if not units_compatible(from_unit, to_unit):
        raise ValueError(f"Incompatible units: {from_unit} and {to_unit}.")
    from_factor = _UNIT_FACTORS[from_unit][1]
    to_factor = _UNIT_FACTORS[to_unit][1]
    return value * from_factor / to_factor


def documents_at_cutoff(
    documents: tuple[SourceDocumentManifest, ...], cutoff_date: date
) -> tuple[SourceDocumentManifest, ...]:
    """Include only documents published no later than the research cutoff."""

    return tuple(
        document
        for document in documents
        if document.publication_date is not None
        and document.publication_date <= cutoff_date
    )


def validate_document_reference(
    *,
    document_id: str,
    document_sha256: str,
    documents: tuple[SourceDocumentManifest, ...],
) -> SourceDocumentManifest:
    """Resolve a source by both server ID and exact byte hash."""

    by_id = {document.document_id: document for document in documents}
    document = by_id.get(document_id)
    if document is None:
        raise CorpusReferenceError(f"Unknown source document: {document_id}.")
    if document.sha256 != document_sha256:
        raise CorpusReferenceError(f"Unknown source hash for {document_id}.")
    return document


def load_manifest() -> tuple[SourceDocumentManifest, ...]:
    artifact = ManifestArtifact.model_validate_json(_read_fixture("manifest.v1.json"))
    _require_unique(
        (document.document_id for document in artifact.documents), "document_id"
    )
    return artifact.documents


def load_observations() -> tuple[SustainabilityObservation, ...]:
    observations = tuple(
        SustainabilityObservation.model_validate_json(line)
        for line in _read_fixture("observations.v1.jsonl").splitlines()
        if line.strip()
    )
    _require_unique(
        (observation.observation_id for observation in observations),
        "observation_id",
    )
    return observations


def load_targets() -> tuple[ClimateTarget, ...]:
    artifact = TargetArtifact.model_validate_json(_read_fixture("targets.v1.json"))
    _require_unique((target.target_id for target in artifact.targets), "target_id")
    return artifact.targets


def load_assurance_assessments() -> tuple[AssuranceAssessment, ...]:
    artifact = AssuranceArtifact.model_validate_json(
        _read_fixture("assurance.v1.json")
    )
    _require_unique(
        (assessment.assessment_id for assessment in artifact.assessments),
        "assessment_id",
    )
    return artifact.assessments


def load_comparison_assessments() -> tuple[ComparisonAssessment, ...]:
    artifact = ComparisonArtifact.model_validate_json(
        _read_fixture("comparisons.v1.json")
    )
    _require_unique(
        (assessment.comparison_id for assessment in artifact.assessments),
        "comparison_id",
    )
    return artifact.assessments


def load_coverage_report() -> CoverageReport:
    return CoverageReport.model_validate_json(_read_fixture("coverage_report.v1.json"))


def load_corpus(cutoff_date: date) -> SustainabilityCorpus:
    """Load committed artifacts, enforce lineage, then apply publication cutoff."""

    all_documents = load_manifest()
    eligible_documents = documents_at_cutoff(all_documents, cutoff_date)
    eligible_document_ids = {document.document_id for document in eligible_documents}

    all_observations = load_observations()
    for observation in all_observations:
        document = validate_document_reference(
            document_id=observation.document_id,
            document_sha256=observation.document_sha256,
            documents=all_documents,
        )
        _validate_record_document_fields(
            issuer_id=observation.issuer_id,
            publication_date=observation.publication_date,
            document=document,
            record_id=observation.observation_id,
        )
        if observation.document_title != document.title:
            raise CorpusReferenceError(
                f"Document title mismatch for {observation.observation_id}."
            )
        if observation.document_year != document.document_year:
            raise CorpusReferenceError(
                f"Document year mismatch for {observation.observation_id}."
            )
    observations = tuple(
        observation
        for observation in all_observations
        if observation.document_id in eligible_document_ids
    )
    observation_ids = {observation.observation_id for observation in observations}

    all_targets = load_targets()
    for target in all_targets:
        document = validate_document_reference(
            document_id=target.document_id,
            document_sha256=target.document_sha256,
            documents=all_documents,
        )
        _validate_record_document_fields(
            issuer_id=target.issuer_id,
            publication_date=target.publication_date,
            document=document,
            record_id=target.target_id,
        )
    targets = tuple(
        target for target in all_targets if target.document_id in eligible_document_ids
    )

    all_observation_ids = {
        observation.observation_id for observation in all_observations
    }
    observations_by_id = {
        observation.observation_id: observation for observation in all_observations
    }
    all_assurance = load_assurance_assessments()
    for assessment in all_assurance:
        validate_document_reference(
            document_id=assessment.document_id,
            document_sha256=assessment.document_sha256,
            documents=all_documents,
        )
        if assessment.observation_id not in all_observation_ids:
            raise CorpusReferenceError(
                f"Assurance assessment references unknown observation: "
                f"{assessment.observation_id}."
            )
        observation = observations_by_id[assessment.observation_id]
        if assessment.document_id != observation.document_id:
            raise CorpusReferenceError(
                f"Assurance source mismatch for {assessment.assessment_id}."
            )
    assurance = tuple(
        assessment
        for assessment in all_assurance
        if assessment.observation_id in observation_ids
    )

    all_comparisons = load_comparison_assessments()
    for assessment in all_comparisons:
        referenced_ids = {
            assessment.left_observation_id,
            assessment.right_observation_id,
        }
        unknown = referenced_ids - all_observation_ids
        if unknown:
            raise CorpusReferenceError(
                f"Comparison assessment references unknown observations: {sorted(unknown)}."
            )
    comparisons = tuple(
        assessment
        for assessment in all_comparisons
        if assessment.left_observation_id in observation_ids
        and assessment.right_observation_id in observation_ids
    )

    coverage = load_coverage_report()
    expected_counts = _observation_counts(all_observations)
    if coverage.document_count != len(all_documents):
        raise CorpusReferenceError("Coverage report document_count is inconsistent.")
    if coverage.observation_count != len(all_observations):
        raise CorpusReferenceError("Coverage report observation_count is inconsistent.")
    if dict(coverage.observations_by_issuer) != dict(expected_counts):
        raise CorpusReferenceError("Coverage report issuer counts are inconsistent.")
    known_document_ids = {document.document_id for document in all_documents}
    documents_by_id = {
        document.document_id: document for document in all_documents
    }
    for finding in coverage.findings:
        unknown = set(finding.searched_document_ids) - known_document_ids
        if unknown:
            raise CorpusReferenceError(
                f"Coverage finding references unknown documents: {sorted(unknown)}."
            )
        if any(
            documents_by_id[document_id].issuer_id != finding.issuer_id
            for document_id in finding.searched_document_ids
        ):
            raise CorpusReferenceError(
                f"Coverage finding source issuer mismatch for {finding.finding_id}."
            )

    eligible_findings = tuple(
        finding
        for finding in coverage.findings
        if set(finding.searched_document_ids) <= eligible_document_ids
    )
    eligible_counts = _observation_counts(observations)
    coverage_at_cutoff = CoverageReport(
        schema_version="climate-coverage-report.v1",
        manual_verification_status=coverage.manual_verification_status,
        document_count=len(eligible_documents),
        observation_count=len(observations),
        observations_by_issuer=eligible_counts,
        findings=eligible_findings,
        limitations=coverage.limitations,
    )

    return SustainabilityCorpus(
        cutoff_date=cutoff_date,
        documents=eligible_documents,
        observations=observations,
        targets=targets,
        assurance_assessments=assurance,
        comparison_assessments=comparisons,
        coverage_report=coverage_at_cutoff,
    )


def _validate_record_document_fields(
    *,
    issuer_id: str,
    publication_date: date,
    document: SourceDocumentManifest,
    record_id: str,
) -> None:
    if issuer_id != document.issuer_id:
        raise CorpusReferenceError(f"Issuer mismatch for {record_id}.")
    if publication_date != document.publication_date:
        raise CorpusReferenceError(f"Publication date mismatch for {record_id}.")


def _observation_counts(
    observations: tuple[SustainabilityObservation, ...],
) -> tuple[tuple[str, int], ...]:
    issuer_ids = sorted({observation.issuer_id for observation in observations})
    return tuple(
        (
            issuer_id,
            sum(observation.issuer_id == issuer_id for observation in observations),
        )
        for issuer_id in issuer_ids
    )


def fixture_directory() -> Path:
    """Return the packaged sustainability artifact directory."""

    return Path(str(files("ai_quant.fixtures").joinpath("sustainability")))


def _read_fixture(filename: str) -> str:
    return (fixture_directory() / filename).read_text(encoding="utf-8")


def _require_unique(values: Iterable[str], field_name: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise CorpusReferenceError(f"Duplicate {field_name} in corpus artifact.")
