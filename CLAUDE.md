# CLAUDE.md - AI Assistant Guide for MicroCapRebuilder

## Project Overview

MicroCapRebuilder is a **daily automated portfolio management and trading system** that picks stocks from a microcap watchlist, tracks positions, and generates performance visualizations. The system implements a 10% risk-per-trade strategy with a starting capital of $5,000.

## Directory Structure

```
MicroCapRebuilder/
├── scripts/                    # Python execution scripts
│   ├── pick_from_watchlist.py  # Daily stock picking logic
│   ├── fix_total_today.py      # Portfolio reconciliation
│   ├── generate_graph.py       # Performance chart generation
│   ├── overlay_stats.py        # Statistics overlay on charts
│   ├── set_roi_baseline.py     # ROI baseline recording
│   └── build_watchlist.py      # Watchlist generator (initialization)
├── data/                       # Data files (gitignored except watchlist)
│   ├── watchlist.jsonl         # Stock watchlist (66 tickers)
│   ├── watchlist.txt           # Backup plain-text watchlist
│   ├── portfolio.csv           # Current holdings
│   ├── portfolio_update.csv    # Daily portfolio snapshots
│   ├── trade_log.csv           # Historical trade records
│   └── roi_baseline.json       # ROI calculation baseline
├── charts/                     # Generated charts (gitignored)
├── run_daily.sh                # Main orchestration script
├── requirements.txt            # Python dependencies
└── .gitignore                  # Version control rules
```

## Key Configuration Values

| Parameter | Value | Location |
|-----------|-------|----------|
| Risk Per Trade | 10% of available cash | `scripts/pick_from_watchlist.py:16` |
| Starting Capital | $5,000.00 | `scripts/fix_total_today.py:10` |
| Chart Window | 30 days | `run_daily.sh:13` |
| Benchmark | ^RUT (Russell 2000) | `run_daily.sh:13` |
| Fallback Benchmark | IWM | `run_daily.sh:13` |

## Scripts Reference

### `pick_from_watchlist.py` - Daily Stock Picker
**Purpose:** Main trading logic that selects stocks and records trades.

**Workflow:**
1. Loads watchlist from `data/watchlist.jsonl`
2. Fetches current prices via yfinance
3. Calculates shares to buy based on 10% of available cash
4. Updates `trade_log.csv` with new trades
5. Updates `portfolio_update.csv` with new positions and TOTAL row

**Key Functions:**
- `read_cash_and_positions()` - Reads current cash and positions from portfolio_update.csv

### `fix_total_today.py` - Portfolio Reconciliation
**Purpose:** Reconciles daily portfolio totals from `portfolio.csv`.

**Workflow:**
1. Reads `portfolio.csv` with current holdings
2. Validates required columns: Ticker, Shares, Price, Cost
3. Computes total position value and cash remaining
4. Appends TOTAL row to `portfolio_update.csv`

### `generate_graph.py` - Performance Chart
**Purpose:** Generates equity performance chart with benchmark comparison.

**CLI Arguments:**
- `--days` (required): Number of days to show
- `--bench` (required): Primary benchmark symbol
- `--fallback` (required): Fallback benchmark if primary fails

**Output:** `charts/performance.png`

### `overlay_stats.py` - Statistics Overlay
**Purpose:** Overlays trading statistics on the performance chart.

**CLI Arguments:**
- `--csv`: Path to portfolio_update.csv
- `--trades`: Path to trade_log.csv
- `--baseline`: Path to roi_baseline.json
- `--img`: Path to chart image

**Stats Displayed:** Equity, buy count, sell count, ROI%

### `set_roi_baseline.py` - Baseline Recording
**Purpose:** Records a baseline equity value for ROI calculations.

**Usage:** `./scripts/set_roi_baseline.py YYYY-MM-DD`

**Output:** JSON to stdout (redirect to `data/roi_baseline.json`)

### `build_watchlist.py` - Watchlist Generator
**Purpose:** Generates initial watchlist.jsonl (currently hardcoded tickers).

## Data File Schemas

### `watchlist.jsonl`
JSONL format, one JSON object per line:
```json
{"ticker": "CRDO"}
{"ticker": "MOD"}
```

### `portfolio.csv`
Required columns: Ticker, Shares, Price, Cost
```csv
Ticker,Shares,Price,Cost
AAPL,6,219.32,1315.95
```

### `portfolio_update.csv`
Daily snapshots with TOTAL row:
```csv
Date,Ticker,Shares,Price,Cost,Value,Cash,Equity
2025-08-07,TOTAL,,,,3729.42,1270.58,5000.0
```

### `trade_log.csv`
Trade records:
```csv
Ticker,Shares Bought,Buy Price
CRDO,1,117.96
```

### `roi_baseline.json`
```json
{"date": "2025-08-07", "baseline_equity": 5000.0}
```

## Development Workflow

### Daily Execution
Run the orchestration script:
```bash
./run_daily.sh
```

This executes in order:
1. `pick_from_watchlist.py` - Pick stocks and record trades
2. `fix_total_today.py` - Reconcile portfolio totals
3. `generate_graph.py` - Create performance chart
4. `overlay_stats.py` - Add statistics to chart

### Setting Up Environment
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Setting a New ROI Baseline
```bash
./scripts/set_roi_baseline.py 2025-08-07 > data/roi_baseline.json
```

## Code Conventions

### Style
- Python 3 shebang: `#!/usr/bin/env python3`
- Imports organized at top of file
- Section comments use Unicode box-drawing characters: `# ─── Section Name ───`
- Verbose variable names preferred
- Print statements with emoji indicators: `✅` for success, `⚠️` for warnings

### Path Handling
- Use `pathlib.Path` for all file paths
- Navigate from script location: `Path(__file__).parent.parent / "data" / "file.csv"`
- Relative paths assume scripts run from project root

### Data Handling
- Use pandas for CSV operations
- Handle column name variations (e.g., "Cash Balance" vs "Cash")
- Always check for file existence before reading
- Validate required columns before processing

### Error Handling
- Use `sys.exit()` for fatal errors with descriptive messages
- Print warnings with `[warn]` prefix or `⚠️` emoji
- Handle missing data gracefully (e.g., skip tickers with no price data)

## Important Notes for AI Assistants

### When Modifying Scripts
1. **Preserve hardcoded parameters** - Risk per trade (10%), starting capital ($5,000) are intentional
2. **Maintain column flexibility** - Scripts handle multiple column name variations
3. **Keep relative paths** - Scripts expect to run from project root or use `__file__` navigation
4. **Test with sample data** - CSV files in `data/` contain real examples

### When Adding Features
1. Follow the single-responsibility pattern (one script = one task)
2. Add CLI arguments via argparse for configurability
3. Output to appropriate directory (data/ for CSVs, charts/ for images)
4. Use pandas for data manipulation, yfinance for market data
5. Add appropriate emoji feedback (✅ success, ⚠️ warning)

### Files That Are Gitignored
- `data/*.csv` and `data/*.json` (except watchlist files)
- `charts/` directory
- `.venv/` and `__pycache__/`
- `backup/` directory

### Common Tasks
- **Add a ticker to watchlist:** Edit `data/watchlist.jsonl`, add `{"ticker": "SYMBOL"}`
- **Reset portfolio:** Delete/recreate `portfolio_update.csv` with proper headers
- **Change benchmark:** Modify `--bench` argument in `run_daily.sh`
- **Adjust risk:** Change `RISK_PER_TRADE` in `pick_from_watchlist.py`

## Dependencies

```
yfinance       # Stock price data from Yahoo Finance
pandas         # Data manipulation and CSV handling
matplotlib     # Chart generation and image manipulation
openai         # Available but not actively used
python-dotenv  # Environment variable management
```

## Testing

No formal test suite exists. Manual testing workflow:
1. Run `./run_daily.sh` and verify no errors
2. Check `data/trade_log.csv` for new trades
3. Check `data/portfolio_update.csv` for updated TOTAL row
4. Verify `charts/performance.png` is generated with stats overlay
