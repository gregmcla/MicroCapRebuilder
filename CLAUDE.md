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
│   ├── webapp.py               # Streamlit web dashboard
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
  "starting_capital": 50000.0,
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

### Web Dashboard

#### `webapp.py` - Streamlit Dashboard
Browser-based dashboard for daily portfolio check-ins.

**Launch:**
```bash
streamlit run scripts/webapp.py
```

**Features:**
- Portfolio summary metrics (equity, positions value, cash)
- Market regime display with bull/bear/sideways indicators
- Performance metrics (Sharpe ratio, max drawdown, total return)
- Trade statistics (win rate, profit factor, realized P&L)
- Positions table with color-coded P&L
- Recent transactions list
- Equity curve chart
- Auto-refresh button

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
- Starting capital: $50,000 (configurable)
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
streamlit      # Web dashboard
```

## Testing

Manual verification:
1. Run `./run_daily.sh` and check output
2. Review `reports/daily_report.txt`
3. Verify `data/transactions.csv` for new trades
4. Check `data/positions.csv` for current state
5. Verify `charts/performance.png` is generated


## Unified Analysis Architecture (New)

The system now uses a unified analysis pipeline that combines quantitative scoring with optional AI review:

### Key Files
- `unified_analysis.py` - Single source of truth for trading decisions
- `ai_review.py` - AI review layer (can APPROVE/MODIFY/VETO trades)
- `webapp.py` - Dashboard with ANALYZE → EXECUTE flow

### Flow
```
ANALYZE button → run_unified_analysis()
                    ↓
              1. Check stop/target triggers → proposed sells
              2. Score watchlist → proposed buys (limited by cash)
              3. AI reviews proposals (batched, 10 at a time)
                    ↓
              Show results with quant + AI reasoning
                    ↓
EXECUTE → execute_approved_actions()
```

### Cash Tracking
Position sizing now tracks remaining cash as buys are proposed:
- Each position is capped by available cash
- Skips positions when cash runs out
- Shows "(${amount} remaining)" in output


## Common Mistakes to Avoid

### Streamlit HTML Rendering
**Problem**: Multi-line f-strings with HTML cause Streamlit to escape tags, showing raw `</div>` in output.

**Solution**: Build HTML as concatenated single-line strings:
```python
# BAD - will show raw </div>
html = f'''<div class="card">
    <div class="title">{title}</div>
</div>'''

# GOOD - renders correctly
html = f'<div class="card">'
html += f'<div class="title">{title}</div>'
html += '</div>'
```

### Streamlit Form Auto-Triggering
**Problem**: `st.text_input` retains state across reruns, causing unintended actions when other buttons trigger page reloads.

**Solution**: Wrap inputs in a form with `clear_on_submit=True`:
```python
with st.form(key="my_form", clear_on_submit=True):
    user_input = st.text_input("Enter text")
    submitted = st.form_submit_button("Submit")
if submitted and user_input:
    # Only runs on explicit submit
```

### AI JSON Parsing
**Problem**: LLMs often return JSON with extra text, markdown blocks, or trailing commas.

**Solution**: Clean the response before parsing:
1. Strip markdown code blocks (`\`\`\`json ... \`\`\``)
2. Find JSON boundaries (`{` to `}`)
3. Remove trailing commas before `}` or `]`
4. Batch large requests (10 items max) to avoid truncation

### StockScorer Attributes
**Problem**: `StockScore` dataclass has individual score attributes, not a `factor_scores` dict.

**Solution**: Build the dict manually:
```python
factor_scores = {
    "momentum": s.momentum_score,
    "volatility": s.volatility_score,
    "volume": s.volume_score,
    "relative_strength": s.relative_strength_score,
    "mean_reversion": s.mean_reversion_score,
    "rsi": s.rsi_score,
}
```

### Cash Limit Enforcement
**Problem**: Proposing unlimited buys without tracking remaining cash.

**Solution**: Track remaining_cash as positions are proposed:
```python
remaining_cash = cash
for candidate in candidates:
    if shares * price > remaining_cash:
        print(f"Skipping {ticker} - insufficient cash")
        continue
    remaining_cash -= shares * price
```


## Project-Specific Commands

### Quick Analysis
```bash
# Run unified analysis (dry run)
python scripts/unified_analysis.py

# Run with execution
python scripts/unified_analysis.py --execute
```

### Dashboard
```bash
streamlit run scripts/webapp.py
```

### Watchlist Management
```bash
# Update watchlist with discovery
python scripts/watchlist_manager.py --update

# Show watchlist status
python scripts/watchlist_manager.py --status
```


## Session Notes

Keep notes from each development session in `docs/session_notes/` to maintain context across conversations. Update after significant changes.
