# Portfolio Status

Generate a real-time portfolio status check.

## Tasks

1. **Load current positions**
   - Read `data/positions.csv`
   - Display ticker, shares, avg cost, entry date

2. **Fetch live prices**
   - Use yfinance to get current prices for each position
   - Handle any failed fetches gracefully

3. **Calculate real-time P&L**
   - Current value vs cost basis
   - Unrealized P&L ($) and (%)
   - Total portfolio value

4. **Risk status for each position**
   - Distance to stop loss (%)
   - Distance to take profit (%)
   - Flag positions within 2% of either trigger

5. **Market regime check**
   - Fetch benchmark (^RUT or IWM) current status
   - Calculate vs 50-day and 200-day SMA
   - Display current regime: BULL / BEAR / SIDEWAYS

6. **Portfolio summary**
   - Total equity
   - Cash available
   - Number of positions vs max (15)
   - Largest position concentration

## Output Format

Clean terminal table with:
- Position details
- Color indicators (green/red for P&L)
- Alert flags for near-trigger positions
- Summary statistics at bottom
