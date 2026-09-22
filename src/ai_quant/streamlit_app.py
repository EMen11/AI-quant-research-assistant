"""Minimal offline Streamlit entry point for the Block 1 foundation."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ai_quant.config import AppMode, Settings
from ai_quant.llm import FakeLLM, LLMClient
from ai_quant.market_data import FrozenMarketDataProvider, MarketDataProvider, MarketSeries


@dataclass(frozen=True, slots=True)
class DemoViewModel:
    """Deterministic values rendered by the minimal demo page."""

    summary: str
    market_series: tuple[MarketSeries, ...]


def build_demo_view(
    settings: Settings,
    llm: LLMClient | None = None,
    market_data: MarketDataProvider | None = None,
) -> DemoViewModel:
    """Build the public demo from injected offline dependencies."""

    if settings.app_mode is not AppMode.DEMO:
        raise ValueError("The frozen demo view can only be built in APP_MODE=demo.")

    llm_client = llm or FakeLLM(
        "The reproducible offline foundation is ready. Quantitative analytics arrive in Block 2."
    )
    provider = market_data or FrozenMarketDataProvider.demo()
    response = llm_client.complete("Summarize the status of the offline Block 1 foundation.")
    series = provider.get_series(("DEMO-ALPHA", "DEMO-BETA"))
    return DemoViewModel(summary=response.text, market_series=series)


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
    st.info("Block 1 scope: reproducible packaging, typed startup, offline fakes, tests and CI.")
