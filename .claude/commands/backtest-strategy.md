# Backtest Strategy

Run a backtest of the current trading strategy against historical data.

## Parameters

$ARGUMENTS

Expected format: `--start 2025-01-01 --end 2025-12-31` (optional)
Default: Last 252 trading days (1 year)

## Backtest Steps

1. **Load configuration**
   - Read `data/config.json` for all parameters
   - Load watchlist from `data/watchlist.jsonl`

2. **Fetch historical data**
   - Use yfinance to get daily OHLCV for all watchlist tickers
   - Also fetch benchmark (^RUT) for comparison
   - Handle missing data gracefully

3. **Simulate trading**
   - Start with `starting_capital` from config
   - For each trading day:
     a. Check existing positions for stop_loss / take_profit triggers
     b. Run stock_scorer.py logic to rank candidates
     c. Apply market_regime.py to determine position sizing
     d. Execute simulated buys respecting max_positions and concentration limits
     e. Record daily equity

4. **Calculate metrics**
   - Total return (%)
   - Annualized return (CAGR)
   - Sharpe ratio (vs risk-free rate of 4%)
   - Sortino ratio
   - Maximum drawdown (%)
   - Win rate
   - Profit factor
   - Average holding period

5. **Benchmark comparison**
   - Calculate same metrics for buy-and-hold benchmark
   - Show relative performance

6. **Trade log**
   - List all simulated trades
   - Show exit reasons breakdown

## Output

Formatted summary with:
- Performance metrics table
- Equity curve description
- Trade statistics
- Comparison to benchmark
- Key observations and potential improvements
