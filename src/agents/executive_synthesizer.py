from src.agents.base_agent import BaseAgent

class ExecutiveSynthesizerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Executive Synthesizer",
            role="Executive communication and synthesis"
        )

    def run(self, query: str, agent1_output: dict, agent2_output: dict, agent3_output: dict) -> dict:
        print(f"\n📝 Agent 4 — Executive synthesis en cours...")

        prompt = f"""You are a Chief Investment Officer writing a concise executive memo.

Original question: {query}

MARKET ANALYSIS (Agent 1):
{agent1_output['analysis'][:600]}

RISK ASSESSMENT (Agent 2):
{agent2_output['analysis'][:600]}

PORTFOLIO STRATEGY (Agent 3):
{agent3_output['analysis'][:600]}

Key metrics:
- Recommended weights: {agent3_output['weights']}
- Expected return: {agent3_output['expected_return']}%
- Expected volatility: {agent3_output['expected_volatility']}%
- Expected Sharpe: {agent3_output['expected_sharpe']}

Write a structured executive memo with EXACTLY this format:

EXECUTIVE SUMMARY
[2-3 sentences max. The answer to the question in plain language.]

KEY FINDINGS
1. [Finding with specific number]
2. [Finding with specific number]
3. [Finding with specific number]

RECOMMENDATION
[One clear action: BUY/SELL/HOLD/REBALANCE + allocation + timeline]

RISKS TO MONITOR
- [Risk 1]
- [Risk 2]

NEXT STEPS
1. [Immediate action]
2. [Short-term action]
3. [Monitoring action]

Keep it under 300 words. No fluff. Institutional tone."""

        analysis = self.call_llm(prompt)

        return {
            "agent": self.name,
            "analysis": analysis,
            "weights": agent3_output["weights"],
            "expected_return": agent3_output["expected_return"],
            "expected_volatility": agent3_output["expected_volatility"],
            "expected_sharpe": agent3_output["expected_sharpe"]
        }