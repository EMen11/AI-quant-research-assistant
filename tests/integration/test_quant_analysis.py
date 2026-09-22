import socket
from dataclasses import replace

import pytest

from ai_quant.market_data import FrozenSnapshotProvider, MarketDataError, SnapshotRun
from ai_quant.quant import (
    OptimizationConstraints,
    analyze_portfolio,
    demo_portfolio,
    demo_risk_free_rate,
)


def test_two_runs_on_same_frozen_snapshot_are_deterministic() -> None:
    first = analyze_portfolio(
        demo_portfolio(), SnapshotRun(FrozenSnapshotProvider.demo()), demo_risk_free_rate()
    )
    second = analyze_portfolio(
        demo_portfolio(), SnapshotRun(FrozenSnapshotProvider.demo()), demo_risk_free_rate()
    )

    assert first == second
    assert first.snapshot.content_sha256 == second.snapshot.content_sha256
    assert first.return_matrix.content_sha256 == second.return_matrix.content_sha256


def test_analysis_loads_provider_once_and_reuses_exact_snapshot(monkeypatch) -> None:
    def forbid_network(*args, **kwargs):
        raise AssertionError("Quant demo attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbid_network)
    provider = FrozenSnapshotProvider.demo()
    run = SnapshotRun(provider)
    portfolio = demo_portfolio()

    analysis = analyze_portfolio(portfolio, run, demo_risk_free_rate())
    same_snapshot = run.snapshot_for(portfolio)

    assert provider.load_count == 1
    assert same_snapshot is analysis.snapshot
    assert analysis.snapshot.missing_values
    assert analysis.return_matrix.dropped_dates


def test_run_rejects_second_portfolio_without_second_provider_call() -> None:
    provider = FrozenSnapshotProvider.demo()
    run = SnapshotRun(provider)
    original = demo_portfolio()
    run.snapshot_for(original)
    different = replace(original, portfolio_id="different-run-request")

    with pytest.raises(MarketDataError, match="second portfolio"):
        run.snapshot_for(different)

    assert provider.load_count == 1


def test_run_rejects_same_id_with_different_instruments_without_provider_call() -> None:
    provider = FrozenSnapshotProvider.demo()
    run = SnapshotRun(provider)
    original = demo_portfolio()
    run.snapshot_for(original)
    different = replace(original, instruments=("DEMO-ALPHA", "DEMO-BETA"))

    with pytest.raises(MarketDataError, match="PortfolioDefinition differs"):
        run.snapshot_for(different)

    assert provider.load_count == 1


def test_run_rejects_same_id_with_different_cutoff_without_provider_call() -> None:
    provider = FrozenSnapshotProvider.demo()
    run = SnapshotRun(provider)
    original = demo_portfolio()
    run.snapshot_for(original)
    different = replace(original, analysis_cutoff=original.analysis_cutoff.replace(day=10))

    with pytest.raises(MarketDataError, match="PortfolioDefinition differs"):
        run.snapshot_for(different)

    assert provider.load_count == 1


def test_run_rejects_same_id_with_different_constraints_without_provider_call() -> None:
    provider = FrozenSnapshotProvider.demo()
    run = SnapshotRun(provider)
    original = demo_portfolio()
    run.snapshot_for(original)
    different = replace(original, constraints=OptimizationConstraints(0.10, 0.80))

    with pytest.raises(MarketDataError, match="PortfolioDefinition differs"):
        run.snapshot_for(different)

    assert provider.load_count == 1


def test_snapshot_respects_analysis_cutoff() -> None:
    provider = FrozenSnapshotProvider.demo()
    portfolio = replace(
        demo_portfolio(),
        portfolio_id="earlier-cutoff",
        analysis_cutoff=demo_portfolio().analysis_cutoff.replace(day=10),
    )

    snapshot = SnapshotRun(provider).snapshot_for(portfolio)

    assert snapshot.data_end.isoformat() == "2026-09-10"
    assert all(item.observed_on <= portfolio.analysis_cutoff.date() for item in snapshot.observations)
