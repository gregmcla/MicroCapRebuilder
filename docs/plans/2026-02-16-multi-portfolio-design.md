# Multi-Portfolio Support Design

**Date:** 2026-02-16
**Status:** Approved

## Overview

Add support for multiple independent portfolios, each with its own config, data files, scoring weights, and risk parameters. A microcap portfolio and a large-cap portfolio are completely separate trading systems that share a UI and codebase.

## Key Decisions

- **Fully independent portfolios** — each has its own config.json, risk parameters, factor weights
- **Separate data directories** — `data/portfolios/{id}/` per portfolio, not a portfolio column in shared files
- **Portfolio-aware backend** — thread `portfolio_id` through API routes and `load_portfolio_state()`
- **Dashboard: overview + switcher** — combined overview as landing page, click into any portfolio for the full single-portfolio experience, top bar switcher to jump between them
- **Guided setup** — pick name, universe, starting capital; system provides smart defaults

## Data Layer

### Portfolio Registry (`data/portfolios.json`)

```json
{
  "portfolios": [
    {
      "id": "microcap",
      "name": "MicroCap Rebuilder",
      "universe": "microcap",
      "created": "2026-02-16",
      "starting_capital": 50000,
      "active": true
    }
  ],
  "default_portfolio": "microcap"
}
```

### Directory Structure

```
data/
├── portfolios.json
├── portfolios/
│   ├── microcap/
│   │   ├── config.json
│   │   ├── positions.csv
│   │   ├── transactions.csv
│   │   ├── daily_snapshots.csv
│   │   ├── watchlist.csv
│   │   ├── post_mortems.csv
│   │   └── tracker.json
│   └── allcap/
│       └── ...same files...
```

### Universe Presets

| Universe | Market Cap Range | Default Stop | Default Risk/Trade | Factor Weight Bias |
|----------|-----------------|--------------|--------------------|--------------------|
| Microcap | <$300M | 8% | 10% | High momentum weight |
| Small Cap | $300M–$2B | 7% | 8% | Balanced |
| Mid Cap | $2B–$10B | 6% | 7% | More mean reversion |
| Large Cap | $10B+ | 5% | 6% | More relative strength |
| Custom | User-defined | User-defined | User-defined | User-defined |

### portfolio_state.py Change

`load_portfolio_state(portfolio_id="microcap", fetch_prices=True)` — resolves data directory from portfolio_id. Defaults to `portfolios.json → default_portfolio`.

## API Changes

### Existing routes become portfolio-scoped

| Current | New |
|---------|-----|
| `GET /api/state` | `GET /api/{portfolio_id}/state` |
| `GET /api/state/refresh` | `GET /api/{portfolio_id}/state/refresh` |
| `POST /api/analyze` | `POST /api/{portfolio_id}/analyze` |
| `POST /api/execute` | `POST /api/{portfolio_id}/execute` |
| `POST /api/sell/{ticker}` | `POST /api/{portfolio_id}/sell/{ticker}` |
| `GET /api/risk` | `GET /api/{portfolio_id}/risk` |
| `GET /api/warnings` | `GET /api/{portfolio_id}/warnings` |
| `GET /api/performance` | `GET /api/{portfolio_id}/performance` |
| `GET /api/learning` | `GET /api/{portfolio_id}/learning` |
| `POST /api/chat` | `POST /api/{portfolio_id}/chat` |
| `GET /api/mommy/insight` | `GET /api/{portfolio_id}/mommy/insight` |
| `POST /api/scan` | `POST /api/{portfolio_id}/scan` |
| `POST /api/close-all` | `POST /api/{portfolio_id}/close-all` |
| `POST /api/mode/toggle` | `POST /api/{portfolio_id}/mode/toggle` |

### New aggregate routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/overview` | GET | Aggregate equity, total P&L, per-portfolio summaries |
| `/api/portfolios` | GET | List all portfolios from registry |
| `/api/portfolios` | POST | Create new portfolio (guided setup) |
| `/api/portfolios/{id}` | DELETE | Soft-delete (set active: false) |

### Overview endpoint

Loads all active portfolios with `fetch_prices=False` (cached prices). Returns: total equity, total cash, total day P&L, and per-portfolio cards (name, equity, return %, position count, risk score, universe).

## Script Changes

Core scripts already consume `PortfolioState` — only `portfolio_state.py` needs to resolve the right data directory.

### run_daily.sh

Loops over all active portfolios:

```bash
for portfolio in $(python3 scripts/list_portfolios.py); do
    python3 scripts/execute_sells.py --portfolio "$portfolio"
    python3 scripts/pick_from_watchlist.py --portfolio "$portfolio"
    python3 scripts/update_positions.py --portfolio "$portfolio"
done
```

Each script gets an optional `--portfolio` CLI arg, defaulting to `default_portfolio` from registry.

## Dashboard Changes

### Top Bar

- Portfolio switcher dropdown (left side, next to logo)
- Shows current portfolio name or "Overview"
- Lists all portfolios + "Overview" option
- "+" button opens guided creation modal

### Overview Page (new, default landing)

- **Aggregate metrics bar:** Total equity, total day P&L, total return %
- **Portfolio cards grid:** One card per portfolio — name, equity, return %, position count, risk score ring, universe badge
- Click a card → enter that portfolio's full view

### Single Portfolio View

Unchanged from current experience. API calls include portfolio_id in URL.

### Guided Portfolio Creation Modal

- Name input
- Universe picker (5 options with descriptions)
- Starting capital input
- Create button → backend creates directory + config with universe presets

### State Management

- New `usePortfolioStore` (Zustand): `activePortfolioId` (string or `"overview"`), `setPortfolio(id)`
- All existing hooks read `activePortfolioId` and include it in API URLs
- Separate `useOverview` hook for aggregate data

## Migration Plan

1. Create `data/portfolios/microcap/` directory
2. Move current flat files into it (positions.csv, transactions.csv, daily_snapshots.csv, watchlist.csv, post_mortems.csv, tracker.json)
3. Move `data/config.json` → `data/portfolios/microcap/config.json`
4. Create `data/portfolios.json` registry with microcap as default
5. Temporary symlink `data/config.json` → `data/portfolios/microcap/config.json` for unmigrated scripts
