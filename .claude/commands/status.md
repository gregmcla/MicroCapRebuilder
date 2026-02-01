# /status - Portfolio Status Check

Quick check of current portfolio state.

## Steps
1. Read `data/positions.csv` and summarize holdings
2. Read `data/daily_snapshots.csv` for recent equity
3. Calculate: total equity, cash, unrealized P&L, number of positions
4. Check for positions near stop loss or take profit

## Output Format
```
Portfolio Status
----------------
Equity: $XX,XXX (+X.X% all-time)
Cash: $XX,XXX (XX% available)
Positions: XX ($XX,XXX invested)
Unrealized P&L: +$XXX

⚠️ Near Stop: [tickers within 3% of stop]
✅ Near Target: [tickers within 5% of target]
```
