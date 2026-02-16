"""Market indices endpoints."""

from fastapi import APIRouter
from typing import Optional
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

router = APIRouter(prefix="/api/market")


def _fetch_index(symbol: str) -> dict:
    """Fetch a single index using yf.Ticker (isolated, no global state)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        if hist.empty or len(hist) < 2:
            return {"value": 0.0, "change_pct": 0.0, "sparkline": []}

        closes = hist["Close"].dropna().tolist()
        sparkline = closes[-20:] if len(closes) >= 20 else closes
        current_value = float(closes[-1])
        prev_close = float(closes[-2])
        change_pct = ((current_value - prev_close) / prev_close * 100) if prev_close > 0 else 0.0

        return {
            "value": round(current_value, 2),
            "change_pct": round(change_pct, 2),
            "sparkline": [round(p, 2) for p in sparkline],
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return {"value": 0.0, "change_pct": 0.0, "sparkline": []}


@router.get("/indices")
def get_market_indices():
    """Fetch S&P 500, Russell 2000, VIX with sparkline data."""
    sp500 = _fetch_index("^GSPC")
    russell = _fetch_index("^RUT")
    vix = _fetch_index("^VIX")

    return {
        "sp500": {"name": "S&P 500", **sp500},
        "russell2000": {"name": "Russell 2000", **russell},
        "vix": {"name": "VIX", **vix},
    }


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

        # Handle MultiIndex columns (only when ticker key exists in MultiIndex)
        # When downloading single ticker, yfinance typically returns simple columns
        if isinstance(data.columns, pd.MultiIndex) and ticker in data["Close"].columns:
            df = pd.DataFrame({
                "time": data.index,
                "open": data["Open"][ticker].values,
                "high": data["High"][ticker].values,
                "low": data["Low"][ticker].values,
                "close": data["Close"][ticker].values,
                "volume": data["Volume"][ticker].values,
            })
        else:
            # Simple columns (single ticker download)
            # Use squeeze() to ensure 1D arrays (handles both Series and DataFrame columns)
            df = pd.DataFrame({
                "time": data.index,
                "open": data["Open"].squeeze().values,
                "high": data["High"].squeeze().values,
                "low": data["Low"].squeeze().values,
                "close": data["Close"].squeeze().values,
                "volume": data["Volume"].squeeze().values,
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
