# Analyze Trades

Analyze recent trading performance from `data/transactions.csv`.

## Tasks

1. **Load and parse transactions**
   - Read `data/transactions.csv`
   - Filter to SELL transactions only (completed trades)
   - Calculate P&L for each closed position

2. **Calculate key metrics**
   - Win rate (% of trades with positive P&L)
   - Average win size vs average loss size
   - Profit factor (gross profits / gross losses)
   - Exit reason breakdown (STOP_LOSS vs TAKE_PROFIT vs SIGNAL)

3. **Pattern analysis**
   - Best/worst performing tickers
   - Average holding period
   - Day of week analysis (if enough data)
   - Recent trend (improving or declining?)

4. **Recommendations**
   - If win rate < 40%, suggest tightening entry criteria
   - If avg loss > avg win, suggest adjusting stop/target ratios
   - If mostly STOP_LOSS exits, consider volatility filter

## Output Format

Display as a clean terminal summary with sections for each analysis area.
Use the trade_analyzer.py module if helpful.

## Date Range (optional)

$ARGUMENTS

If provided, filter to trades within the specified date range.
