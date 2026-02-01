# /fix-watchlist - Clean Up Watchlist

Remove stale or delisted tickers from the watchlist.

## Steps
1. Read `data/watchlist.jsonl`
2. For each ticker, try to fetch price via yfinance
3. Mark as stale/remove if:
   - Price fetch fails with "delisted" error
   - No price data available
   - Marked as STALE for more than 30 days
4. Report what was removed and current watchlist size

## Common Delisted Tickers to Check
- JBT (known issue)
- Any with "YFPricesMissingError"
