"""Validated runtime loader for the embedded, network-independent Equity fixtures."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ai_quant.equity.models import (
    EquityValidationError,
    Formula,
    MetricValue,
    SourceReference,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "equity"
EXPECTED_TICKERS = ("BANB.SW", "SFZN.SW")
EXPECTED_YEARS = tuple(range(2021, 2026))
COMPANY_IDS = {"BANB.SW": "bachem", "SFZN.SW": "siegfried"}


@dataclass(frozen=True, slots=True)
class EquityRepository:
    """Immutable in-memory view backed only by verified embedded files."""

    metrics: tuple[MetricValue, ...]
    manifest: dict[str, Any]
    valuation_diagnostic: dict[str, Any]

    def metric(self, ticker: str, fiscal_year: int, metric_name: str) -> MetricValue:
        """Return exactly one metric by issuer, period, and canonical name."""

        company_id = COMPANY_IDS.get(ticker)
        if company_id is None:
            raise KeyError(f"Unknown Equity ticker: {ticker}")
        matches = tuple(
            item
            for item in self.metrics
            if item.company_id == company_id
            and item.fiscal_year == fiscal_year
            and item.name == metric_name
        )
        if len(matches) != 1:
            raise KeyError(f"Metric not found: {ticker} FY{fiscal_year} {metric_name}")
        return matches[0]


def load_equity_repository(fixture_dir: Path = FIXTURE_DIR) -> EquityRepository:
    """Validate hashes and schemas, then load fixtures without any external access."""

    manifest_path = fixture_dir / "manifest.v1.json"
    if not manifest_path.is_file():
        raise EquityValidationError("Embedded Equity manifest is missing.")
    try:
        manifest = json.loads(manifest_path.read_bytes())
    except json.JSONDecodeError as error:
        raise EquityValidationError("Embedded Equity manifest is invalid JSON.") from error
    _validate_manifest(manifest)
    for output in manifest["outputs"]:
        path = fixture_dir / output["file"]
        if not path.is_file():
            raise EquityValidationError(f"Embedded Equity output is missing: {path.name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != output["sha256"]:
            raise EquityValidationError(f"Embedded Equity hash mismatch: {path.name}")

    sources = _load_sources(fixture_dir / "cdmo_sources.v1.csv")
    metrics = _load_metrics(fixture_dir / "cdmo_fundamentals.v1.csv", sources)
    expected_count = len(manifest["fields"]) * len(EXPECTED_TICKERS) * len(EXPECTED_YEARS)
    if len(metrics) != expected_count:
        raise EquityValidationError(
            f"Equity metric cardinality mismatch: expected {expected_count}, found {len(metrics)}."
        )
    diagnostic = json.loads((fixture_dir / "valuation_diagnostic.v1.json").read_bytes())
    if diagnostic.get("schema_version") != "equity-valuation-diagnostic.v1":
        raise EquityValidationError("Unexpected Equity valuation diagnostic schema.")
    return EquityRepository(
        metrics=tuple(sorted(metrics, key=lambda item: item.metric_id)),
        manifest=manifest,
        valuation_diagnostic=diagnostic,
    )


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != "equity-snapshot-manifest.v1":
        raise EquityValidationError("Unexpected Equity manifest schema.")
    if manifest.get("runtime_external_dependency") is not False:
        raise EquityValidationError("Equity runtime must not declare an external dependency.")
    if manifest.get("tickers") != list(EXPECTED_TICKERS):
        raise EquityValidationError("Equity manifest ticker universe is invalid.")
    if manifest.get("periods") != list(EXPECTED_YEARS):
        raise EquityValidationError("Equity manifest period universe is invalid.")
    if manifest.get("gates", {}).get("fundamentals") != "pass":
        raise EquityValidationError("Equity fundamentals gate is not open.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise EquityValidationError("Equity manifest outputs are missing.")
    if len({item.get("file") for item in outputs}) != len(outputs):
        raise EquityValidationError("Equity manifest output names must be unique.")


def _load_sources(path: Path) -> dict[str, SourceReference]:
    rows = _read_csv(path)
    if len(rows) != len(EXPECTED_TICKERS) * len(EXPECTED_YEARS):
        raise EquityValidationError("Equity source fixture must contain exactly ten rows.")
    sources: dict[str, SourceReference] = {}
    for row in rows:
        source_id = row["source_id"]
        if source_id in sources:
            raise EquityValidationError(f"Duplicate Equity source ID: {source_id}")
        page = int(row["pdf_page"]) if row["pdf_page"] else None
        sources[source_id] = SourceReference(
            source_id=source_id.lower().replace(".", "-"),
            document=row["source_snapshot_file"],
            fiscal_year=int(row["fiscal_year"]),
            field="locked_snapshot_row",
            source_unit="mixed_explicit_units",
            method="reported",
            source_uri=row["source_document"],
            document_sha256=row["source_snapshot_sha256"],
            page=page,
        )
    return sources


def _load_metrics(
    path: Path,
    sources: dict[str, SourceReference],
) -> list[MetricValue]:
    rows = _read_csv(path)
    metrics: list[MetricValue] = []
    seen: set[str] = set()
    for row in rows:
        metric_id = row["metric_id"]
        if metric_id in seen:
            raise EquityValidationError(f"Duplicate Equity metric ID: {metric_id}")
        seen.add(metric_id)
        ticker = row["ticker"]
        if ticker not in COMPANY_IDS:
            raise EquityValidationError(f"Unexpected Equity ticker in fixture: {ticker}")
        source_row = sources.get(row["source_id"])
        if source_row is None:
            raise EquityValidationError(f"Unknown Equity source ID: {row['source_id']}")
        status = row["status"]
        if status not in {"reported", "calculated", "unavailable", "not_comparable"}:
            raise EquityValidationError(f"Unexpected Equity metric status: {status}")
        try:
            value = Decimal(row["value"]) if row["value"] else None
        except InvalidOperation as error:
            raise EquityValidationError(f"Invalid Equity numeric value: {metric_id}") from error
        formula = None
        input_metric_ids: tuple[str, ...] = ()
        if status == "calculated":
            if row["formula_version"] != "equity-formulas.v1":
                raise EquityValidationError(f"Unexpected formula version: {metric_id}")
            formula = Formula(
                formula_id=row["formula_id"],
                expression=row["formula_expression"],
                version=row["formula_version"],
            )
            input_metric_ids = tuple(filter(None, row["input_metric_ids"].split(";")))
        source = SourceReference(
            source_id=f"{source_row.source_id}-{row['source_field'].replace('_', '-')}",
            document=source_row.document,
            fiscal_year=source_row.fiscal_year,
            field=row["source_field"],
            source_unit=row["unit"],
            method="calculated" if status == "calculated" else "reported",
            source_uri=source_row.source_uri,
            document_sha256=source_row.document_sha256,
            page=source_row.page,
        )
        metrics.append(
            MetricValue(
                metric_id=metric_id,
                company_id=COMPANY_IDS[ticker],
                fiscal_year=int(row["fiscal_year"]),
                name=row["metric_name"],
                value=value,
                unit=row["unit"],
                status=status,
                sources=(source,),
                formula=formula,
                input_metric_ids=input_metric_ids,
                note=row["note"] or None,
            )
        )
    return metrics


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise EquityValidationError(f"Embedded Equity fixture is missing: {path.name}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (UnicodeDecodeError, csv.Error) as error:
        raise EquityValidationError(f"Embedded Equity CSV is invalid: {path.name}") from error
