# CLAUDE.md - AI Assistant Guide for MicroCapRebuilder

## Project Overview

MicroCapRebuilder is an **intelligent, risk-managed portfolio trading system** for microcap stocks. The system features:

- **Multi-factor stock scoring** (momentum, volatility, volume, relative strength)
- **Market regime detection** (bull/bear/sideways adaptation)
- **Automated risk management** (stop losses, take profits, position limits)
- **Professional analytics** (Sharpe ratio, drawdown, win rate)
- **Daily reporting** with comprehensive metrics

## Directory Structure

```
MicroCapRebuilder/
├── scripts/                    # Python execution scripts
│   ├── pick_from_watchlist.py  # Intelligent stock picker with scoring
│   ├── execute_sells.py        # Stop loss / take profit execution
│   ├── update_positions.py     # Position updates with live prices
│   ├── stock_scorer.py         # Multi-factor scoring module
│   ├── market_regime.py        # Bull/bear/sideways detection
│   ├── risk_manager.py         # Risk management module
│   ├── analytics.py            # Risk-adjusted metrics (Sharpe, etc.)
│   ├── trade_analyzer.py       # Trade performance analysis
│   ├── generate_report.py      # Daily text report generation
│   ├── generate_graph.py       # Performance chart generation
│   ├── overlay_stats.py        # Statistics overlay on charts
│   ├── schema.py               # Centralized data schemas
│   ├── migrate_data.py         # Legacy data migration (one-time)
│   ├── set_roi_baseline.py     # ROI baseline recording
│   └── build_watchlist.py      # Watchlist generator
├── data/                       # Data files
│   ├── config.json             # Centralized configuration
│   ├── watchlist.jsonl         # Stock watchlist (66 tickers)
│   ├── transactions.csv        # Unified transaction ledger
│   ├── positions.csv           # Current holdings
│   └── daily_snapshots.csv     # Daily equity snapshots
├── reports/                    # Generated reports
│   └── daily_report.txt        # Daily summary report
├── charts/                     # Generated charts
├── backup/                     # Data backups
├── run_daily.sh                # Main orchestration script
├── requirements.txt            # Python dependencies
└── .gitignore                  # Version control rules
```

## Key Configuration (`data/config.json`)

```json
{
  "starting_capital": 5000.0,
  "risk_per_trade_pct": 10.0,
  "max_position_pct": 15.0,
  "max_positions": 15,
  "default_stop_loss_pct": 8.0,
  "default_take_profit_pct": 20.0,
  "volatility_lookback_days": 20,
  "benchmark_symbol": "^RUT",
  "fallback_benchmark": "IWM",
  "chart_days": 30
}
```

## Core Scripts

### Trading Logic

#### `pick_from_watchlist.py` - Intelligent Stock Picker
Scores and ranks watchlist candidates, then executes buys with risk management.

**Workflow:**
1. Check market regime (skip buying in bear markets)
2. Load current positions and cash
3. Score all candidates using multi-factor model
4. Select top picks that pass portfolio limits
5. Calculate volatility-adjusted position sizes
6. Set stop loss (-8%) and take profit (+20%) at entry
7. Record transactions to `transactions.csv`

#### `execute_sells.py` - Automated Sell Execution
Checks all positions for stop loss and take profit triggers.

**Workflow:**
1. Load positions with stop/take profit levels
2. Fetch current prices
3. Check for triggered stops or targets
4. Execute sells and record to `transactions.csv`
5. Remove sold positions from `positions.csv`

#### `update_positions.py` - Position Updates
Updates positions with current prices and records daily snapshot.

**Workflow:**
1. Fetch current prices for all positions
2. Calculate unrealized P&L
3. Update `positions.csv` with current values
4. Append daily snapshot to `daily_snapshots.csv`

### Scoring & Analysis

#### `stock_scorer.py` - Multi-Factor Scoring
Scores stocks on 5 factors (weights in parentheses):
- **Momentum (30%)**: 20-day price change
- **Volatility (20%)**: Lower volatility = higher score
- **Volume (15%)**: Recent vs average volume (liquidity)
- **Relative Strength (25%)**: Performance vs Russell 2000
- **Mean Reversion (10%)**: Distance from 20-day SMA

Also calculates ATR% for volatility-adjusted position sizing.

#### `market_regime.py` - Market Regime Detection
Detects market conditions using benchmark moving averages:
- **BULL**: Above 50-day and 200-day SMA → 100% position size
- **SIDEWAYS**: Mixed signals → 50% position size
- **BEAR**: Below both SMAs → No new buys

#### `risk_manager.py` - Risk Management
- Stop loss checking
- Take profit checking
- Volatility-adjusted position sizing
- Portfolio concentration limits

#### `analytics.py` - Portfolio Analytics
Calculates professional metrics:
- Sharpe Ratio, Sortino Ratio
- Maximum Drawdown, Current Drawdown
- Calmar Ratio, CAGR
- Annual Volatility, Exposure %

#### `trade_analyzer.py` - Trade Analysis
Analyzes completed trades:
- Win rate, Profit factor
- Average win/loss
- Best/worst trades
- Stats by exit reason (stop loss vs take profit)

### Reporting

#### `generate_report.py` - Daily Report
Generates comprehensive text report (`reports/daily_report.txt`):
- Portfolio summary (equity, cash, positions)
- Today's activity
- Performance metrics
- Trade statistics
- Current positions with stops/targets
- Recent trade history

## Data Schemas

### `transactions.csv` (Unified Ledger)
```csv
transaction_id,date,ticker,action,shares,price,total_value,stop_loss,take_profit,reason
d08b2cc8,2026-01-27,CRDO,BUY,1,117.96,117.96,108.52,141.55,SIGNAL
```

Actions: `BUY`, `SELL`
Reasons: `SIGNAL`, `STOP_LOSS`, `TAKE_PROFIT`, `MANUAL`, `MIGRATION`

### `positions.csv` (Current Holdings)
```csv
ticker,shares,avg_cost_basis,current_price,market_value,unrealized_pnl,unrealized_pnl_pct,stop_loss,take_profit,entry_date
CRDO,2,118.87,120.50,241.00,4.26,1.80,109.36,142.64,2026-01-27
```

### `daily_snapshots.csv` (Equity Curve)
```csv
date,cash,positions_value,total_equity,day_pnl,day_pnl_pct,benchmark_value
2026-01-27,2484.30,2515.50,4999.80,-0.20,-0.00,
```

## Daily Workflow

Run the orchestration script:
```bash
./run_daily.sh
```

**Execution Order:**
1. `execute_sells.py` - Check stop loss / take profit triggers
2. `pick_from_watchlist.py` - Score and buy new positions
3. `update_positions.py` - Update prices and daily snapshot
4. `generate_graph.py` - Create performance chart
5. `overlay_stats.py` - Add statistics to chart

## Setup

### Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Initial Migration (One-Time)
If starting with legacy data:
```bash
python scripts/migrate_data.py
```

## Code Conventions

### Style
- Python 3 shebang: `#!/usr/bin/env python3`
- Imports from `schema.py` for consistent column names
- Section comments: `# ─── Section Name ───`
- Emoji feedback: `✅` success, `⚠️` warning, `🐂` bull, `🐻` bear

### Path Handling
- Use `pathlib.Path` for all file paths
- Navigate from script: `Path(__file__).parent.parent / "data"`

### Module Imports
```python
from schema import TRANSACTION_COLUMNS, Action, Reason
from risk_manager import RiskManager
from stock_scorer import StockScorer
from market_regime import get_market_regime, MarketRegime
```

## Important Notes for AI Assistants

### Configuration
- All parameters are in `data/config.json` - don't hardcode
- Starting capital: $5,000 (configurable)
- Risk per trade: 10% (configurable)
- Stop loss: 8%, Take profit: 20% (configurable)

### Data Integrity
- Always use `schema.py` column constants
- Transactions are the source of truth for positions
- Cash is calculated from transactions, not stored directly

### Risk Management
- Stop losses and take profits are set at entry
- Position sizes are volatility-adjusted
- Market regime affects position sizing (0-100%)
- Max 15 positions, max 15% per position

### Files That Are Gitignored
- `data/*.csv` (except config.json via `!data/config.json`)
- `charts/`, `reports/`, `backup/`, `logs/`
- `.venv/`, `__pycache__/`

## Dependencies

```
yfinance       # Stock price data
pandas         # Data manipulation
numpy          # Analytics calculations
matplotlib     # Chart generation
python-dotenv  # Environment variables
```

## Testing

Manual verification:
1. Run `./run_daily.sh` and check output
2. Review `reports/daily_report.txt`
3. Verify `data/transactions.csv` for new trades
4. Check `data/positions.csv` for current state
5. Verify `charts/performance.png` is generated

## Claude Code Integration

### Custom Slash Commands

Available commands in `.claude/commands/`:

| Command | Purpose |
|---------|---------|
| `/analyze-trades` | Analyze recent trading performance and patterns |
| `/portfolio-status` | Real-time portfolio check with live prices |
| `/validate-data` | Check data integrity across all CSV files |
| `/backtest-strategy` | Run backtests against historical data |
| `/techdebt` | Find and catalog technical debt |
| `/market-check` | Quick market conditions assessment |

### Advanced Usage

See `docs/CLAUDE_CODE_STRATEGY.md` for:
- Parallel worktree setup for concurrent development
- Plan mode workflows for complex features
- Subagent usage for compute-heavy analysis
- Bug fixing automation patterns

## AI Assistant Self-Rules (Learned)

Rules accumulated from corrections - **do not violate these**:

### Market Data
- Never assume market is open - always check trading hours before live price fetches
- yfinance returns NaN for delisted/invalid tickers - always handle with `.dropna()` or explicit checks
- Weekend/holiday dates have no price data - skip these in backtests
- Use `period` parameter for recent data, `start/end` for specific ranges

### Position Calculations
- Cash is DERIVED from transactions, never stored directly - recalculate from transaction history
- Stop loss prices must be BELOW entry for longs: `stop_loss < avg_cost_basis < take_profit`
- Position sizing: `shares = floor((equity * risk_pct) / (entry - stop_loss))`
- Never allow negative shares or negative cash in any calculation

### Data Integrity
- Always use `schema.py` constants for column names - never hardcode strings
- When writing CSVs, use `index=False` to avoid extra index column
- Transaction IDs must be unique UUIDs - generate with `uuid.uuid4().hex[:8]`
- Append to `transactions.csv`, never overwrite (it's a ledger)

### Error Handling
- Wrap all yfinance calls in try/except - API can fail
- Log failures but don't crash the daily run for single ticker failures
- If >50% of price fetches fail, something is wrong - abort and alert

### Testing Changes
- After modifying trading logic, verify with: current positions match transactions
- After modifying scoring, verify: all scores between 0-100, no NaN values
- Run `./run_daily.sh` after any change to validate full pipeline
