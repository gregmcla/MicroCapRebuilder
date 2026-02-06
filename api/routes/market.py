"""Market indices endpoints."""

from fastapi import APIRouter
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

router = APIRouter(prefix="/api/market")


@router.get("/indices")
def get_market_indices():
    """Fetch S&P 500, Russell 2000, VIX with sparkline data.

    Returns:
        dict: Market indices with current value, change %, and 20-bar sparkline.
    """
    indices = {
        "sp500": {"ticker": "^GSPC", "name": "S&P 500"},
        "russell2000": {"ticker": "^RUT", "name": "Russell 2000"},
        "vix": {"ticker": "^VIX", "name": "VIX"},
    }

    result = {}

    for key, info in indices.items():
        ticker = info["ticker"]
        try:
            # Fetch 1 day of 5-minute bars for sparkline
            data = yf.download(
                ticker,
                period="1d",
                interval="5m",
                progress=False
            )

            if data.empty or len(data) < 2:
                # Fallback: no data available
                result[key] = {
                    "name": info["name"],
                    "value": 0.0,
                    "change_pct": 0.0,
                    "sparkline": []
                }
                continue

            # Handle MultiIndex columns from yfinance
            if isinstance(data.columns, pd.MultiIndex):
                closes = data["Close"][ticker].dropna()
            else:
                closes = data["Close"].dropna()

            closes_list = closes.tolist()

            # Get last 20 prices for sparkline
            sparkline = closes_list[-20:] if len(closes_list) >= 20 else closes_list

            # Current value and change
            current_value = float(closes_list[-1])
            prev_value = float(closes_list[0])
            change_pct = ((current_value - prev_value) / prev_value * 100) if prev_value > 0 else 0.0

            result[key] = {
                "name": info["name"],
                "value": round(current_value, 2),
                "change_pct": round(change_pct, 2),
                "sparkline": [round(p, 2) for p in sparkline]
            }

        except Exception as e:
            # Graceful degradation on error
            result[key] = {
                "name": info["name"],
                "value": 0.0,
                "change_pct": 0.0,
                "sparkline": []
            }

    return result
