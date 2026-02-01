# /analyze - Run Trading Analysis

Run the unified analysis system to check for trading opportunities.

## Steps
1. Run `python scripts/unified_analysis.py` and show the output
2. Summarize: number of proposed buys/sells, cash remaining, any skipped tickers
3. If there are proposals, ask if user wants to execute

## Example Output Summary
- Proposed: X buys, Y sells
- Top picks: [list top 3 by score]
- Cash after: $X,XXX
- Skipped: N tickers (insufficient cash)
