"""Market indices endpoints."""

from fastapi import APIRouter
from typing import Optional
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
            print(f"Error fetching {key}: {e}")
            result[key] = {
                "name": info["name"],
                "value": 0.0,
                "change_pct": 0.0,
                "sparkline": []
            }

    return result


@router.get("/chart/{ticker}")
def get_chart_data(ticker: str, range: str = "1M", interval: Optional[str] = None):
    """Fetch OHLCV data with technical indicators for candlestick charts.

    Args:
        ticker: Stock ticker symbol
        range: Time range (1D, 5D, 1M, 3M, YTD, ALL, 20D)
        interval: Optional interval override (auto-selected if not provided)

    Returns:
        dict: Chart data with OHLCV and technical indicators
    """
    # Map range to yfinance period and interval
    range_map = {
        "1D": ("1d", "5m"),
        "5D": ("5d", "15m"),
        "1M": ("1mo", "1d"),
        "3M": ("3mo", "1d"),
        "YTD": ("ytd", "1d"),
        "ALL": ("max", "1d"),
        "20D": ("1mo", "1d"),  # 20 trading days ≈ 1 month
    }

    period, default_interval = range_map.get(range, ("1mo", "1d"))
    interval = interval or default_interval

    try:
        # Fetch historical data
        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False
        )

        if data.empty:
            return {
                "ticker": ticker,
                "range": range,
                "data": [],
                "indicators": {"rsi": [], "sma_20": [], "sma_50": []}
            }

        # Handle MultiIndex columns
        if isinstance(data.columns, pd.MultiIndex):
            df = pd.DataFrame({
                "time": data.index,
                "open": data["Open"][ticker].values,
                "high": data["High"][ticker].values,
                "low": data["Low"][ticker].values,
                "close": data["Close"][ticker].values,
                "volume": data["Volume"][ticker].values,
            })
        else:
            df = pd.DataFrame({
                "time": data.index,
                "open": data["Open"].values,
                "high": data["High"].values,
                "low": data["Low"].values,
                "close": data["Close"].values,
                "volume": data["Volume"].values,
            })

        # Calculate RSI (14-period)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Calculate moving averages
        sma_20 = df["close"].rolling(window=20).mean()
        sma_50 = df["close"].rolling(window=50).mean()

        # Convert to JSON-serializable format
        ohlcv_data = []
        for i, row in df.iterrows():
            ohlcv_data.append({
                "time": int(row["time"].timestamp() * 1000),  # milliseconds
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
            })

        # Convert indicators to lists (handle NaN)
        rsi_list = [round(float(v), 2) if pd.notna(v) else None for v in rsi]
        sma_20_list = [round(float(v), 2) if pd.notna(v) else None for v in sma_20]
        sma_50_list = [round(float(v), 2) if pd.notna(v) else None for v in sma_50]

        return {
            "ticker": ticker,
            "range": range,
            "data": ohlcv_data,
            "indicators": {
                "rsi": rsi_list,
                "sma_20": sma_20_list,
                "sma_50": sma_50_list,
            }
        }

    except Exception as e:
        # Graceful degradation on error
        print(f"ERROR fetching chart data for {ticker} (range={range}): {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "ticker": ticker,
            "range": range,
            "data": [],
            "indicators": {"rsi": [], "sma_20": [], "sma_50": []}
        }
