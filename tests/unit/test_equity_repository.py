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
    assert repository.manifest["source_repository"]["identifier"] == "SED/pdf.extractor"
    assert repository.manifest["source_repository"]["commit_sha"] == (
        "bc1c54eefd663a257aab71e58fd7953a6239a1fc"
    )
    assert repository.manifest["gates"]["fundamentals"] == "pass"
    assert repository.manifest["gates"]["comparative_valuation"] == "pass"


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
    assert siegfried_market_cap.status == "reported"
    assert siegfried_market_cap.value == Decimal("3268")


def test_siegfried_authority_chain_and_hashes_are_available_at_runtime() -> None:
    repository = load_equity_repository()
    source = next(item for item in repository.manifest["sources"] if item["ticker"] == "SFZN.SW")

    assert source["authority"]["mode"] == "external_verified_lock_and_promotion_chain"
    assert len(source["authority"]["reports"]) == 3
    assert source["source_schema_version"] == "v2"
    assert repository.valuation_diagnostic["blocked_columns"]["SFZN.SW"] == []
    assert repository.valuation_diagnostic["remaining_source_limitations"] == {
        "BANB.SW": ["price_to_earnings_published"]
    }


def test_market_fixture_coverage_and_published_value_precedence() -> None:
    repository = load_equity_repository()

    expected = {
        2021: ("89.0", "43960000", "3745", "41"),
        2022: ("61.4", "44320000", "2584", "21"),
        2023: ("86.0", "44680000", "3648", "29"),
        2024: ("98.6", "45130000", "4306", "27"),
        2025: ("74.6", "45230000", "3268", "20"),
    }
    names = (
        "year_end_share_price",
        "registered_shares",
        "market_capitalization_published",
        "price_to_earnings_published",
    )
    for year, values in expected.items():
        for name, value in zip(names, values, strict=True):
            metric = repository.metric("SFZN.SW", year, name)
            assert metric.status == "reported"
            assert metric.value == Decimal(value)
        assert repository.metric(
            "BANB.SW", year, "price_to_earnings_published"
        ).status == "unavailable"

    split_rule = repository.manifest["split_rules"]["SFZN.SW"]
    assert split_rule["runtime_basis"] == "issuer_published_2025_post_split_comparative"
    assert split_rule["native_and_recalculated_values_preserved_in_source"] is True
    assert split_rule["published_market_capitalization_precedence"] is True


def test_repository_fails_closed_when_embedded_fixture_hash_changes(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "equity"
    shutil.copytree(FIXTURE_DIR, fixture_dir)
    fundamentals = fixture_dir / "cdmo_fundamentals.v1.csv"
    fundamentals.write_bytes(fundamentals.read_bytes() + b"\n")

    with pytest.raises(EquityValidationError, match="hash mismatch"):
        load_equity_repository(fixture_dir)
