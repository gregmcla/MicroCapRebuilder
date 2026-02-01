# Validate Data Integrity

Check all data files for consistency and integrity issues.

## Validation Checks

### 1. Transaction Ledger (`data/transactions.csv`)
- All required columns present per schema.py
- No duplicate transaction_ids
- All dates are valid ISO format
- All actions are BUY or SELL
- All reasons are valid (SIGNAL, STOP_LOSS, TAKE_PROFIT, MANUAL, MIGRATION)
- No negative shares or prices
- total_value = shares * price (within rounding tolerance)

### 2. Position Consistency
- For each SELL, verify a corresponding prior BUY exists
- No "orphaned" sells (selling more than bought)
- Current positions in `positions.csv` match net from transactions
- stop_loss < avg_cost_basis < take_profit for all positions

### 3. Daily Snapshots (`data/daily_snapshots.csv`)
- No date gaps (weekends/holidays acceptable)
- No duplicate dates
- total_equity = cash + positions_value
- Equity curve is monotonically dated

### 4. Positions File (`data/positions.csv`)
- All required columns present
- No negative shares
- market_value = shares * current_price
- unrealized_pnl = market_value - (shares * avg_cost_basis)

### 5. Config Validation (`data/config.json`)
- All required keys present
- Values within reasonable bounds
- stop_loss_pct < take_profit_pct

### 6. Watchlist (`data/watchlist.jsonl`)
- Valid JSON on each line
- Each entry has ticker field
- No duplicate tickers

## Output

Report each check as PASS or FAIL with details.
Provide a summary count at the end.
If any FAIL, suggest specific fixes.
