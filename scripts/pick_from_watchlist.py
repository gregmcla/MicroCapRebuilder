#!/usr/bin/env python3
import json, sys, datetime as dt
from pathlib import Path
import pandas as pd
import yfinance as yf

# ─── 1) Load your static watchlist ──────────────────────────────────────────────
wl_path = Path(__file__).parent.parent / "data" / "watchlist.jsonl"
if not wl_path.exists():
    sys.exit(f"{wl_path} not found")
with open(wl_path, "r") as f:
    WATCHLIST = [json.loads(line) for line in f if line.strip()]
TICKERS = [item["ticker"] for item in WATCHLIST]

# ─── 2) Parameters ─────────────────────────────────────────────────────────────
RISK_PER_TRADE = 0.10    # 10% of available cash per trade

# ─── 3) Read existing cash & positions ─────────────────────────────────────────
def read_cash_and_positions():
    p = Path(__file__).parent.parent / "data" / "portfolio_update.csv"
    df = pd.read_csv(p)
    # detect cash column name
    cash_col = "Cash Balance" if "Cash Balance" in df.columns else "Cash"
    # get latest TOTAL row
    total_row = df[df["Ticker"].str.upper() == "TOTAL"].iloc[-1]
    cash = float(total_row[cash_col])
    # existing positions (ignore TOTAL)
    pos = df[df["Ticker"].str.upper() != "TOTAL"].copy()
    return cash, pos

# ─── 4) Main logic ─────────────────────────────────────────────────────────────
def main():
    cash, positions = read_cash_and_positions()
    total_val = positions["Total Value"].sum()
    risk_capital = cash * RISK_PER_TRADE
    total_val = positions["Total Value"].sum()

    new_trades = []
    for ticker in TICKERS:
        # fetch latest price
        df = yf.download(ticker, period="1d", progress=False, auto_adjust=True)
        if df.empty:
            print(f"[warn] no data for {ticker}, skipping")
            continue
        price = df["Close"].iloc[-1].item()
        # compute how many shares we can buy with risk_capital
        shares = int(risk_capital // price)
        if shares < 1:
            # not enough risk capital to buy at least one share
            continue
        total_cost = shares * price
        if total_cost > cash:
            # not enough cash left
            continue
        # record this buy
        new_trades.append((ticker, shares, price))
        cash -= total_cost

    if not new_trades:
        print("[warn] No picks this run")
    else:
        # 5a) Append to trade_log.csv
        tl = Path(__file__).parent.parent / "data" / "trade_log.csv"
        df_tl = pd.read_csv(tl)
        today = dt.date.today().isoformat()
        for t, s, p in new_trades:
            df_tl.loc[len(df_tl)] = {
                "Date": today,
                "Ticker": t,
                "Shares Bought": s,
                "Buy Price": round(p, 2)
            }
        df_tl.to_csv(tl, index=False)

        # 5b) Update portfolio_update.csv
        pu = Path(__file__).parent.parent / "data" / "portfolio_update.csv"
        df_pu = pd.read_csv(pu)

        val_col = "Total Value" if "Total Value" in df_pu.columns else "Value"

        # drop old TOTAL
        df_pu = df_pu[df_pu["Ticker"].str.upper() != "TOTAL"]

        # add new position rows
        for t, s, p in new_trades:
            df_pu.loc[len(df_pu)] = {
                "Date": today,
                "Ticker": t,
                "Shares": s,
                "Cost Basis": "",
                "Stop Loss": "",
                "Current Price": round(p, 2),
                val_col: round(s * p, 2),
                "PnL": "",
                "Cash Balance": "",
                "Total Equity": ""
            }

        # re-compute TOTAL row for today
        pos = df_pu[df_pu["Ticker"].str.upper() != "TOTAL"]
        total_val = pos[val_col].sum()
        df_pu.loc[len(df_pu)] = {
            "Date": today,
            "Ticker": "TOTAL",
            "Shares": "",
            "Cost Basis": "",
            "Stop Loss": "",
            "Current Price": "",
            val_col: "",
            "PnL": "",
            "Cash Balance": round(cash, 2),
            "Total Equity": round(total_val + cash, 2)
        }

        df_pu.to_csv(pu, index=False)
        print("✅ picked from watchlist")

    # final status
    print(f"✅ TOTAL for {dt.date.today().isoformat()} set to ${round(total_val+cash,2)} "
          f"(positions ${round(total_val,2)} + cash ${round(cash,2)})")

if __name__ == "__main__":
    main()
