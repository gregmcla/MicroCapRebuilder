#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, required=True)
parser.add_argument("--bench", required=True)
parser.add_argument("--fallback", required=True)
args = parser.parse_args()

pf = pd.read_csv("data/portfolio_update.csv", parse_dates=["Date"]).set_index("Date")
eq = pf["Equity"].resample("D").ffill()
bench = pd.read_csv("data/portfolio_update.csv", parse_dates=["Date"]).set_index("Date")  # placeholder
fig, ax = plt.subplots()
ax.plot(eq.index, eq.values, label="Equity")
ax.set_title(f"Equity last {args.days} days")
ax.legend()
plt.tight_layout()
plt.savefig("charts/performance.png")
print("✅ Chart saved to charts/performance.png")
