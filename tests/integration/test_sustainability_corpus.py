"""Offline lineage and extraction tests for the Block 4 corpus."""

from __future__ import annotations

import socket
from datetime import date
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from ai_quant.sustainability import (
    CorpusReferenceError,
    SourceDocumentError,
    SourceDocumentManifest,
    extract_pdf_pages,
    load_corpus,
    load_manifest,
    load_observations,
    sha256_file,
    validate_document_reference,
)


def test_committed_corpus_has_two_documents_and_twelve_balanced_observations() -> None:
    corpus = load_corpus(date(2026, 3, 12))
    issuer_counts = {
        issuer_id: sum(
            observation.issuer_id == issuer_id for observation in corpus.observations
        )
        for issuer_id in {item.issuer_id for item in corpus.observations}
    }

    assert len(corpus.documents) == 2
    assert len(corpus.observations) == 12
    assert issuer_counts == {"bachem-holding-ag": 6, "siegfried-holding-ag": 6}
    assert corpus.coverage_report.manual_verification_status == "completed"


def test_corpus_loading_requires_no_network(monkeypatch) -> None:
    def forbid_network(*args, **kwargs):
        raise AssertionError("Offline corpus loading attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbid_network)

    corpus = load_corpus(date(2026, 3, 12))

    assert len(corpus.observations) == 12


def test_cutoff_filters_documents_records_and_coverage_together() -> None:
    corpus = load_corpus(date(2026, 2, 20))

    assert tuple(document.issuer_id for document in corpus.documents) == (
        "siegfried-holding-ag",
    )
    assert len(corpus.observations) == 6
    assert len(corpus.targets) == 1
    assert corpus.coverage_report.document_count == 1
    assert corpus.coverage_report.observation_count == 6
    assert corpus.coverage_report.observations_by_issuer == (
        ("siegfried-holding-ag", 6),
    )
    assert corpus.coverage_report.findings == ()


def test_bachem_is_excluded_before_and_included_on_official_release_date() -> None:
    before_release = load_corpus(date(2026, 3, 11))
    on_release = load_corpus(date(2026, 3, 12))

    assert {document.issuer_id for document in before_release.documents} == {
        "siegfried-holding-ag"
    }
    assert len(before_release.observations) == 6
    assert {document.issuer_id for document in on_release.documents} == {
        "bachem-holding-ag",
        "siegfried-holding-ag",
    }
    assert len(on_release.observations) == 12


def test_unknown_document_or_hash_is_rejected() -> None:
    documents = load_manifest()

    with pytest.raises(CorpusReferenceError, match="Unknown source document"):
        validate_document_reference(
            document_id="document-unknown-report-2025",
            document_sha256="0" * 64,
            documents=documents,
        )
    with pytest.raises(CorpusReferenceError, match="Unknown source hash"):
        validate_document_reference(
            document_id=documents[0].document_id,
            document_sha256="0" * 64,
            documents=documents,
        )


def test_every_observation_resolves_to_exact_manifest_hash() -> None:
    documents = load_manifest()

    resolved = [
        validate_document_reference(
            document_id=observation.document_id,
            document_sha256=observation.document_sha256,
            documents=documents,
        )
        for observation in load_observations()
    ]

    assert len(resolved) == 12


def test_deterministic_page_extraction_preserves_page_identity(tmp_path: Path) -> None:
    source = tmp_path / "synthetic-source.pdf"
    pdf = canvas.Canvas(str(source))
    pdf.drawString(72, 720, "Issuer reported Scope 1: 12 tCO2e")
    pdf.showPage()
    pdf.showPage()
    pdf.save()

    manifest_payload = load_manifest()[0].model_dump()
    manifest_payload.update(
        document_id="document-synthetic-source-2025",
        issuer_id="synthetic-issuer",
        title="Synthetic source",
        local_filename="synthetic-source.pdf",
        local_path="data/source_documents/synthetic-source.pdf",
        sha256=sha256_file(source),
        page_count=2,
    )
    manifest = SourceDocumentManifest.model_validate(manifest_payload)

    first = extract_pdf_pages(source, manifest, printed_pages={1: 7, 2: 8})
    second = extract_pdf_pages(source, manifest, printed_pages={1: 7, 2: 8})

    assert tuple((page.pdf_page, page.printed_page) for page in first) == (
        (1, 7),
        (2, 8),
    )
    assert first[0].extraction_status == "extracted"
    assert first[1].extraction_status == "ocr_required_not_supported"
    assert first == second


def test_extraction_rejects_changed_source_bytes(tmp_path: Path) -> None:
    source = tmp_path / "synthetic-source.pdf"
    source.write_bytes(b"not the manifested PDF")
    manifest = load_manifest()[0]

    with pytest.raises(SourceDocumentError, match="SHA-256 mismatch"):
        extract_pdf_pages(source, manifest)
