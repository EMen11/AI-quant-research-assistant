"""Strict models for the traceable offline climate corpus."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ai_quant.trust.models import Identifier, NonEmptyText, Sha256, StrictModel

CoverageStatus = Literal[
    "reported_value",
    "reported_zero",
    "not_found",
    "explicitly_not_published",
    "ambiguous",
]
ValueKind = Literal["actual", "target"]
ValueOrigin = Literal["issuer_reported", "code_derived"]
Scope2Method = Literal["location_based", "market_based", "not_applicable"]
IndicatorType = Literal[
    "scope_1_ghg_emissions",
    "scope_2_ghg_emissions",
    "scope_3_ghg_emissions",
    "total_energy_consumption",
    "electricity_consumption",
    "renewable_energy_consumption",
    "renewable_electricity_share",
    "climate_target",
]
MeasurementUnit = Literal["tCO2e", "ktCO2e", "GJ", "TJ", "%"]
MeasurementBasis = Literal["absolute", "intensity", "share"]
AssuranceStatus = Literal[
    "verified_in_assurance_statement",
    "issuer_claimed_assurance",
    "explicitly_not_assured",
    "not_stated",
    "ambiguous",
]
AssuranceLevel = Literal["limited", "reasonable", "not_applicable", "unknown"]
PublicationDateStatus = Literal["exact", "conservative_proxy", "unknown"]
ComparisonStatus = Literal[
    "comparable",
    "partially_comparable",
    "not_comparable",
    "review_required",
]
DimensionAssessment = Literal[
    "same",
    "convertible",
    "different",
    "unknown",
    "not_applicable",
]
DecimalValue = Annotated[Decimal, Field(max_digits=28, decimal_places=10)]
ShortExcerpt = Annotated[str, Field(min_length=1, max_length=180)]
OfficialUrl = Annotated[str, Field(pattern=r"^https://[A-Za-z0-9.-]+/.+")]


class SourceDocumentManifest(StrictModel):
    """Immutable identity and local storage metadata for one official PDF."""

    schema_version: Literal["source-document-manifest.v1"]
    document_id: Identifier
    issuer_id: Identifier
    title: NonEmptyText
    document_year: int = Field(ge=2000, le=2100)
    document_type: Literal["annual_report", "sustainability_report"]
    reporting_period_start: date
    reporting_period_end: date
    publication_date: date | None
    publication_date_status: PublicationDateStatus
    publication_date_evidence: NonEmptyText
    publication_date_evidence_url: OfficialUrl
    official_page_url: OfficialUrl
    requested_url: OfficialUrl
    final_url: OfficialUrl
    accessed_at: datetime
    local_filename: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]+\.pdf$")]
    local_path: Annotated[
        str,
        Field(pattern=r"^data/source_documents/[a-z0-9][a-z0-9.-]+\.pdf$"),
    ]
    sha256: Sha256
    page_count: int = Field(ge=1)
    language: Literal["en"]
    extraction_status: Literal["text_extractable", "ocr_required", "unsupported"]

    @field_validator("accessed_at")
    @classmethod
    def accessed_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("accessed_at must be timezone-aware UTC.")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> SourceDocumentManifest:
        if self.reporting_period_end < self.reporting_period_start:
            raise ValueError("reporting_period_end must not precede reporting_period_start.")
        if self.document_year != self.reporting_period_end.year:
            raise ValueError("document_year must match reporting_period_end year.")
        if self.publication_date_status == "unknown" and self.publication_date is not None:
            raise ValueError("Unknown publication date status requires publication_date=None.")
        if self.publication_date_status != "unknown" and self.publication_date is None:
            raise ValueError("A known or proxy publication date requires a date.")
        return self


class SustainabilityObservation(StrictModel):
    """One issuer-published or Python-derived measured climate observation."""

    schema_version: Literal["sustainability-observation.v1"]
    observation_id: Identifier
    issuer_id: Identifier
    document_id: Identifier
    document_title: NonEmptyText
    document_year: int = Field(ge=2000, le=2100)
    publication_date: date
    period_start: date
    period_end: date
    pdf_page: int = Field(ge=1)
    printed_page: int | None = Field(default=None, ge=1)
    short_exact_excerpt: ShortExcerpt
    indicator_type: IndicatorType
    raw_metric_label: NonEmptyText
    value: DecimalValue | None
    unit: MeasurementUnit | None
    coverage_status: CoverageStatus
    value_kind: ValueKind
    value_origin: ValueOrigin
    basis: MeasurementBasis
    scope_2_method: Scope2Method
    assurance_status: AssuranceStatus
    organizational_boundary: NonEmptyText
    methodology_or_standard: NonEmptyText
    restatement: NonEmptyText
    document_sha256: Sha256
    provenance: Literal["official_issuer_pdf_manual_annotation_v1"]

    @model_validator(mode="after")
    def validate_semantics(self) -> SustainabilityObservation:
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start.")
        if self.coverage_status == "reported_zero" and self.value != Decimal("0"):
            raise ValueError("reported_zero requires an explicit Decimal zero.")
        if self.coverage_status == "reported_value" and (
            self.value is None or self.value == Decimal("0")
        ):
            raise ValueError("reported_value requires an explicit non-zero value.")
        if self.coverage_status in {
            "not_found",
            "explicitly_not_published",
            "ambiguous",
        } and self.value is not None:
            raise ValueError("Missing or ambiguous coverage cannot carry a numeric value.")
        if self.coverage_status.startswith("reported_") and self.unit is None:
            raise ValueError("A reported value requires a unit.")
        if self.indicator_type == "scope_2_ghg_emissions":
            if self.scope_2_method == "not_applicable":
                raise ValueError("Scope 2 observations require location- or market-based method.")
        elif self.scope_2_method != "not_applicable":
            raise ValueError("Only Scope 2 observations can declare a Scope 2 method.")
        if self.value_kind != "actual":
            raise ValueError("Measured observations are actual; use ClimateTarget for targets.")
        return self


class ClimateTarget(StrictModel):
    """Issuer-published climate target kept separate from actual observations."""

    schema_version: Literal["climate-target.v1"]
    target_id: Identifier
    issuer_id: Identifier
    document_id: Identifier
    document_sha256: Sha256
    publication_date: date
    pdf_page: int = Field(ge=1)
    printed_page: int | None = Field(default=None, ge=1)
    short_exact_excerpt: ShortExcerpt
    indicator_type: Literal["climate_target"]
    value_kind: Literal["target"]
    value_origin: Literal["issuer_reported"]
    target_value: DecimalValue
    unit: Literal["%"]
    base_year: int = Field(ge=1990, le=2100)
    target_year: int = Field(ge=1990, le=2100)
    covered_scopes: Annotated[tuple[Literal["scope_1", "scope_2", "scope_3"], ...], Field(min_length=1)]
    validation_status: Literal[
        "issuer_claimed_external_validation",
        "externally_verified_in_registry",
        "submitted_for_validation",
        "not_stated",
    ]
    organizational_boundary: NonEmptyText
    methodology_or_standard: NonEmptyText
    assurance_status: AssuranceStatus
    provenance: Literal["official_issuer_pdf_manual_annotation_v1"]

    @model_validator(mode="after")
    def target_year_follows_base_year(self) -> ClimateTarget:
        if self.target_year <= self.base_year:
            raise ValueError("target_year must be after base_year.")
        if len(set(self.covered_scopes)) != len(self.covered_scopes):
            raise ValueError("covered_scopes must be unique.")
        return self


class CoverageFinding(StrictModel):
    """Explicit result of searching the bounded official corpus for an indicator."""

    schema_version: Literal["coverage-finding.v1"]
    finding_id: Identifier
    issuer_id: Identifier
    indicator_type: IndicatorType
    period_start: date
    period_end: date
    status: CoverageStatus
    searched_document_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    pdf_page: int | None = Field(default=None, ge=1)
    printed_page: int | None = Field(default=None, ge=1)
    short_exact_excerpt: str | None = Field(default=None, min_length=1, max_length=180)
    notes: NonEmptyText

    @model_validator(mode="after")
    def validate_finding(self) -> CoverageFinding:
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start.")
        if self.status == "explicitly_not_published" and not self.short_exact_excerpt:
            raise ValueError("Explicit non-publication requires an exact excerpt.")
        if self.status in {"reported_value", "reported_zero"}:
            raise ValueError("Reported values belong in SustainabilityObservation.")
        return self


class ComparisonAssessment(StrictModel):
    """Versioned pairwise assessment; comparison is never inferred from units alone."""

    schema_version: Literal["comparison-assessment.v1"]
    comparison_id: Identifier
    left_observation_id: Identifier
    right_observation_id: Identifier
    purpose: Literal["cross_issuer", "time_series"]
    ruleset_version: Literal["climate-comparability.v1"]
    status: ComparisonStatus
    organizational_boundary: DimensionAssessment
    period: DimensionAssessment
    unit: DimensionAssessment
    scope_2_method: DimensionAssessment
    basis: DimensionAssessment
    restatement: DimensionAssessment
    assurance: DimensionAssessment
    definition_or_methodology: DimensionAssessment
    reasons: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def observations_are_distinct(self) -> ComparisonAssessment:
        if self.left_observation_id == self.right_observation_id:
            raise ValueError("A comparison requires two distinct observations.")
        return self


class AssuranceAssessment(StrictModel):
    """Assessment of whether assurance explicitly covers one observation."""

    schema_version: Literal["assurance-assessment.v1"]
    assessment_id: Identifier
    observation_id: Identifier
    document_id: Identifier
    document_sha256: Sha256
    status: AssuranceStatus
    level: AssuranceLevel
    assurance_scope_confirmed: bool
    pdf_page: int = Field(ge=1)
    printed_page: int | None = Field(default=None, ge=1)
    short_exact_excerpt: ShortExcerpt
    notes: NonEmptyText

    @model_validator(mode="after")
    def validate_assurance(self) -> AssuranceAssessment:
        if self.status == "verified_in_assurance_statement":
            if self.level not in {"limited", "reasonable"}:
                raise ValueError("Verified assurance requires a stated assurance level.")
            if not self.assurance_scope_confirmed:
                raise ValueError("Verified assurance requires confirmed metric scope.")
        if self.status == "explicitly_not_assured":
            if self.level != "not_applicable" or self.assurance_scope_confirmed:
                raise ValueError("Explicitly unassured data cannot have assurance scope or level.")
        return self


class ExtractedPage(StrictModel):
    """Deterministic local extraction result preserving PDF and printed page identity."""

    schema_version: Literal["extracted-page.v1"]
    document_id: Identifier
    document_sha256: Sha256
    pdf_page: int = Field(ge=1)
    printed_page: int | None = Field(default=None, ge=1)
    extraction_method: Literal["pypdf-text-v1"]
    extraction_status: Literal["extracted", "ocr_required_not_supported"]
    text_sha256: Sha256
    text: str

    @model_validator(mode="after")
    def validate_extraction(self) -> ExtractedPage:
        if self.extraction_status == "extracted" and not self.text.strip():
            raise ValueError("Extracted pages require non-empty text.")
        if self.extraction_status == "ocr_required_not_supported" and self.text:
            raise ValueError("Unsupported OCR pages cannot claim extracted text.")
        return self
