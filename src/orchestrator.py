import sqlite3
import json
import os
from datetime import datetime
from src.agents.market_analyst import MarketAnalystAgent
from src.agents.risk_assessor import RiskAssessorAgent
from src.agents.portfolio_strategist import PortfolioStrategistAgent
from src.agents.executive_synthesizer import ExecutiveSynthesizerAgent

class MultiAgentOrchestrator:
    def __init__(self, db_path: str = "data/conversations.db"):
        self.db_path = db_path
        self.agent1 = MarketAnalystAgent()
        self.agent2 = RiskAssessorAgent()
        self.agent3 = PortfolioStrategistAgent()
        self.agent4 = ExecutiveSynthesizerAgent()
        self._init_db()

    def _init_db(self):
        """Crée la table SQLite si elle n'existe pas."""
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                query TEXT,
                tickers TEXT,
                executive_summary TEXT,
                weights TEXT,
                expected_return REAL,
                expected_volatility REAL,
                expected_sharpe REAL
            )
        """)
        conn.commit()
        conn.close()

    def _save_to_db(self, query: str, result: dict):
        """Sauvegarde le résultat dans SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO conversations 
            (timestamp, query, tickers, executive_summary, weights, 
             expected_return, expected_volatility, expected_sharpe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            query,
            json.dumps(result["tickers"]),
            result["executive_summary"],
            json.dumps(result["weights"], default=str),
            result["expected_return"],
            result["expected_volatility"],
            result["expected_sharpe"]
        ))
        conn.commit()
        conn.close()

    def run(self, query: str, period: str = "1y") -> dict:
        """Lance la chaîne complète des 4 agents."""
        print(f"\n{'='*60}")
        print(f"🚀 Analyse en cours pour : {query[:60]}...")
        print(f"{'='*60}")

        # Chaîne des agents
        r1 = self.agent1.run(query, period=period)
        r2 = self.agent2.run(query, r1)
        r3 = self.agent3.run(query, r1, r2)
        r4 = self.agent4.run(query, r1, r2, r3)

        result = {
            "query": query,
            "tickers": r1["tickers"],
            "market_analysis": r1["analysis"],
            "risk_assessment": r2["analysis"],
            "portfolio_strategy": r3["analysis"],
            "executive_summary": r4["analysis"],
            "weights": r3["weights"],
            "expected_return": r3["expected_return"],
            "expected_volatility": r3["expected_volatility"],
            "expected_sharpe": r3["expected_sharpe"],
            "risk_metrics": r2["risk_metrics"],
            "market_metrics": r1["metrics"]
        }

        # Sauvegarde en base
        self._save_to_db(query, result)
        print(f"\n✅ Analyse complète sauvegardée en base.")

        return result

    def get_history(self, limit: int = 10) -> list:
        """Récupère les dernières analyses."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT timestamp, query, expected_return, expected_sharpe
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows