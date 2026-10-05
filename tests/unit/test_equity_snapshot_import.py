from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "import_equity_snapshot.py"
SPEC = importlib.util.spec_from_file_location("import_equity_snapshot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SnapshotImportError = MODULE.SnapshotImportError
build_fixtures = MODULE.build_fixtures
load_sources = MODULE.load_sources


def row(ticker: str, year: int) -> dict[str, str]:
    return {
        "ticker": ticker,
        "year": str(year),
        "source_file": f"{ticker}_{year}.pdf",
        "candidate_row_status": "validated",
        "validation_status": "locked_snapshot",
        "validation_phase": "test",
        "validation_report": f"reports/{ticker}_{year}.md",
        "source_note": "Validated test row.",
        "formula_note": (
            "ebitda = ebit + da; free_cash_flow_calculated = operating_cf + "
            "capex_calculated; equity_ratio_pct = total_equity / total_assets."
        ),
        "valuation_status": "missing_source_unavailable",
        "revenue": "100",
        "ebit": "20",
        "da": "5",
        "ebitda": "25",
        "net_income": "15",
        "eps_basic": "2.5",
        "dividend_per_share": "0.5",
        "total_assets": "300",
        "current_assets": "100",
        "total_equity": "180",
        "total_liabilities": "120",
        "current_liabilities": "60",
        "cash": "30",
        "total_debt": "50",
        "operating_cf": "40",
        "capex_reported": "10",
        "capex_calculated": "-10",
        "free_cash_flow_reported": "30",
        "free_cash_flow_calculated": "30",
        "equity_ratio_pct": "60",
    }


def write_source(directory: Path, ticker: str, *, locked: bool) -> tuple[str, str]:
    rows = [row(ticker, year) for year in range(2015, 2026)]
    csv_path = directory / MODULE.SOURCE_FILES[ticker]["csv"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    payload: dict[str, object] = {
        "ticker": ticker,
        "company_name": MODULE.COMPANY_NAMES[ticker],
        "snapshot_version": "v1",
        "row_count": 11,
        "locked": locked,
        "validation_status": "locked_snapshot" if locked else "candidate",
        "artifact_type": "locked_snapshot" if locked else "candidate_snapshot_for_review",
    }
    if not locked:
        payload["rows"] = rows
    json_path = directory / MODULE.SOURCE_FILES[ticker]["json"]
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    return hashlib.sha256(csv_path.read_bytes()).hexdigest(), hashlib.sha256(json_path.read_bytes()).hexdigest()


def write_sfzn_authority(directory: Path, csv_sha256: str, json_sha256: str) -> None:
    locked_csv, locked_json = MODULE.SFZN_LOCKED_PATHS
    (directory / MODULE.SFZN_AUTHORITY_REPORTS[0]).write_text(
        f"""# Phase 6A
{locked_csv}
{locked_json}
Candidate CSV SHA-256: `{csv_sha256}`
Locked CSV SHA-256: `{csv_sha256}`
Candidate JSON SHA-256: `{json_sha256}`
Locked JSON SHA-256: `{json_sha256}`
copied byte-for-byte into the locked snapshot version
`cmp` checks returned exit code 0
## Final Phase Decision

GO
""",
        encoding="utf-8",
    )
    checks = "\n".join(
        f"| {name} | PASS | evidence |"
        for name in (
            "Artifact presence",
            "Byte-level CSV comparison",
            "Byte-level JSON comparison",
            "Row drift",
            "Schema drift",
            "Formula drift",
            "Currency and unit drift",
            "Provenance drift",
        )
    )
    (directory / MODULE.SFZN_AUTHORITY_REPORTS[1]).write_text(
        f"""# Phase 6B
{locked_csv}
{locked_json}
CSV hashes both equal `{csv_sha256}`
JSON hashes both equal `{json_sha256}`
Cell-level drift count: 0
{checks}
No row drift, schema drift, formula drift, currency drift, unit drift, or provenance drift
## Final Phase Decision

GO
""",
        encoding="utf-8",
    )
    (directory / MODULE.SFZN_AUTHORITY_REPORTS[2]).write_text(
        f"""# Phase 7B product_data_v2
{locked_csv}
{locked_json}
protocol_status=full_v2_locked_snapshot
No market data was invented.
`python scripts/check_product_data_v2.py`: PASS
""",
        encoding="utf-8",
    )


def source_set(directory: Path, *, with_authority: bool = True) -> None:
    write_source(directory, "BANB.SW", locked=True)
    csv_sha, json_sha = write_source(directory, "SFZN.SW", locked=False)
    if with_authority:
        write_sfzn_authority(directory, csv_sha, json_sha)


def test_candidate_is_rejected_without_complete_external_authority(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_set(source_dir, with_authority=False)

    with pytest.raises(SnapshotImportError, match="required authority report is missing"):
        load_sources(source_dir)


def test_authority_chain_fails_closed_on_hash_mismatch(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_set(source_dir)
    phase6a = source_dir / MODULE.SFZN_AUTHORITY_REPORTS[0]
    phase6a.write_text(phase6a.read_text().replace("Candidate CSV SHA-256", "Old CSV SHA-256"))

    with pytest.raises(SnapshotImportError, match="required evidence is missing"):
        load_sources(source_dir)


def test_import_projects_fundamentals_and_records_authority_hashes(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_set(source_dir)
    output_dir = tmp_path / "output"

    manifest = build_fixtures(
        source_dir,
        output_dir,
        generated_at=datetime(2026, 10, 5, 12, 0, tzinfo=UTC),
    )

    assert manifest["tickers"] == ["BANB.SW", "SFZN.SW"]
    assert manifest["periods"] == [2021, 2022, 2023, 2024, 2025]
    assert manifest["runtime_external_dependency"] is False
    assert manifest["gates"] == {
        "fundamentals": "pass",
        "comparative_valuation": "blocked",
    }
    sfzn = next(item for item in manifest["sources"] if item["ticker"] == "SFZN.SW")
    assert sfzn["authority"]["mode"] == "external_verified_lock_and_promotion_chain"
    assert sfzn["authority"]["documented_locked_paths"] == list(MODULE.SFZN_LOCKED_PATHS)
    assert len(sfzn["authority"]["reports"]) == 3
    assert all(len(item["sha256"]) == 64 for item in sfzn["authority"]["reports"])
    assert {item["file"] for item in manifest["outputs"]} == {
        "cdmo_fundamentals.v1.csv",
        "cdmo_sources.v1.csv",
        "valuation_diagnostic.v1.json",
    }

    with (output_dir / "cdmo_fundamentals.v1.csv").open(newline="") as handle:
        fundamentals = list(csv.DictReader(handle))
    with (output_dir / "cdmo_sources.v1.csv").open(newline="") as handle:
        sources = list(csv.DictReader(handle))
    assert len(fundamentals) == 2 * 5 * len(MODULE.METRICS)
    assert len(sources) == 10
    ebitda = next(item for item in fundamentals if item["metric_name"] == "ebitda")
    revenue = next(item for item in fundamentals if item["metric_name"] == "revenue")
    assert ebitda["status"] == "calculated"
    assert ebitda["formula_version"] == "equity-formulas.v1"
    assert revenue["status"] == "reported"


def test_valuation_diagnostic_is_precise_and_does_not_backfill(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_set(source_dir)
    output_dir = tmp_path / "output"
    build_fixtures(source_dir, output_dir)

    diagnostic = json.loads((output_dir / "valuation_diagnostic.v1.json").read_text())
    assert diagnostic["status"] == "fundamentals_ready_comparative_valuation_blocked"
    assert diagnostic["blocked_columns"]["SFZN.SW"] == list(MODULE.MARKET_METRICS)
    assert diagnostic["phase_readiness"]["phase_3_fundamentals_engine"] == "ready"
    assert diagnostic["phase_readiness"]["phase_4_comparative_valuation"] == "blocked"


def test_import_is_deterministic_for_same_inputs_and_generation_time(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_set(source_dir)
    timestamp = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_fixtures(source_dir, first, generated_at=timestamp)
    build_fixtures(source_dir, second, generated_at=timestamp)

    for filename in (
        "cdmo_fundamentals.v1.csv",
        "cdmo_sources.v1.csv",
        "valuation_diagnostic.v1.json",
        "manifest.v1.json",
    ):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
