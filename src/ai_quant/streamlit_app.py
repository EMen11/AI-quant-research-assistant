"""Offline Streamlit entry point for the reproducible foundation and Quant Core."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ai_quant.config import AppMode, Settings
from ai_quant.llm import FakeLLM, LLMClient
from ai_quant.market_data import (
    FrozenMarketDataProvider,
    FrozenSnapshotProvider,
    MarketDataProvider,
    MarketSeries,
    SnapshotMarketDataProvider,
    SnapshotRun,
)
from ai_quant.quant import QuantAnalysis, analyze_portfolio, demo_portfolio, demo_risk_free_rate


@dataclass(frozen=True, slots=True)
class DemoViewModel:
    """Deterministic values rendered by the minimal demo page."""

    summary: str
    market_series: tuple[MarketSeries, ...]
    quant_analysis: QuantAnalysis


def build_demo_view(
    settings: Settings,
    llm: LLMClient | None = None,
    market_data: MarketDataProvider | None = None,
    snapshot_provider: SnapshotMarketDataProvider | None = None,
) -> DemoViewModel:
    """Build the public demo from injected offline dependencies."""

    if settings.app_mode is not AppMode.DEMO:
        raise ValueError("The frozen demo view can only be built in APP_MODE=demo.")

    llm_client = llm or FakeLLM(
        "The reproducible offline foundation is ready. The deterministic Quant Core is loaded."
    )
    provider = market_data or FrozenMarketDataProvider.demo()
    response = llm_client.complete("Summarize the status of the offline Block 1 foundation.")
    series = provider.get_series(("DEMO-ALPHA", "DEMO-BETA"))
    quant_analysis = analyze_portfolio(
        demo_portfolio(),
        SnapshotRun(snapshot_provider or FrozenSnapshotProvider.demo()),
        demo_risk_free_rate(),
    )
    return DemoViewModel(
        summary=response.text,
        market_series=series,
        quant_analysis=quant_analysis,
    )


def main() -> None:
    """Validate startup configuration and render the selected application mode."""

    settings = Settings.from_env()
    st.set_page_config(
        page_title="AI Quant Research Workbench",
        page_icon="📊",
        layout="wide",
    )
    st.title("AI Quant Research Workbench")

    if settings.app_mode is AppMode.LIVE:
        st.warning(
            "Live mode is validated but intentionally not wired into the Block 1 page. "
            "Use APP_MODE=demo for the offline foundation."
        )
        return

    view = build_demo_view(settings)
    st.success("Frozen public demo · offline · no secret required")
    st.write(view.summary)
    st.subheader("Illustrative frozen startup fixture")
    st.caption(
        "These synthetic values verify deterministic provider wiring only. "
        "They are not market analysis or investment advice."
    )
    st.table(
        [
            {
                "Symbol": series.symbol,
                "Date": series.latest.observed_on.isoformat(),
                "Close": str(series.latest.close),
                "Currency": series.currency,
                "Provider": series.provider,
            }
            for series in view.market_series
        ]
    )
    st.info("Block 1 foundation preserved: packaging, typed startup, offline fakes, tests and CI.")

    analysis = view.quant_analysis
    snapshot = analysis.snapshot
    st.divider()
    st.header("Quant")
    st.warning(
        "Historical, synthetic demonstration only — this is neither a forecast nor an investment "
        "recommendation."
    )
    st.subheader("Immutable market snapshot")
    st.table(
        [
            {
                "Snapshot": snapshot.snapshot_id,
                "SHA-256": snapshot.content_sha256,
                "Assets": ", ".join(snapshot.instruments),
                "Period": f"{snapshot.data_start.isoformat()} → {snapshot.data_end.isoformat()}",
                "Reference date": analysis.portfolio.analysis_cutoff.date().isoformat(),
                "Frequency": snapshot.frequency,
                "Currency": snapshot.base_currency,
                "Provider": snapshot.provider,
                "Retrieved at": snapshot.retrieved_at.isoformat(),
                "Price rows": snapshot.rows,
                "Missing prices": len(snapshot.missing_values),
                "Dropped return dates": len(analysis.return_matrix.dropped_dates),
            }
        ]
    )
    st.caption(snapshot.adjustment_policy)

    st.subheader("Historical portfolio metrics · equal weight")
    metrics = analysis.portfolio_metrics
    metric_rows = [
        {
            "Metric": "Cumulative return",
            "Value": f"{metrics.cumulative_return.value:.2%}",
            "Unit / horizon": metrics.cumulative_return.horizon,
        },
        {
            "Metric": "Historical annualized return",
            "Value": f"{metrics.historical_annualized_return.value:.2%}",
            "Unit / horizon": metrics.historical_annualized_return.horizon,
        },
        {
            "Metric": "Annualized volatility",
            "Value": f"{metrics.annualized_volatility.value:.2%}",
            "Unit / horizon": metrics.annualized_volatility.horizon,
        },
        {
            "Metric": "Maximum drawdown (positive loss)",
            "Value": f"{metrics.maximum_drawdown.value:.2%}",
            "Unit / horizon": metrics.maximum_drawdown.horizon,
        },
    ]
    for estimate in metrics.risk_estimates:
        level = f"{estimate.confidence_level:.0%}"
        metric_rows.extend(
            (
                {
                    "Metric": f"Historical VaR ({level})",
                    "Value": f"{estimate.historical_var.value:.2%}",
                    "Unit / horizon": estimate.historical_var.horizon,
                },
                {
                    "Metric": f"Parametric VaR ({level})",
                    "Value": f"{estimate.parametric_var.value:.2%}",
                    "Unit / horizon": estimate.parametric_var.horizon,
                },
                {
                    "Metric": f"Expected Shortfall ({level})",
                    "Value": f"{estimate.expected_shortfall.value:.2%}",
                    "Unit / horizon": estimate.expected_shortfall.horizon,
                },
            )
        )
    st.table(metric_rows)
    risk_free = analysis.risk_free_rate
    st.caption(
        f"Risk-free assumption: {risk_free.annual_rate:.2%} {risk_free.currency}, "
        f"dated {risk_free.as_of.isoformat()} — {risk_free.source}"
    )

    st.subheader("Markowitz scenario and diagnostics")
    optimization = analysis.optimization
    if optimization.diagnostics.converged:
        st.table(
            [
                {"Asset": asset, "Weight": f"{weight:.2%}"}
                for asset, weight in optimization.weights
            ]
        )
    else:
        st.error(f"No optimizer weights emitted: {optimization.diagnostics.failure_reason}")
    diagnostics = optimization.diagnostics
    st.json(
        {
            "objective": diagnostics.objective,
            "converged": diagnostics.converged,
            "solver_success": diagnostics.solver_success,
            "constraints_satisfied": diagnostics.constraints_satisfied,
            "bounds_satisfied": diagnostics.bounds_satisfied,
            "weight_sum": diagnostics.weight_sum,
            "excluded_assets": diagnostics.excluded_assets,
            "iterations": diagnostics.iterations,
            "failure_reason": diagnostics.failure_reason,
        }
    )

    st.subheader("Assumptions")
    for assumption in analysis.assumptions:
        st.markdown(f"- {assumption}")
