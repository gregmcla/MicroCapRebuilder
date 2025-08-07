#!/usr/bin/env python3
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, required=True)
parser.add_argument("--bench", required=True)
parser.add_argument("--fallback", required=True)
args = parser.parse_args()

pf = pd.read_csv("data/portfolio_update.csv", parse_dates=["Date"]).set_index("Date")
eq = pf["Equity"].resample("D").ffill()

end = eq.index.max()
start = end - pd.Timedelta(days=args.days - 1)
eq = eq[start:]


def fetch_benchmark(symbol: str) -> pd.Series:
    data = yf.download(symbol, start=start, end=end + pd.Timedelta(days=1), progress=False)
    if data.empty:
        raise ValueError(f"no data for {symbol}")
    return data["Adj Close"]


bench_symbol = args.bench
bench = None
try:
    bench = fetch_benchmark(bench_symbol)
except Exception:
    print(f"⚠️ Failed to download {bench_symbol}, trying fallback {args.fallback}")
    bench_symbol = args.fallback
    try:
        bench = fetch_benchmark(bench_symbol)
        print(f"⚠️ Falling back to {bench_symbol}")
    except Exception:
        print(f"⚠️ Failed to download fallback benchmark {bench_symbol}. Proceeding without benchmark")

fig, ax = plt.subplots()
ax.plot(eq.index, eq.values, label="Equity")
if bench is not None:
    bench = bench.reindex(eq.index, method="ffill")
    ax.plot(bench.index, bench.values, label=bench_symbol)
    ax.set_title(f"Equity vs {bench_symbol} last {args.days} days")
else:
    ax.set_title(f"Equity last {args.days} days")
ax.legend()
plt.tight_layout()
Path("charts").mkdir(exist_ok=True)
plt.savefig("charts/performance.png")
print("✅ Chart saved to charts/performance.png")
