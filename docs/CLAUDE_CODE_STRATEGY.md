# Claude Code Strategy for MicroCapRebuilder

This document outlines concrete strategies for using Claude Code effectively with this trading system, based on tips from the Claude Code team.

## 1. Parallel Worktrees Strategy

Run multiple independent Claude sessions for different concerns:

```bash
# Create dedicated worktrees
git worktree add ../mcr-trading trading-logic
git worktree add ../mcr-analytics analytics
git worktree add ../mcr-backtest backtesting
git worktree add ../mcr-analysis main  # Read-only for logs/queries

# Shell aliases for quick switching
alias za='cd ../mcr-trading && claude'
alias zb='cd ../mcr-analytics && claude'
alias zc='cd ../mcr-backtest && claude'
alias zq='cd ../mcr-analysis && claude'  # Query/analysis only
```

**Recommended parallel workflows:**
| Worktree | Purpose | Example Tasks |
|----------|---------|---------------|
| `mcr-trading` | Trading logic changes | Modify `pick_from_watchlist.py`, `execute_sells.py` |
| `mcr-analytics` | Analytics improvements | Enhance `analytics.py`, `trade_analyzer.py` |
| `mcr-backtest` | Strategy backtesting | Test new scoring factors, regime detection |
| `mcr-analysis` | Read-only queries | Analyze `transactions.csv`, run ad-hoc yfinance queries |

## 2. Plan Mode Workflow

For complex trading features, always start in plan mode:

```
/plan Add a new momentum divergence indicator to stock_scorer.py
```

**Two-Claude Review Pattern:**
1. Claude A creates the plan
2. Ask Claude A: "Review this plan as a senior quant would. What edge cases around market data gaps or corporate actions am I missing?"
3. Or spin up Claude B to independently review

**Re-plan triggers (switch back to plan mode if):**
- yfinance API returns unexpected data structure
- Position calculations don't match expected values
- Stop loss logic has edge cases around after-hours moves

**Trading-specific plan prompts:**
```
/plan Implement volatility-adjusted position sizing that accounts for
overnight gap risk in microcaps. Consider correlation with market regime.
```

## 3. CLAUDE.md Self-Rules

End every correction session with:
```
Update CLAUDE.md so you don't make that mistake again.
Add this to the "AI Assistant Rules" section.
```

**Example self-rules for this project:**
```markdown
## AI Assistant Rules (Learned)

- Never assume market is open - always check trading hours before live price fetches
- When calculating cash, derive from transactions.csv, never store separately
- yfinance returns NaN for delisted tickers - always handle with .dropna()
- Stop loss prices must be BELOW entry for longs (sanity check: stop < entry < take_profit)
- Position sizing calculation: shares = (equity * risk_pct) / (entry - stop_loss)
```

## 4. Custom Slash Commands

Create `.claude/commands/` directory with trading-specific skills:

### `/analyze-trades` - Quick Trade Analysis
```markdown
# .claude/commands/analyze-trades.md
Analyze recent trades in data/transactions.csv:
1. Calculate win rate for last 30 days
2. Compare STOP_LOSS vs TAKE_PROFIT exit frequency
3. Identify any patterns (time of week, sector, etc.)
4. Suggest parameter adjustments based on findings

Use pandas and output a formatted summary.
```

### `/portfolio-status` - Quick Portfolio Check
```markdown
# .claude/commands/portfolio-status.md
Generate a quick portfolio status:
1. Read data/positions.csv and show current holdings
2. Fetch live prices via yfinance for each position
3. Calculate real-time P&L
4. Show which positions are near stop loss or take profit
5. Display current market regime

Output as a clean terminal table.
```

### `/validate-data` - Data Integrity Check
```markdown
# .claude/commands/validate-data.md
Validate data integrity across all CSV files:
1. Check transactions.csv has no orphaned sells
2. Verify positions.csv matches transaction history
3. Ensure daily_snapshots.csv has no gaps
4. Validate stop_loss < entry < take_profit for all positions
5. Check for duplicate transaction_ids

Report any issues found.
```

### `/backtest-strategy` - Quick Backtest
```markdown
# .claude/commands/backtest-strategy.md
Run a quick backtest:
1. Load historical data from watchlist tickers via yfinance
2. Apply current scoring logic from stock_scorer.py
3. Simulate trades with config.json parameters
4. Calculate Sharpe ratio, max drawdown, win rate
5. Compare to benchmark (^RUT)

Accept optional date range parameter: $ARGUMENTS
```

### `/techdebt` - Code Cleanup
```markdown
# .claude/commands/techdebt.md
Find and fix technical debt:
1. Search for TODO/FIXME comments in scripts/
2. Identify duplicated code across modules
3. Check for hardcoded values that should be in config.json
4. Find unused imports
5. Suggest consolidation opportunities

Create a prioritized list and optionally fix top items.
```

## 5. Bug Fixing Automation

**CI Failure Pattern:**
```
Go fix the failing tests in scripts/test_integration.py.
Don't ask me questions - debug and fix.
```

**Data Issue Pattern:**
```
positions.csv shows negative shares for CRDO.
Investigate transactions.csv, find the bug, and fix it.
```

**Price Fetch Issues:**
```
yfinance is returning NaN for several tickers.
Check which ones are delisted, update watchlist.jsonl,
and add defensive handling to all price fetch code.
```

## 6. Advanced Prompting for Trading

**Challenge Claude for Better Strategies:**
```
Grill me on this scoring algorithm. What market conditions
would cause it to fail? What factor tilts am I missing?
Don't be nice - I want to find weaknesses.
```

**Elegant Solutions:**
```
The position sizing logic in pick_from_watchlist.py is getting messy.
Knowing everything you know about risk management and this codebase,
scrap the current approach and implement the elegant solution.
```

**Prove It Works:**
```
Prove to me that the stop loss logic in execute_sells.py correctly
handles after-hours gaps. Show me the edge cases and verify each one.
```

## 7. Subagent Usage

Append "use subagents" for complex analysis:

```
Optimize the stock_scorer.py weights to maximize Sharpe ratio
over the last year of data. Use subagents to test multiple
weight combinations in parallel.
```

**Keep main context clean by offloading:**
- Historical data fetching to subagent
- Complex backtesting calculations to subagent
- Multi-factor optimization to subagent

## 8. Data Analysis with CLI Tools

**yfinance for market data:**
```python
# Claude can run this directly
import yfinance as yf
spy = yf.Ticker("SPY")
print(spy.history(period="1mo"))
```

**Pandas for transaction analysis:**
```
Load transactions.csv and tell me:
- Average holding period for winning trades
- Most profitable ticker
- Day of week with best win rate
- Correlation between position size and outcome
```

**Ad-hoc market queries:**
```
Fetch the current market regime indicators:
- SPY vs 50-day and 200-day SMA
- VIX level
- Put/call ratio if available
Give me a bull/bear/sideways assessment.
```

## 9. Learning Mode Usage

Enable explanatory output in `/config` for:
- Understanding new yfinance API features
- Learning about trading concepts (Sharpe, Sortino, Calmar)
- Understanding why certain risk parameters matter

**Request visual explanations:**
```
Create an HTML presentation explaining the market regime
detection logic in market_regime.py. Include diagrams
showing how SMA crossovers determine bull/bear/sideways.
```

**Request ASCII diagrams:**
```
Draw an ASCII diagram showing the data flow:
watchlist.jsonl -> stock_scorer.py -> pick_from_watchlist.py -> transactions.csv
Show how positions.csv is derived.
```

## 10. Terminal Setup Recommendations

**Statusline should show:**
- Current git branch
- Context usage (important for long trading analysis sessions)
- Last portfolio equity (via custom script)

**Tab naming convention:**
```
Tab 1: [TRADE] - Active trading logic development
Tab 2: [ANALYZE] - Read-only analysis
Tab 3: [BACKTEST] - Strategy testing
Tab 4: [DAILY] - Running ./run_daily.sh
```

**Voice dictation for detailed prompts:**
Voice input is 3x faster - especially useful for describing complex trading scenarios:
```
"I want to add a mean reversion component to the scorer that
identifies when a stock has dropped more than two standard
deviations from its twenty day moving average but is showing
volume confirmation of a potential reversal..."
```

---

## Quick Reference

| Tip | Command/Action |
|-----|----------------|
| Quick analysis | `/portfolio-status` |
| Check data integrity | `/validate-data` |
| After any correction | "Update CLAUDE.md so you don't make that mistake again" |
| Complex feature | Start with `/plan` |
| Failing tests | "Go fix the failing tests, don't ask questions" |
| Optimize strategy | "Use subagents to test parameter combinations" |
| Understand code | "Create an ASCII diagram of the data flow" |
