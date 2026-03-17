import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import MultiAgentOrchestrator

# Config page
st.set_page_config(
    page_title="AI Quant Research Assistant",
    page_icon="📊",
    layout="wide"
)

# Header
st.title("📊 AI Quant Research Assistant")
st.caption("Multi-agent system powered by Claude API — Institutional-grade investment analysis")
st.divider()

# Init orchestrator
@st.cache_resource
def get_orchestrator():
    return MultiAgentOrchestrator()

orch = get_orchestrator()

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    period = st.selectbox("Data period", ["6mo", "1y", "2y"], index=1)
    st.divider()
    st.header("📁 Recent Analyses")
    history = orch.get_history(limit=5)
    if history:
        for row in history:
            st.caption(f"🕐 {row[0][:10]}")
            st.caption(f"_{row[1][:40]}..._")
            st.caption(f"Return: {row[2]}% | Sharpe: {row[3]}")
            st.divider()
    else:
        st.caption("No analyses yet.")

# Main input
query = st.text_area(
    "💬 Your investment question",
    placeholder="e.g. Should I increase my exposure to Swiss pharmaceutical stocks given recent FDA approvals?",
    height=100
)

col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)
with col2:
    st.caption("~30-45 seconds")

# Run analysis
if run_btn and query:
    with st.spinner("Running 4-agent analysis..."):
        
        # Progress steps
        progress = st.progress(0)
        status = st.empty()

        status.text("📊 Agent 1: Fetching market data...")
        progress.progress(10)

        try:
            result = orch.run(query, period=period)
            progress.progress(100)
            status.empty()

            st.success("✅ Analysis complete")

            if not result.get("tickers"):
                st.warning(
                    "No specific assets were identified in your question. "
                    "Please mention stocks, indices, or assets you'd like to analyze. "
                    "Examples: *Apple*, *S&P500*, *gold*, *Tesla*, *Nvidia*, *bonds*, *oil*."
                )
                st.markdown(result.get("market_analysis", ""))
                st.stop()

            st.divider()

            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Tickers", ", ".join(result["tickers"]))
            col2.metric("Expected Return", f"{result['expected_return']}%")
            col3.metric("Volatility", f"{result['expected_volatility']}%")
            col4.metric("Sharpe Ratio", result["expected_sharpe"])

            st.divider()

            # Tabs pour chaque agent
            tab1, tab2, tab3, tab4 = st.tabs([
                "📝 Executive Summary",
                "📊 Market Analysis", 
                "⚠️ Risk Assessment",
                "📈 Portfolio Strategy"
            ])

            with tab1:
                st.markdown(result["executive_summary"])

            with tab2:
                st.markdown(result["market_analysis"])
                st.subheader("Raw Metrics")
                st.json(result["market_metrics"])

            with tab3:
                st.markdown(result["risk_assessment"])
                st.subheader("Risk Metrics")
                st.json(result["risk_metrics"])

            with tab4:
                st.markdown(result["portfolio_strategy"])
                st.subheader("Optimal Weights")
                weights = result["weights"]
                for ticker, w in weights.items():
                    st.progress(float(w), text=f"{ticker}: {round(float(w)*100, 1)}%")

        except Exception as e:
            progress.empty()
            status.empty()
            st.error(f"Error: {e}")

elif run_btn and not query:
    st.warning("Please enter an investment question.")