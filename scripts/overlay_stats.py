#!/usr/bin/env python3
import pandas as pd, json, argparse
from matplotlib import pyplot as plt
from matplotlib.offsetbox import AnchoredText

p = argparse.ArgumentParser()
p.add_argument("--csv"); p.add_argument("--trades"); p.add_argument("--baseline"); p.add_argument("--img")
args = p.parse_args()

# load data
df = pd.read_csv(args.csv)
trades = pd.read_csv(args.trades) if args.trades else pd.DataFrame()
base = json.load(open(args.baseline))

# compute stats
total_equity = (df["Shares"] * df["Price"]).sum()
buy_count  = len(trades[trades["Shares Bought"]>0])    if "Shares Bought" in trades else 0
sell_count = len(trades[trades["Shares Sold"]>0])      if "Shares Sold" in trades else 0
roi = (total_equity - base["baseline_equity"]) / base["baseline_equity"] * 100

# overlay
img = plt.imread(args.img)
fig,ax = plt.subplots(figsize=(10,6))
ax.imshow(img); ax.axis("off")
txt = (
  f"Equity: ${total_equity:,.2f}\n"
  f"Buys today: {buy_count}\n"
  f"Sells today: {sell_count}\n"
  f"ROI since {base['date']}: {roi:.2f}%"
)
at = AnchoredText(txt, loc='upper left', prop=dict(size=10), pad=0.5, frameon=True)
ax.add_artist(at)
fig.savefig(args.img, dpi=150, bbox_inches="tight")
