from src.agents.base_agent import BaseAgent
from src.data_fetcher import fetch_market_data, calculate_metrics, extract_tickers
import json

class MarketAnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Market Analyst",
            role="Quantitative market data analysis"
        )

    def run(self, query: str, period: str = "1y") -> dict:
        # 1. Extraire les tickers de la question
        tickers = extract_tickers(query)
        print(f"\n📊 Agent 1 — Tickers détectés : {tickers}")

        if tickers is None:
            return {
                "agent": self.name,
                "tickers": [],
                "metrics": {},
                "analysis": "No specific financial assets were detected in your query. Please specify the stocks, indices, or assets you'd like to analyze (e.g. Apple, S&P500, gold, Tesla)."
            }

        # 2. Fetch les données
        market_data = fetch_market_data(tickers, period=period)
        metrics = calculate_metrics(market_data)

        # 3. Préparer le contexte pour Claude
        metrics_str = json.dumps(metrics, indent=2, default=str)

        prompt = f"""You are a quantitative market data analyst. Analyze the following market data:

User question: {query}

Market metrics:
{metrics_str}

Provide a structured analysis with:
1. Key price movements and trends for each asset
2. Volatility assessment
3. Notable patterns or risk signals
4. 3-5 key insights relevant to the user's question

Be concise, data-driven, and quantitative. Reference specific numbers from the data."""

        # 4. Appel Claude
        analysis = self.call_llm(prompt)

        return {
            "agent": self.name,
            "tickers": tickers,
            "metrics": metrics,
            "analysis": analysis
        }