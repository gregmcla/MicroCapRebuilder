# Strategy-Focused Portfolio Creation

**Date:** 2026-02-24

## Problem

Portfolio creation only lets you pick cap size and starting capital. No way to express sector focus (AI, Industrials, Healthcare) or trading style (aggressive momentum vs conservative value). Every portfolio of the same cap size gets identical config.

## Solution

Two creation paths, both producing the same config output:

1. **Strategy Wizard** — step-by-step configurator: cap size, sector focus, trading style, review
2. **AI Strategy** — describe what you want in plain text, Mommy generates the config, you review/edit before creating

## Creation Flow

### Path A: Strategy Wizard

1. **Name + Capital** — portfolio name, starting capital
2. **Cap Size** — microcap / smallcap / midcap / largecap (sets base config: market cap filters, benchmark, base ETFs)
3. **Sector Focus** — checkbox grid of 11 GICS sectors. "All" selected by default. Picking specific sectors restricts universe + discovery to those sectors only.
4. **Trading Style** — pick one: Aggressive Momentum / Balanced / Conservative Value / Mean Reversion. Maps to scoring weights + risk params.
5. **Review + Create** — summary card showing full config, create button.

### Path B: AI Strategy

1. **Name + Capital** — same as wizard
2. **Text prompt** — describe desired strategy (e.g., "Aggressive AI and semiconductor play with tight stops")
3. **Mommy generates config** — AI returns structured JSON with sectors, style, risk params, rationale
4. **Review + Edit** — same summary card as wizard step 5, fully editable before creating

Both paths call the same `create_portfolio()` with the assembled config.

## Sector Focus System

11 GICS sectors, each mapped to sector ETFs used as **data sources** for discovering individual stocks (we never buy ETFs):

| Sector | ETF Source | Example Themes |
|--------|-----------|----------------|
| Technology | XLK | AI, semiconductors, software |
| Communication | XLC | social media, streaming, telecom |
| Healthcare | XLV | biotech, pharma, medical devices |
| Financials | XLF | banks, insurance, fintech |
| Consumer Discretionary | XLY | retail, auto, luxury |
| Consumer Staples | XLP | food, beverage, household |
| Industrials | XLI | aerospace, machinery, logistics |
| Energy | XLE | oil, gas, renewables |
| Materials | XLB | mining, chemicals, steel |
| Utilities | XLU | electric, water, gas utilities |
| Real Estate | XLRE | REITs, property |

When sectors are selected:
- ETF sources are replaced with sector-specific ETFs + cap-size base ETF for breadth
- `config.discovery.sector_filter` restricts discovery to whitelisted sectors
- "All" means no filter (current behavior)

Filtering enforced at:
- `universe_provider.py` — filters ETF holdings by sector
- `stock_discovery.py` — `_passes_filters()` checks sector membership

## Trading Style Presets

| Parameter | Aggressive Momentum | Balanced | Conservative Value | Mean Reversion |
|-----------|-------------------|----------|-------------------|----------------|
| Momentum weight | 0.35 | 0.20 | 0.10 | 0.10 |
| Relative Strength | 0.25 | 0.20 | 0.15 | 0.10 |
| Volatility | 0.05 | 0.15 | 0.25 | 0.15 |
| Mean Reversion | 0.05 | 0.15 | 0.20 | 0.35 |
| Volume | 0.15 | 0.15 | 0.10 | 0.15 |
| RSI | 0.15 | 0.15 | 0.20 | 0.15 |
| Stop loss | 5% | 7% | 8% | 6% |
| Risk per trade | 5% | 3% | 2% | 3% |
| Max position | 10% | 8% | 6% | 8% |
| Trailing stop trigger | 8% | 12% | 15% | 10% |
| Discovery scans | momentum + volume | all four | oversold + sector leaders | oversold + mean rev |

Merged on top of cap-size base config.

## AI Strategy Generation

1. User types prompt describing desired strategy
2. System sends to Mommy with structured system prompt requesting JSON output:
   - `sectors`: list of GICS sectors
   - `trading_style`: preset name OR custom weights
   - `risk_profile`: stop loss %, risk per trade %, max position %
   - `discovery_scans`: which scan types to enable
   - `etf_sources`: additional sector ETFs
   - `rationale`: explanation of choices
3. Response parsed and mapped to same config structure as wizard
4. Review card shown — user can edit before confirming
5. Uses existing chat endpoint infrastructure with specialized system prompt

## Data Model

### New config fields

```json
{
  "strategy": {
    "name": "Aggressive Momentum",
    "sectors": ["Technology", "Communication"],
    "trading_style": "aggressive_momentum",
    "created_via": "wizard",
    "ai_prompt": null,
    "ai_rationale": null
  },
  "discovery": {
    "sector_filter": ["Technology", "Communication"],
    "scan_thresholds": { ... }
  }
}
```

`strategy` block is metadata for display/reference. Actual behavior comes from the fields it populates.

### Registry changes (`portfolio_registry.py`)

- `TRADING_STYLES` dict — four preset style configs
- `SECTOR_ETF_MAP` dict — sector name to ETF ticker mapping
- `create_portfolio()` accepts: `sectors`, `trading_style`, `ai_config`

### API changes

- `POST /api/portfolios` — request body adds `sectors: string[]`, `trading_style: string`, `ai_config: object`
- `POST /api/portfolios/generate-strategy` (new) — takes text prompt + cap size + capital, returns proposed config JSON. Does NOT create portfolio.

### Filtering enforcement

- `universe_provider.py` — reads `config.discovery.sector_filter`, filters holdings by sector
- `stock_discovery.py` — `_passes_filters()` checks sector membership

### Dashboard changes

- `CreatePortfolioModal.tsx` — redesigned with wizard/AI toggle, multi-step flow
- `StrategyReviewCard.tsx` (new) — shared summary card for both paths
