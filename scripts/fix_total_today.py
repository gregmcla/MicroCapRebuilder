#!/usr/bin/env python3
import pandas as pd
import datetime as dt

df = pd.read_csv("data/portfolio.csv")
today = dt.date.today()
df["Value"] = df["Shares"] * df["Price"]
pos_val = df["Value"].sum()
cash = 5000.0 - df["Cost"].sum()
out = pd.DataFrame([{
    "Date": today.isoformat(),
    "Ticker": "TOTAL",
    "Shares": "",
    "Cost": "",
    "Stop": "",
    "Price": "",
    "Value": pos_val,
    "PnL": "",
    "Cash": cash,
    "Equity": pos_val + cash,
}])
out.to_csv("data/portfolio_update.csv", index=False)
print(f"✅ TOTAL for {today} set to {pos_val+cash:.2f}")
