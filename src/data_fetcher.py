import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def fetch_market_data(tickers: list, period: str = "1y") -> dict:
    """Télécharge les données de prix pour une liste de tickers."""
    data = {}
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                print(f"⚠️  Pas de données pour {ticker}")
                continue
            
            data[ticker] = hist
            print(f"✅ {ticker} : {len(hist)} jours de données")
        
        except Exception as e:
            print(f"❌ Erreur pour {ticker}: {e}")
    
    return data


def calculate_metrics(data: dict) -> dict:
    """Calcule les métriques clés pour chaque ticker."""
    metrics = {}
    
    for ticker, hist in data.items():
        if len(hist) < 2:
            continue
        returns = hist["Close"].pct_change().dropna()

        metrics[ticker] = {
            "current_price": round(hist["Close"].iloc[-1], 2),
            "return_1y": round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2),
            "volatility_annualized": round(returns.std() * np.sqrt(252) * 100, 2) if not returns.empty else 0.0,
            "max_drawdown": round(calculate_max_drawdown(hist["Close"]) * 100, 2),
            "avg_volume": int(hist["Volume"].mean()),
        }
    
    return metrics


def calculate_max_drawdown(prices: pd.Series) -> float:
    """Calcule le drawdown maximum sur la période."""
    peak = prices.expanding().max()
    drawdown = (prices - peak) / peak
    return drawdown.min()


def extract_tickers(text: str) -> list:
    """Extrait les tickers mentionnés dans le texte utilisateur."""
    # Tickers communs Swiss + US + indices
    known_tickers = {
        "novartis": "NOVN.SW", "roche": "ROG.SW", "nestle": "NESN.SW",
        "ubs": "UBSG.SW", "cs": "CSGN.SW", "smi": "^SSMI",
        "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
        "amazon": "AMZN", "tesla": "TSLA", "nvidia": "NVDA",
        "sp500": "^GSPC", "nasdaq": "^IXIC", "gold": "GC=F",
        "bitcoin": "BTC-USD", "swiss": "^SSMI",
        "oil": "CL=F", "energy": "XLE", "defense": "ITA", "bonds": "TLT"
    }

    blacklist = {"I", "AI", "OR", "AND", "THE", "USA", "US", "UN", "NATO", "GDP", "IRAN", "ISRAEL"}

    text_lower = text.lower()
    found = []

    for keyword, ticker in known_tickers.items():
        if keyword in text_lower and ticker not in found:
            found.append(ticker)

    # Détecte aussi les tickers directs en majuscules (ex: AAPL, MSFT)
    import re
    direct = re.findall(r'\b[A-Z]{2,5}\b', text)
    for t in direct:
        if t not in found and t not in blacklist:
            found.append(t)

    return found if found else None