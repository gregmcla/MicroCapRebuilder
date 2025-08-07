#!/usr/bin/env python3
import sys, json
import pandas as pd

if len(sys.argv) != 2:
    sys.exit("usage: set_roi_baseline.py YYYY-MM-DD")

date = sys.argv[1]
df   = pd.read_csv("data/portfolio_update.csv", parse_dates=["Date"])
today = df[df["Date"] == date]

if today.empty:
    sys.exit(f"No rows for {date} in portfolio_update.csv")

# Prefer Total Equity if present
if "Total Equity" in today.columns:
    eq = float(today["Total Equity"].iloc[-1])
# Otherwise sum Shares * Current Price
else:
    eq = float((today["Shares"] * today["Current Price"]).sum())

out = {"date": date, "baseline_equity": eq}
print(json.dumps(out))
