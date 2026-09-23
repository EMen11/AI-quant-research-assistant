"""Local-only commands for climate corpus verification and PDF extraction."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_quant.sustainability.corpus import (
    load_corpus,
    load_manifest,
    load_observations,
    load_targets,
)
from ai_quant.sustainability.extraction import extract_pdf_pages, verify_local_documents


def main() -> None:
    """Run an explicitly selected offline corpus command."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_artifacts = subparsers.add_parser(
        "verify-artifacts", help="Validate committed artifacts without official PDFs."
    )
    verify_artifacts.add_argument("--cutoff", default="9999-12-31")

    verify_pdfs = subparsers.add_parser(
        "verify-pdfs", help="Verify locally downloaded official PDF bytes and page counts."
    )
    verify_pdfs.add_argument(
        "--source-dir", type=Path, default=Path("data/source_documents")
    )

    extract = subparsers.add_parser(
        "extract", help="Extract local official PDFs page-by-page without OCR."
    )
    extract.add_argument(
        "--source-dir", type=Path, default=Path("data/source_documents")
    )
    extract.add_argument(
        "--output-dir", type=Path, default=Path("data/extracted_pages")
    )

    args = parser.parse_args()
    if args.command == "verify-artifacts":
        from datetime import date

        cutoff = date.fromisoformat(args.cutoff)
        corpus = load_corpus(cutoff)
        print(
            f"verified documents={len(corpus.documents)} "
            f"observations={len(corpus.observations)} targets={len(corpus.targets)}"
        )
        return

    manifests = load_manifest()
    verify_local_documents(args.source_dir, manifests)
    if args.command == "verify-pdfs":
        print(f"verified local_pdfs={len(manifests)}")
        return

    printed_pages: dict[str, dict[int, int | None]] = {
        manifest.document_id: {} for manifest in manifests
    }
    for record in (*load_observations(), *load_targets()):
        printed_pages[record.document_id][record.pdf_page] = record.printed_page
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for manifest in manifests:
        pages = extract_pdf_pages(
            args.source_dir / manifest.local_filename,
            manifest,
            printed_pages=printed_pages[manifest.document_id],
        )
        output = args.output_dir / f"{manifest.document_id}.jsonl"
        output.write_text(
            "".join(f"{page.model_dump_json()}\n" for page in pages),
            encoding="utf-8",
        )
        print(f"extracted document={manifest.document_id} pages={len(pages)}")


if __name__ == "__main__":
    main()
