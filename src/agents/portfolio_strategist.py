from src.agents.base_agent import BaseAgent
import numpy as np
import json
from scipy.optimize import minimize
import yfinance as yf

class PortfolioStrategistAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Portfolio Strategist",
            role="Portfolio optimization and allocation"
        )

    def get_returns_matrix(self, tickers: list, period: str = "1y") -> np.ndarray:
        """Télécharge les returns journaliers pour tous les tickers."""
        returns = {}
        for ticker in tickers:
            hist = yf.Ticker(ticker).history(period=period)
            if not hist.empty:
                returns[ticker] = hist["Close"].pct_change().dropna()
        
        import pandas as pd
        df = pd.DataFrame(returns).dropna()
        return df

    def markowitz_optimization(self, returns_df) -> dict:
        """
        Vraie optimisation Markowitz via scipy.optimize.
        
        Objectif : maximiser le Sharpe Ratio
        Contraintes :
          - sum(weights) = 1
          - weights >= 0 (long-only)
        """
        if returns_df.empty:
            return {}
        if returns_df.shape[1] == 1:
            # Un seul actif — pas d'optimisation possible
            ticker = returns_df.columns[0]
            return {ticker: 1.0}

        # Paramètres annualisés
        rf = 0.02  # Risk-free rate 2% (Swiss context)
        n = returns_df.shape[1]
        mean_returns = returns_df.mean() * 252
        cov_matrix = returns_df.cov() * 252

        # Fonction objectif : négatif du Sharpe (on minimise)
        def neg_sharpe(weights):
            port_return = np.dot(weights, mean_returns)
            port_vol = np.sqrt(weights @ cov_matrix.values @ weights)
            if port_vol == 0:
                return 0
            return -(port_return - rf) / port_vol

        # Contraintes
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        
        # Bornes : long-only, max 60% par actif
        bounds = tuple((0.05, 0.60) for _ in range(n))
        
        # Point de départ : poids égaux
        w0 = np.array([1/n] * n)

        result = minimize(
            neg_sharpe,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-9}
        )

        if result.success:
            weights = dict(zip(returns_df.columns, np.round(result.x, 4)))
        else:
            # Fallback : poids égaux si optimisation échoue
            weights = {t: round(1/n, 4) for t in returns_df.columns}

        return weights

    def compute_portfolio_metrics(self, weights: dict, returns_df, rf: float = 0.02) -> dict:
        """Calcule les métriques du portefeuille optimisé."""
        if returns_df.empty:
            return {}

        w = np.array([weights.get(t, 0) for t in returns_df.columns])
        mean_returns = returns_df.mean() * 252
        cov_matrix = returns_df.cov() * 252

        port_return = float(np.dot(w, mean_returns) * 100)
        port_vol = float(np.sqrt(w @ cov_matrix.values @ w) * 100)
        sharpe = round((port_return/100 - rf) / (port_vol/100), 3) if port_vol > 0 else 0

        return {
            "expected_return": round(port_return, 2),
            "expected_volatility": round(port_vol, 2),
            "sharpe_ratio": sharpe
        }

    def run(self, query: str, agent1_output: dict, agent2_output: dict) -> dict:
        print(f"\n📈 Agent 3 — Markowitz optimization en cours...")

        tickers = agent1_output["tickers"]
        
        # Récupère la matrice de returns
        returns_df = self.get_returns_matrix(tickers)

        # Optimisation Markowitz réelle
        weights = self.markowitz_optimization(returns_df)

        # Métriques portefeuille
        pm = self.compute_portfolio_metrics(weights, returns_df)

        weights_str = json.dumps(weights, indent=2)
        risk_analysis = agent2_output["analysis"]

        prompt = f"""You are a senior portfolio strategist at an institutional asset manager.

User question: {query}

Markowitz-optimized allocation (maximizing Sharpe ratio, long-only, max 60% per asset):
{weights_str}

Portfolio metrics (annualized, risk-free rate = 2%):
- Expected return: {pm.get('expected_return', 'N/A')}%
- Expected volatility: {pm.get('expected_volatility', 'N/A')}%
- Sharpe ratio: {pm.get('sharpe_ratio', 'N/A')}

Covariance matrix used for optimization (real historical data).

Risk assessment:
{risk_analysis[:500]}...

Provide:
1. Clear BUY / HOLD / SELL / REBALANCE recommendation
2. Allocation rationale (why these weights)
3. Entry strategy (timing, phasing)
4. Expected risk/return vs benchmark
5. Exit conditions

Be decisive and quantitative."""

        analysis = self.call_llm(prompt)

        return {
            "agent": self.name,
            "weights": weights,
            "expected_return": pm.get("expected_return", 0),
            "expected_volatility": pm.get("expected_volatility", 0),
            "expected_sharpe": pm.get("sharpe_ratio", 0),
            "analysis": analysis
        }