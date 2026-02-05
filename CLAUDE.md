# CLAUDE.md - AI Assistant Guide for MicroCapRebuilder

## Project Overview

MicroCapRebuilder (aka **Mommy Bot**) is an **intelligent, adaptive portfolio trading system** for microcap stocks. The system features:

- **Multi-factor stock scoring** (momentum, volatility, volume, relative strength, RSI)
- **Market regime detection** (bull/bear/sideways adaptation)
- **Automated risk management** (stop losses, take profits, position sizing)
- **Professional analytics** (Sharpe ratio, drawdown, win rate)
- **Adaptive Strategy System** (PIVOT analysis, health monitoring, early warnings)
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
│   ├── webapp.py               # Streamlit web dashboard (tab-based)
│   ├── webapp_styles.py        # CSS design system
│   ├── webapp_components.py    # Reusable UI components
│   ├── webapp_helpers.py       # Dashboard helper functions
│   ├── avatar_svg.py           # SVG avatar generator
│   ├── avatar_states.py        # Avatar state management
│   ├── portfolio_chat.py       # AI chat functionality
│   ├── overlay_stats.py        # Statistics overlay on charts
│   ├── schema.py               # Centralized data schemas
│   ├── migrate_data.py         # Legacy data migration (one-time)
│   ├── set_roi_baseline.py     # ROI baseline recording
│   ├── build_watchlist.py      # Watchlist generator
│   ├── watchlist_manager.py    # Watchlist discovery and management
│   ├── strategy_health.py      # Strategy Health Dashboard (A-F grading)
│   ├── strategy_pivot.py       # PIVOT analysis and recommendations
│   └── early_warning.py        # Early warning system
├── run_dashboard.sh            # Auto-pull + start dashboard
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
Browser-based dashboard with **tab-based navigation architecture** for reduced cognitive load.

**Launch:**
```bash
streamlit run scripts/webapp.py
```

Or use the auto-pull helper (pulls latest changes before running):
```bash
./run_dashboard.sh
```

#### Dashboard Architecture (Tab-Based Navigation)

The dashboard uses a tab-based navigation system instead of a single mega-scroll page:

| Tab | Contents |
|-----|----------|
| **Dashboard** | Alerts (positions near stop/target), Top 5 positions needing attention, Compact equity curve, Recent activity |
| **Positions** | Full positions list, Cards/Table toggle, REFRESH and UPDATE buttons |
| **Analysis** | ANALYZE + EXECUTE buttons, AI review results, Portfolio treemap, Risk metrics, Diversification |
| **Activity** | Full transaction history, Trade history/journal |
| **Discover** | RUN DISCOVERY button for stock screening |

#### Global Elements (Always Visible)

1. **Header Bar**: Logo + Navigation tabs + Status dot + LIVE/PAPER toggle + ⚠️ Emergency button
2. **Compact Metrics Strip** (50px): Equity | Today P&L | Total P&L | Cash | Regime badge
3. **Mommy Sidebar** (persistent right panel): Avatar, greeting, insights, chat input

#### Key Dashboard Files

```
scripts/
├── webapp.py              # Main dashboard (tab-based navigation)
├── webapp_styles.py       # CSS design system (colors, typography, components)
├── webapp_components.py   # Reusable UI components (cards, charts, etc.)
├── webapp_helpers.py      # Helper functions (greetings, calculations)
├── avatar_svg.py          # Programmatic SVG avatar generator (4 expressions)
├── avatar_states.py       # Avatar state management based on portfolio conditions
└── portfolio_chat.py      # AI chat functionality
```

#### Avatar System

The Mommy avatar has 4 expressions determined by portfolio state:
- **neutral**: Default state
- **pleased**: Good day P&L or positions near targets
- **concerned**: Positions near stop loss or high drawdown
- **skeptical**: Bear market regime

```python
from avatar_svg import get_avatar_svg
from avatar_states import determine_avatar_state_simple

state = determine_avatar_state_simple(day_pnl=100, positions_near_stop=0, ...)
svg = get_avatar_svg(state.value, size=80)
```

#### Session State Keys

The dashboard uses these Streamlit session state keys:
- `current_tab`: Active navigation tab ("Dashboard", "Positions", etc.)
- `unified_analysis`: Results from ANALYZE button
- `show_execute_confirm`: Execute confirmation dialog
- `show_emergency_modal`: Emergency controls modal
- `mommy_chat_response`: Persisted chat response
- `view_mode`: Positions view mode ("cards" or "table")
- `chart_timeframe`: Equity curve timeframe ("1W", "1M", "3M", "YTD", "ALL")

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
anthropic      # Claude AI for chat and review (optional)
```


## Paper Mode vs Live Mode

The system supports two modes controlled via `data/config.json`:

```python
# In config.json
"mode": "paper"  # or "live"
```

**Paper Mode:**
- Uses separate data files: `positions_paper.csv`, `transactions_paper.csv`, `daily_snapshots_paper.csv`
- Safe for testing without affecting real portfolio data
- Toggle via LIVE/PAPER button in dashboard header

**Live Mode:**
- Uses main data files: `positions.csv`, `transactions.csv`, `daily_snapshots.csv`
- Real portfolio tracking

```python
# How it works in code
def get_data_files():
    suffix = "_paper" if is_paper_mode() else ""
    return {
        "positions": DATA_DIR / f"positions{suffix}.csv",
        "transactions": DATA_DIR / f"transactions{suffix}.csv",
        "snapshots": DATA_DIR / f"daily_snapshots{suffix}.csv",
    }
```


## AI Chat System (Mommy Chat)

The dashboard includes an AI chat feature powered by Claude:

### Key Files
- `portfolio_chat.py` - Chat interface with portfolio context
- Requires `ANTHROPIC_API_KEY` in `.env` file

### How It Works
1. User asks a question in the sidebar
2. System builds context from current positions, transactions, metrics
3. Claude responds with portfolio-aware advice
4. Response persists in session state until cleared

### Setup
```bash
# Add to .env file
ANTHROPIC_API_KEY=sk-ant-...
```

### Chat Context Includes
- Current positions with P&L
- Recent transactions
- Risk metrics (Sharpe, drawdown)
- Market regime
- Positions near stops/targets


## Watchlist & Universe Expansion

### Watchlist File
`data/watchlist.jsonl` - One JSON object per line:
```json
{"ticker": "CRDO", "added": "2026-01-15", "source": "discovery"}
```

### Discovery System (`watchlist_manager.py`)
Scans for new candidates using multiple strategies:
- **Momentum breakouts**: Stocks breaking above resistance
- **Oversold bounces**: RSI < 30 with reversal signals
- **Sector leaders**: Top performers in each sector
- **Volume surges**: Unusual volume with price movement

```bash
# Run discovery
python scripts/watchlist_manager.py --update

# From dashboard: click DISCOVER button
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


## Design System

The dashboard uses a custom design system defined in `webapp_styles.py`:

### Color Palette
```python
COLORS = {
    "bg_primary": "#0A1628",      # Deep navy background
    "bg_card": "#111D2E",         # Card background
    "accent_teal": "#4FD1C5",     # Primary accent (teal)
    "success": "#48BB78",         # Green (profits, bull)
    "warning": "#ED8936",         # Orange (caution)
    "danger": "#F56565",          # Red (losses, bear, stops)
    "text_primary": "#F7FAFC",    # Main text
    "text_secondary": "#A0AEC0",  # Secondary text
    "text_muted": "#4A5568",      # Muted text
}
```

### Typography
- **Display font**: Fraunces (serif) - for headers and branding
- **Body font**: Inter (sans-serif) - for content

### CSS Classes (defined in webapp_styles.py)
- `.metrics-strip` - Compact top metrics bar
- `.nav-tab` / `.nav-tab.active` - Navigation tabs
- `.alert-card` / `.alert-card.danger` / `.alert-card.success` - Alert cards
- `.regime-badge.bull` / `.bear` / `.sideways` - Regime indicators
- `.mommy-avatar-container` - Avatar with breathing animation
- `.quick-chips` / `.quick-chip` - Chat quick-action chips


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

### Streamlit Chat Response Persistence
**Problem**: Chat responses disappear after form submission because the page reruns.

**Solution**: Store response in session state and display OUTSIDE the submit block:
```python
# Initialize session state
if "chat_response" not in st.session_state:
    st.session_state.chat_response = None

# Form with clear_on_submit
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask", label_visibility="collapsed")
    submitted = st.form_submit_button("Send")

# Process submission and store in session state
if submitted and user_input:
    response = ai_chat(user_input)
    if response.success:
        st.session_state.chat_response = response.message

# Display OUTSIDE the if block so it persists across reruns
if st.session_state.chat_response:
    st.markdown(f'"{st.session_state.chat_response}"')
    if st.button("Clear"):
        st.session_state.chat_response = None
        st.rerun()
```

### SVG Rendering in Streamlit
**Problem**: SVG gradients (`<linearGradient>`) and filters don't render in Streamlit's markdown.

**Solution**: Use solid colors instead of gradients:
```python
# BAD - gradients won't render
svg = '<linearGradient id="grad"><stop offset="0%" stop-color="#4FD1C5"/></linearGradient>'
svg += '<circle fill="url(#grad)"/>'

# GOOD - solid colors work
svg = '<circle fill="#4FD1C5"/>'
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


## Git Workflow

### Branch Structure
- `main` - Stable production code
- `claude/*` - Feature branches created by Claude Code sessions

### Common Issue: Local config.json Conflicts
The dashboard modifies `data/config.json` when toggling LIVE/PAPER mode. This causes merge conflicts when pulling.

**Fix:**
```bash
git checkout data/config.json
git pull origin <branch-name>
```

### Auto-Pull Script
`run_dashboard.sh` automatically pulls before starting:
```bash
#!/bin/bash
cd ~/MicroCapRebuilder
git pull origin claude/add-claude-documentation-SJTa1
source .venv/bin/activate
streamlit run scripts/webapp.py
```


## Session Notes

Keep notes from each development session in `docs/session_notes/` to maintain context across conversations. Update after significant changes.


## Adaptive Strategy System (New)

The system now includes an adaptive strategy layer that monitors performance and suggests strategic pivots when conditions change.

### Key Files
- `strategy_health.py` - Strategy Health Dashboard (A-F grading)
- `strategy_pivot.py` - PIVOT analyzer and recommendation engine
- `early_warning.py` - Early warning system for detecting issues

### PIVOT Button

The PIVOT button in the dashboard performs holistic strategy analysis:

1. **Strategy Health Check** - Grades strategy A-F across 5 components:
   - Performance (30%): Returns, Sharpe ratio, alpha
   - Risk Control (25%): Drawdown, stop adherence
   - Trading Edge (20%): Win rate, profit factor
   - Factor Alignment (15%): Are factors working for current regime?
   - Market Fit (10%): Is strategy suited to current conditions?

2. **Diagnosis** - Identifies what's working and what's struggling

3. **Pivot Recommendations** - Suggests strategic changes:
   - **Consolidation Mode**: Fewer, larger positions
   - **Defensive Mode**: Reduced risk, tighter stops
   - **Cash Mode**: Significant exposure reduction
   - **Aggressive Mode**: Lean into momentum (bull markets)
   - **Regime Adaptation**: Adjust for current market regime

### Usage

```python
from strategy_health import get_strategy_health
from strategy_pivot import analyze_pivot, apply_recommended_pivot

# Get strategy health
health = get_strategy_health()
print(f"Grade: {health.grade} ({health.score}/100)")

# Run pivot analysis
pivot = analyze_pivot()
if pivot.should_pivot:
    print(f"Recommended: {pivot.recommended_pivot.name}")
    # Apply the recommended pivot
    apply_recommended_pivot(pivot)
```

### Early Warning System

Detects issues before they cause damage:
- Regime shifts (benchmark near key moving averages)
- Drawdown warnings (approaching thresholds)
- Losing streaks (consecutive stop-loss exits)
- Concentration risk (single position too large)
- Over-diversification (too many small positions)

```python
from early_warning import get_warnings
warnings = get_warnings()
for w in warnings:
    print(f"[{w.severity.value}] {w.title}: {w.description}")
```

### Design Philosophy

Mommy Bot is designed to be **adaptive, not constrained**:
- No hard position limits - the system learns what works
- Strategy health monitoring suggests when to consolidate or expand
- PIVOT analysis recommends changes based on performance, not arbitrary rules
- Early warnings provide proactive risk management
