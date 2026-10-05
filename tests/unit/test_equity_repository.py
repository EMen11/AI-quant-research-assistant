from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from ai_quant.equity import EquityValidationError, load_equity_repository
from ai_quant.equity.repository import FIXTURE_DIR


def test_embedded_repository_loads_exact_universe_without_external_dependency() -> None:
    repository = load_equity_repository()

    assert len(repository.metrics) == 240
    assert repository.manifest["runtime_external_dependency"] is False
    assert repository.manifest["gates"]["fundamentals"] == "pass"
    assert repository.manifest["gates"]["comparative_valuation"] == "blocked"


def test_repository_preserves_reported_calculated_and_unavailable_statuses() -> None:
    repository = load_equity_repository()

    bachem_revenue = repository.metric("BANB.SW", 2025, "revenue")
    siegfried_ebitda = repository.metric("SFZN.SW", 2025, "ebitda")
    siegfried_market_cap = repository.metric(
        "SFZN.SW", 2025, "market_capitalization_published"
    )

    assert bachem_revenue.status == "reported"
    assert bachem_revenue.value == Decimal("695.070")
    assert siegfried_ebitda.status == "calculated"
    assert siegfried_ebitda.value == Decimal("318.5")
    assert siegfried_ebitda.formula.version == "equity-formulas.v1"
    assert siegfried_market_cap.status == "unavailable"
    assert siegfried_market_cap.value is None


def test_siegfried_authority_chain_and_hashes_are_available_at_runtime() -> None:
    repository = load_equity_repository()
    source = next(item for item in repository.manifest["sources"] if item["ticker"] == "SFZN.SW")

    assert source["authority"]["mode"] == "external_verified_lock_and_promotion_chain"
    assert len(source["authority"]["reports"]) == 3
    assert source["source_schema_version"] == "v1"
    assert repository.valuation_diagnostic["blocked_columns"]["SFZN.SW"] == [
        "year_end_share_price",
        "registered_shares",
        "market_capitalization_published",
        "price_to_earnings_published",
    ]


def test_repository_fails_closed_when_embedded_fixture_hash_changes(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "equity"
    shutil.copytree(FIXTURE_DIR, fixture_dir)
    fundamentals = fixture_dir / "cdmo_fundamentals.v1.csv"
    fundamentals.write_bytes(fundamentals.read_bytes() + b"\n")

    with pytest.raises(EquityValidationError, match="hash mismatch"):
        load_equity_repository(fixture_dir)
