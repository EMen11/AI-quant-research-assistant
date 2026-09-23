"""Deterministic local PDF extraction and source-file verification."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from pypdf import PdfReader

from ai_quant.sustainability.models import ExtractedPage, SourceDocumentManifest


class SourceDocumentError(RuntimeError):
    """Raised when a local official PDF does not match its committed manifest."""


def sha256_file(path: Path) -> str:
    """Hash exact file bytes with bounded memory usage."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_pdf_pages(
    path: Path,
    manifest: SourceDocumentManifest,
    *,
    printed_pages: Mapping[int, int | None] | None = None,
) -> tuple[ExtractedPage, ...]:
    """Extract text page-by-page; never invoke OCR or infer printed pagination."""

    actual_hash = sha256_file(path)
    if actual_hash != manifest.sha256:
        raise SourceDocumentError(
            f"SHA-256 mismatch for {manifest.document_id}: {actual_hash}."
        )
    reader = PdfReader(path)
    if len(reader.pages) != manifest.page_count:
        raise SourceDocumentError(
            f"Page-count mismatch for {manifest.document_id}: {len(reader.pages)}."
        )

    printed_pages = printed_pages or {}
    extracted: list[ExtractedPage] = []
    for pdf_page, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        text = raw_text.strip()
        status = "extracted" if text else "ocr_required_not_supported"
        extracted.append(
            ExtractedPage(
                schema_version="extracted-page.v1",
                document_id=manifest.document_id,
                document_sha256=manifest.sha256,
                pdf_page=pdf_page,
                printed_page=printed_pages.get(pdf_page),
                extraction_method="pypdf-text-v1",
                extraction_status=status,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                text=text,
            )
        )
    return tuple(extracted)


def verify_local_documents(
    source_directory: Path,
    manifests: tuple[SourceDocumentManifest, ...],
) -> None:
    """Verify exact bytes and page counts without contacting a network."""

    for manifest in manifests:
        path = source_directory / manifest.local_filename
        if not path.is_file():
            raise SourceDocumentError(f"Missing local PDF for {manifest.document_id}: {path}.")
        actual_hash = sha256_file(path)
        if actual_hash != manifest.sha256:
            raise SourceDocumentError(
                f"SHA-256 mismatch for {manifest.document_id}: {actual_hash}."
            )
        page_count = len(PdfReader(path).pages)
        if page_count != manifest.page_count:
            raise SourceDocumentError(
                f"Page-count mismatch for {manifest.document_id}: {page_count}."
            )
