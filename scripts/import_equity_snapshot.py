"""Build minimal offline Equity fixtures from locally copied, locked SED artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SOURCE_FILES = {
    "BANB.SW": {
        "csv": "BANB.SW_2015_2025_locked_snapshot_v1.csv",
        "json": "BANB.SW_2015_2025_locked_snapshot_v1.json",
    },
    "SFZN.SW": {
        "csv": "SFZN.SW_2015_2025_locked_snapshot_v1.csv",
        "json": "SFZN.SW_2015_2025_locked_snapshot_v1.json",
    },
}
SFZN_AUTHORITY_REPORTS = (
    "SFZN.SW_phase_6A_locked_snapshot_creation_report.md",
    "SFZN.SW_phase_6B_regression_protection_report.md",
    "SFZN.SW_phase_7B_product_data_v2_promotion_report.md",
)
SFZN_LOCKED_PATHS = (
    "snapshots/locked/SFZN.SW/v1/SFZN.SW_2015_2025_locked_snapshot_v1.csv",
    "snapshots/locked/SFZN.SW/v1/SFZN.SW_2015_2025_locked_snapshot_v1.json",
)
COMPANY_NAMES = {
    "BANB.SW": "Bachem Holding AG",
    "SFZN.SW": "Siegfried Holding AG",
}
EXPECTED_YEARS = tuple(range(2021, 2026))
FIXTURE_SCHEMA_VERSION = "equity-fundamentals.v1"
MANIFEST_SCHEMA_VERSION = "equity-snapshot-manifest.v1"
AUTHORITY_SCHEMA_VERSION = "sed-locked-authority-chain.v1"
VALUATION_DIAGNOSTIC_VERSION = "equity-valuation-diagnostic.v1"
FORMULA_VERSION = "equity-formulas.v1"


@dataclass(frozen=True, slots=True)
class MetricProjection:
    source_fields: tuple[str, ...]
    metric_name: str
    unit: str
    default_method: str = "reported"


METRICS = (
    MetricProjection(("revenue",), "revenue", "CHF_millions"),
    MetricProjection(("ebit",), "ebit", "CHF_millions"),
    MetricProjection(("depreciation_amortization", "da"), "depreciation_amortization", "CHF_millions"),
    MetricProjection(("ebitda",), "ebitda", "CHF_millions"),
    MetricProjection(("net_income",), "net_income", "CHF_millions"),
    MetricProjection(("eps", "eps_basic"), "eps_basic", "CHF_per_share"),
    MetricProjection(("dividend_per_share",), "dividend_per_share", "CHF_per_share"),
    MetricProjection(("total_assets",), "total_assets", "CHF_millions"),
    MetricProjection(("current_assets",), "current_assets", "CHF_millions"),
    MetricProjection(("total_equity",), "total_equity", "CHF_millions"),
    MetricProjection(("total_liabilities",), "total_liabilities", "CHF_millions"),
    MetricProjection(("current_liabilities",), "current_liabilities", "CHF_millions"),
    MetricProjection(("cash",), "cash", "CHF_millions"),
    MetricProjection(("total_debt",), "total_debt", "CHF_millions"),
    MetricProjection(("operating_cash_flow", "operating_cf"), "operating_cash_flow", "CHF_millions"),
    MetricProjection(("capex_reported",), "capex_reported", "CHF_millions"),
    MetricProjection(("capex_calculated",), "capex_calculated", "CHF_millions", "calculated"),
    MetricProjection(("free_cash_flow_reported",), "free_cash_flow_reported", "CHF_millions"),
    MetricProjection(
        ("free_cash_flow_calculated",),
        "free_cash_flow_calculated",
        "CHF_millions",
        "calculated",
    ),
    MetricProjection(("equity_ratio_pct",), "equity_ratio", "percent", "calculated"),
    MetricProjection(("year_end_share_price",), "year_end_share_price", "CHF_per_share"),
    MetricProjection(("shares_outstanding", "registered_shares"), "registered_shares", "shares"),
    MetricProjection(("market_cap", "market_capitalization_published"), "market_capitalization_published", "CHF_millions"),
    MetricProjection(("pe_published",), "price_to_earnings_published", "multiple"),
)
MARKET_METRICS = (
    "year_end_share_price",
    "registered_shares",
    "market_capitalization_published",
    "price_to_earnings_published",
)
FORMULAS = {
    "ebitda": "ebit-plus-depreciation-amortization",
    "capex_calculated": "cash-flow-capex",
    "free_cash_flow_calculated": "free-cash-flow-signed-capex",
    "equity_ratio_pct": "period-end-equity-to-total-assets",
}
FORMULA_EXPRESSIONS = {
    "ebitda": "ebit + depreciation_amortization",
    "capex_calculated": "sum(signed_cash_flow_capex_lines)",
    "free_cash_flow_calculated": "operating_cash_flow + signed_capex",
    "equity_ratio_pct": "total_equity / total_assets * 100",
}
FORMULA_INPUT_FIELDS = {
    "ebitda": ("ebit", "depreciation_amortization"),
    "capex_calculated": ("cash_flow_investment_lines",),
    "free_cash_flow_calculated": ("operating_cash_flow", "capex_calculated"),
    "equity_ratio_pct": ("total_equity", "total_assets"),
}


class SnapshotImportError(ValueError):
    """Raised before any output is written when source validation fails."""


@dataclass(frozen=True, slots=True)
class AuthorityEvidence:
    mode: str
    reports: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    ticker: str
    csv_path: Path
    csv_sha256: str
    json_path: Path
    json_sha256: str
    payload: dict[str, Any]
    rows: tuple[dict[str, str], ...]
    authority: AuthorityEvidence


def load_sources(source_dir: Path) -> tuple[SourceSnapshot, ...]:
    """Load both locked CSVs and validate their JSON metadata and authority chain."""

    snapshots: list[SourceSnapshot] = []
    errors: list[str] = []
    for ticker, filenames in SOURCE_FILES.items():
        csv_path = source_dir / filenames["csv"]
        json_path = source_dir / filenames["json"]
        missing = [path.name for path in (csv_path, json_path) if not path.is_file()]
        if missing:
            errors.append(f"{ticker}: missing source artifacts {missing}")
            continue
        csv_raw = csv_path.read_bytes()
        json_raw = json_path.read_bytes()
        csv_sha256 = hashlib.sha256(csv_raw).hexdigest()
        json_sha256 = hashlib.sha256(json_raw).hexdigest()
        try:
            payload = json.loads(json_raw)
        except json.JSONDecodeError as error:
            errors.append(f"{json_path.name}: invalid JSON ({error.msg})")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{json_path.name}: top-level JSON value must be an object")
            continue
        if payload.get("ticker") != ticker:
            errors.append(f"{json_path.name}: ticker does not match {ticker}")
        try:
            csv_rows = tuple(csv.DictReader(io.StringIO(csv_raw.decode("utf-8"))))
        except (UnicodeDecodeError, csv.Error) as error:
            errors.append(f"{csv_path.name}: invalid UTF-8 CSV ({error})")
            continue
        if not csv_rows:
            errors.append(f"{csv_path.name}: CSV contains no data rows")
            continue
        authority: AuthorityEvidence | None = None
        if _is_locked(payload):
            authority = AuthorityEvidence(mode="internal_locked_snapshot")
        elif ticker == "SFZN.SW":
            try:
                authority = _validate_sfzn_authority_chain(
                    source_dir,
                    csv_sha256=csv_sha256,
                    json_sha256=json_sha256,
                )
            except SnapshotImportError as error:
                errors.extend(str(error).splitlines())
        else:
            status = _artifact_status(payload)
            errors.append(f"{json_path.name}: internal artifact status is not locked ({status})")
        if ticker == "BANB.SW":
            if any(row.get("validation_status") != "locked_snapshot" for row in csv_rows):
                errors.append(f"{csv_path.name}: every row must have validation_status=locked_snapshot")
            declared_rows = payload.get("row_count")
            if declared_rows != len(csv_rows):
                errors.append(
                    f"{csv_path.name}: row count {len(csv_rows)} differs from JSON declaration "
                    f"{declared_rows}"
                )
        json_rows = payload.get("rows")
        if isinstance(json_rows, list) and tuple(json_rows) != csv_rows:
            errors.append(f"{ticker}: local JSON rows and locked CSV rows differ")
        selected, row_errors = _select_rows(ticker, csv_path.name, list(csv_rows))
        errors.extend(row_errors)
        if authority is not None:
            snapshots.append(
                SourceSnapshot(
                    ticker=ticker,
                    csv_path=csv_path,
                    csv_sha256=csv_sha256,
                    json_path=json_path,
                    json_sha256=json_sha256,
                    payload=payload,
                    rows=selected,
                    authority=authority,
                )
            )
    if errors:
        raise SnapshotImportError("Source preflight failed:\n- " + "\n- ".join(errors))
    if {snapshot.ticker for snapshot in snapshots} != set(SOURCE_FILES):
        raise SnapshotImportError("Source preflight failed: both required tickers are mandatory.")
    return tuple(sorted(snapshots, key=lambda item: item.ticker))


def build_fixtures(
    source_dir: Path,
    output_dir: Path,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Validate every source first, then atomically write derived offline fixtures."""

    snapshots = load_sources(source_dir)
    timestamp = generated_at or datetime.now(UTC).replace(microsecond=0)
    if timestamp.tzinfo is None:
        raise SnapshotImportError("generated_at must be timezone-aware.")
    fundamentals, sources, missing_values, caveats = _project(snapshots)
    valuation_diagnostic = _valuation_diagnostic(fundamentals)
    output_payloads = {
        "cdmo_fundamentals.v1.csv": _csv_bytes(fundamentals),
        "cdmo_sources.v1.csv": _csv_bytes(sources),
        "valuation_diagnostic.v1.json": _json_bytes(valuation_diagnostic),
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
        "authority_schema_version": AUTHORITY_SCHEMA_VERSION,
        "formula_version": FORMULA_VERSION,
        "generated_at": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "runtime_external_dependency": False,
        "tickers": list(SOURCE_FILES),
        "periods": list(EXPECTED_YEARS),
        "gates": {
            "fundamentals": "pass",
            "comparative_valuation": "blocked",
        },
        "sources": [_manifest_source(snapshot) for snapshot in snapshots],
        "outputs": [
            {"file": name, "sha256": hashlib.sha256(payload).hexdigest()}
            for name, payload in output_payloads.items()
        ],
        "fields": [{"name": item.metric_name, "unit": item.unit} for item in METRICS],
        "missing_values": missing_values,
        "caveats": caveats,
    }
    output_payloads["manifest.v1.json"] = _json_bytes(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in output_payloads.items():
        temporary = output_dir / f".{name}.tmp"
        temporary.write_bytes(payload)
        os.replace(temporary, output_dir / name)
    return manifest


def _validate_sfzn_authority_chain(
    source_dir: Path,
    *,
    csv_sha256: str,
    json_sha256: str,
) -> AuthorityEvidence:
    errors: list[str] = []
    texts: dict[str, str] = {}
    report_hashes: list[tuple[str, str]] = []
    for filename in SFZN_AUTHORITY_REPORTS:
        path = source_dir / filename
        if not path.is_file():
            errors.append(f"{filename}: required authority report is missing")
            continue
        raw = path.read_bytes()
        try:
            texts[filename] = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{filename}: report is not valid UTF-8")
            continue
        report_hashes.append((filename, hashlib.sha256(raw).hexdigest()))
    if errors:
        raise SnapshotImportError("\n".join(errors))

    locked_csv, locked_json = SFZN_LOCKED_PATHS
    phase6a = texts[SFZN_AUTHORITY_REPORTS[0]]
    phase6b = texts[SFZN_AUTHORITY_REPORTS[1]]
    phase7b = texts[SFZN_AUTHORITY_REPORTS[2]]
    _require_report_phrases(
        SFZN_AUTHORITY_REPORTS[0],
        phase6a,
        (
            locked_csv,
            locked_json,
            f"Candidate CSV SHA-256: `{csv_sha256}`",
            f"Locked CSV SHA-256: `{csv_sha256}`",
            f"Candidate JSON SHA-256: `{json_sha256}`",
            f"Locked JSON SHA-256: `{json_sha256}`",
            "copied byte-for-byte into the locked snapshot version",
            "`cmp` checks returned exit code 0",
            "## Final Phase Decision\n\nGO",
        ),
        errors,
    )
    _require_report_phrases(
        SFZN_AUTHORITY_REPORTS[1],
        phase6b,
        (
            locked_csv,
            locked_json,
            f"both equal `{csv_sha256}`",
            f"both equal `{json_sha256}`",
            "Cell-level drift count: 0",
            "No row drift, schema drift, formula drift, currency drift, unit drift, or provenance drift",
            "## Final Phase Decision\n\nGO",
        ),
        errors,
    )
    required_pass_checks = (
        "Artifact presence",
        "Byte-level CSV comparison",
        "Byte-level JSON comparison",
        "Row drift",
        "Schema drift",
        "Formula drift",
        "Currency and unit drift",
        "Provenance drift",
    )
    for check in required_pass_checks:
        if re.search(rf"\|\s*{re.escape(check)}\s*\|\s*PASS\s*\|", phase6b) is None:
            errors.append(f"{SFZN_AUTHORITY_REPORTS[1]}: missing PASS for {check}")
    _require_report_phrases(
        SFZN_AUTHORITY_REPORTS[2],
        phase7b,
        (
            locked_csv,
            locked_json,
            "protocol_status=full_v2_locked_snapshot",
            "No market data was invented.",
            "`python scripts/check_product_data_v2.py`: PASS",
        ),
        errors,
    )
    if errors:
        raise SnapshotImportError("\n".join(errors))
    return AuthorityEvidence(
        mode="external_verified_lock_and_promotion_chain",
        reports=tuple(sorted(report_hashes)),
    )


def _require_report_phrases(
    filename: str,
    text: str,
    phrases: tuple[str, ...],
    errors: list[str],
) -> None:
    for phrase in phrases:
        if phrase not in text:
            errors.append(f"{filename}: required evidence is missing: {phrase}")


def _select_rows(
    ticker: str,
    filename: str,
    rows: list[dict[str, str]],
) -> tuple[tuple[dict[str, str], ...], list[str]]:
    selected: dict[int, dict[str, str]] = {}
    errors: list[str] = []
    for row in rows:
        raw_year = row.get("year") or row.get("fiscal_year")
        try:
            year = int(raw_year or "")
        except ValueError:
            errors.append(f"{filename}: row has invalid year {raw_year!r}")
            continue
        if year not in EXPECTED_YEARS:
            continue
        if row.get("ticker") != ticker:
            errors.append(f"{filename}: FY{year} row ticker does not match {ticker}")
        if year in selected:
            errors.append(f"{filename}: duplicate FY{year} row")
        selected[year] = row
    missing_years = [year for year in EXPECTED_YEARS if year not in selected]
    if missing_years:
        errors.append(f"{filename}: missing fiscal years {missing_years}")
    return tuple(selected[year] for year in EXPECTED_YEARS if year in selected), errors


def _project(
    snapshots: tuple[SourceSnapshot, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    fundamentals: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    missing_values: list[dict[str, Any]] = []
    caveats = {
        "Source snapshots do not provide PDF page numbers; page-level provenance is unavailable.",
        "Comparative valuation remains blocked until Siegfried market fields are source-validated.",
    }
    for snapshot in snapshots:
        company_name = str(snapshot.payload.get("company_name", COMPANY_NAMES[snapshot.ticker]))
        for row in snapshot.rows:
            year = int(row.get("year") or row.get("fiscal_year") or "")
            source_id = f"{snapshot.ticker}-{year}"
            sources.append(
                {
                    "source_id": source_id,
                    "ticker": snapshot.ticker,
                    "company_name": company_name,
                    "fiscal_year": year,
                    "source_snapshot_file": snapshot.csv_path.name,
                    "source_snapshot_sha256": snapshot.csv_sha256,
                    "source_metadata_file": snapshot.json_path.name,
                    "source_metadata_sha256": snapshot.json_sha256,
                    "authority_mode": snapshot.authority.mode,
                    "source_document": row.get("source_file") or f"{company_name} Annual Report {year}",
                    "pdf_page": "",
                    "row_status": row.get("validation_status") or row.get("candidate_row_status") or row.get("status", ""),
                    "validation_phase": row.get("validation_phase", ""),
                    "validation_report": row.get("validation_report", ""),
                    "source_note": row.get("source_note") or row.get("source_caveats", ""),
                    "formula_note": row.get("formula_note") or row.get("notes", ""),
                }
            )
            for projection in METRICS:
                source_field = _source_field(projection, row)
                raw_value = row.get(source_field) if source_field else None
                method = _metric_method(projection, row)
                if raw_value in (None, ""):
                    status = "unavailable"
                    value = ""
                    method = ""
                    note = _missing_note(projection, row)
                    missing_values.append(
                        {
                            "ticker": snapshot.ticker,
                            "fiscal_year": year,
                            "field": projection.metric_name,
                            "reason": note,
                        }
                    )
                else:
                    try:
                        Decimal(str(raw_value))
                    except InvalidOperation as error:
                        raise SnapshotImportError(
                            f"{snapshot.csv_path.name}: FY{year} {source_field} is not numeric"
                        ) from error
                    status = method
                    value = str(raw_value)
                    note = (
                        row.get("formula_note") or row.get("notes", "")
                        if method == "calculated"
                        else ""
                    )
                fundamentals.append(
                    {
                        "metric_id": _metric_id(snapshot.ticker, year, projection.metric_name),
                        "ticker": snapshot.ticker,
                        "company_name": company_name,
                        "fiscal_year": year,
                        "metric_name": projection.metric_name,
                        "value": value,
                        "unit": projection.unit,
                        "status": status,
                        "formula_id": (
                            FORMULAS.get(source_field, "") if method == "calculated" else ""
                        ),
                        "formula_expression": (
                            FORMULA_EXPRESSIONS.get(source_field, "")
                            if method == "calculated"
                            else ""
                        ),
                        "formula_version": FORMULA_VERSION if method == "calculated" else "",
                        "input_metric_ids": (
                            ";".join(
                                _metric_id(snapshot.ticker, year, field)
                                for field in FORMULA_INPUT_FIELDS.get(source_field, ())
                            )
                            if method == "calculated"
                            else ""
                        ),
                        "source_id": source_id,
                        "source_field": source_field,
                        "note": note,
                    }
                )
            for label in ("source_note", "source_caveats", "split_caveats"):
                note = str(row.get(label, "")).strip()
                if note:
                    caveats.add(f"{snapshot.ticker} FY{year}: {note}")
        for label in ("split_caveats", "notes"):
            for caveat in snapshot.payload.get(label, []):
                caveats.add(str(caveat))
    return fundamentals, sources, missing_values, sorted(caveats)


def _valuation_diagnostic(fundamentals: list[dict[str, Any]]) -> dict[str, Any]:
    coverage: dict[str, dict[str, list[int]]] = {}
    for ticker in SOURCE_FILES:
        coverage[ticker] = {}
        for field in MARKET_METRICS:
            coverage[ticker][field] = sorted(
                int(row["fiscal_year"])
                for row in fundamentals
                if row["ticker"] == ticker
                and row["metric_name"] == field
                and row["status"] in {"reported", "calculated"}
            )
    blocked = {
        ticker: [field for field, years in fields.items() if years != list(EXPECTED_YEARS)]
        for ticker, fields in coverage.items()
    }
    return {
        "schema_version": VALUATION_DIAGNOSTIC_VERSION,
        "status": "fundamentals_ready_comparative_valuation_blocked",
        "periods": list(EXPECTED_YEARS),
        "market_field_coverage": coverage,
        "blocked_columns": blocked,
        "blocking_reason": (
            "Siegfried locked FY2021–FY2025 rows contain no closing share price, registered "
            "shares, published market capitalization, or published P/E. Missing values were "
            "not inferred or backfilled."
        ),
        "phase_readiness": {
            "phase_2_fundamentals_snapshot": "ready",
            "phase_3_fundamentals_engine": "ready",
            "phase_4_snapshot_and_fundamentals_tabs": "ready",
            "phase_4_bachem_historical_valuation": "partially_ready",
            "phase_4_comparative_valuation": "blocked",
        },
    }


def _manifest_source(snapshot: SourceSnapshot) -> dict[str, Any]:
    return {
        "ticker": snapshot.ticker,
        "csv": {"file": snapshot.csv_path.name, "sha256": snapshot.csv_sha256},
        "json": {"file": snapshot.json_path.name, "sha256": snapshot.json_sha256},
        "source_schema_version": (
            "v1" if snapshot.authority.mode == "external_verified_lock_and_promotion_chain"
            else _source_schema_version(snapshot.payload)
        ),
        "internal_artifact_status": _artifact_status(snapshot.payload),
        "authority": {
            "mode": snapshot.authority.mode,
            "documented_locked_paths": (
                list(SFZN_LOCKED_PATHS) if snapshot.ticker == "SFZN.SW" else []
            ),
            "reports": [
                {"file": filename, "sha256": sha256}
                for filename, sha256 in snapshot.authority.reports
            ],
        },
    }


def _source_field(projection: MetricProjection, row: dict[str, str]) -> str:
    return next((field for field in projection.source_fields if field in row), projection.source_fields[0])


def _metric_id(ticker: str, year: int, metric_name: str) -> str:
    return (
        f"{ticker.lower().replace('.', '-')}-{year}-"
        f"{metric_name.replace('_', '-')}"
    )


def _metric_method(projection: MetricProjection, row: dict[str, str]) -> str:
    if projection.metric_name != "ebitda":
        return projection.default_method
    notes = f"{row.get('source_note', '')} {row.get('formula_note', '')}".lower()
    return "calculated" if "ebitda calculated" in notes or "ebitda = ebit + da" in notes else "reported"


def _missing_note(projection: MetricProjection, row: dict[str, str]) -> str:
    if projection.metric_name in MARKET_METRICS:
        return str(row.get("valuation_status") or "market field absent from locked source")
    declared = set(filter(None, row.get("missing_fields", "").split(";")))
    if any(field in declared for field in projection.source_fields):
        return "documented missing in locked source"
    return str(row.get("missing_reason") or "field absent from locked source schema")


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        raise SnapshotImportError("Cannot serialize an empty fixture.")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _is_locked(payload: dict[str, Any]) -> bool:
    return (
        payload.get("locked") is True
        or payload.get("validation_status") == "locked_snapshot"
        or payload.get("artifact_type") == "locked_snapshot"
    )


def _artifact_status(payload: dict[str, Any]) -> str:
    if payload.get("locked") is True:
        return str(payload.get("validation_status", "locked"))
    return str(payload.get("artifact_type") or payload.get("validation_status") or "unknown")


def _source_schema_version(payload: dict[str, Any]) -> str:
    return str(payload.get("snapshot_version") or payload.get("schema_version") or "unversioned")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src/ai_quant/fixtures/equity",
    )
    parser.add_argument(
        "--generated-at",
        type=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
    )
    args = parser.parse_args()
    try:
        manifest = build_fixtures(args.source_dir, args.output_dir, generated_at=args.generated_at)
    except SnapshotImportError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(
        f"Equity fundamentals generated for {len(manifest['tickers'])} tickers; "
        f"comparative valuation gate: {manifest['gates']['comparative_valuation']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
