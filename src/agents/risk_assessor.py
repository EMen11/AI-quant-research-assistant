from src.agents.base_agent import BaseAgent
import numpy as np
import json

class RiskAssessorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Risk Assessor",
            role="Quantitative risk management"
        )

    def calculate_var(self, returns: list, confidence: float = 0.95) -> float:
        """Value at Risk historique."""
        return round(float(np.percentile(returns, (1 - confidence) * 100)), 4)

    def run(self, query: str, agent1_output: dict) -> dict:
        print(f"\n⚠️  Agent 2 — Risk assessment en cours...")

        # Calcul VaR depuis les métriques Agent 1
        risk_metrics = {}
        for ticker, m in agent1_output["metrics"].items():
            vol = m["volatility_annualized"] / 100
            daily_vol = vol / np.sqrt(252)
            risk_metrics[ticker] = {
                "var_95_daily": round(-1.645 * daily_vol * 100, 2),
                "var_99_daily": round(-2.326 * daily_vol * 100, 2),
                "max_drawdown": m["max_drawdown"],
                "volatility": m["volatility_annualized"]
            }

        risk_str = json.dumps(risk_metrics, indent=2)
        analysis_str = agent1_output["analysis"]

        prompt = f"""You are a risk management specialist at an institutional asset manager.

User question: {query}

Market analysis from previous agent:
{analysis_str}

Calculated risk metrics:
{risk_str}

Note: VaR figures represent daily percentage loss at given confidence level.

Provide:
1. Overall risk assessment (Low/Medium/High) with justification
2. VaR interpretation for each asset
3. Key risk factors specific to the user's question
4. 2-3 stress test scenarios with estimated impact
5. Risk mitigation recommendations

Be specific with numbers and actionable."""

        analysis = self.call_llm(prompt)

        return {
            "agent": self.name,
            "risk_metrics": risk_metrics,
            "analysis": analysis
        }