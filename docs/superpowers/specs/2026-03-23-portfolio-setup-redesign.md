# Portfolio Setup Redesign — AI-Driven Only

## Context

All new portfolios are AI-driven. The current `CreatePortfolioModal` (954 lines) has three modes: Wizard (6 steps), AI Strategy (4 steps), and AI-Driven (4 steps). Two of those modes are dead weight. The AI-Driven path works but has friction and ships with bad scan defaults (extended_max=6000, daily frequency, exchange_listings enabled) that cause scan timeouts.

## Goal

Replace the multi-mode creation flow with a streamlined 2-step AI-driven-only modal. Fix scan defaults. Delete dead code paths.

## Design

### New Creation Flow

**Step 1 — "Define Your Strategy"**
- Starting capital input (default $1,000,000)
- Strategy DNA textarea (7 rows, placeholder: "Describe your investment thesis...")
- "Next" button calls `POST /api/portfolios/suggest-config`
- Loading state: button disabled with "Generating..." text + spinner while Claude call runs
- Error state: red error message below textarea if call fails; user can retry without navigating

**Step 2 — "Review & Create"**
- Compact card showing Claude's suggestions:
  - Name (e.g. "Defense Tech Autonomous Systems")
  - ID slug (auto-generated from name via `slugify()`)
  - Universe (e.g. "midcap")
  - ETFs (e.g. ITA, FITE, ROBO)
  - Risk posture summary (e.g. "7% stop loss, 8% max position")
- "Back" button returns to Step 1 to revise DNA
- "Create" button calls `POST /api/portfolios`

### Data Flow: suggest-config → create

The frontend packs Claude's suggestions into the existing `CreatePortfolioRequest`:

```
POST /api/portfolios {
  id: slugify(suggestResponse.name),     // auto-generated from Claude's name
  name: suggestResponse.name,
  universe: suggestResponse.universe,
  starting_capital: <user-entered>,
  ai_driven: true,
  strategy_dna: <user-entered DNA>,
  ai_config: {
    stop_loss_pct: suggestResponse.stop_loss_pct,
    risk_per_trade_pct: suggestResponse.risk_per_trade_pct,
    max_position_pct: suggestResponse.max_position_pct,
    etf_sources: suggestResponse.etfs
  }
}
```

This uses the existing `ai_config` parameter, which `create_portfolio()` already applies as Layer 4 overrides. The `etf_sources` key is already handled (appended to `etf_holdings.etfs` in `portfolio_registry.py` lines 515-519). No changes to `create_portfolio()` signature needed.

The slug is generated client-side from Claude's suggested name. If the slug collides with an existing portfolio ID, the `POST /api/portfolios` endpoint returns a 400 and the frontend shows the error — user can go back to Step 1 to revise the DNA (which will generate a different name).

### New Backend Endpoint

**`POST /api/portfolios/suggest-config`**

Request:
```json
{
  "strategy_dna": "string",
  "starting_capital": 1000000
}
```

Response:
```json
{
  "name": "Defense Tech Autonomous Systems",
  "universe": "midcap",
  "etfs": ["ITA", "FITE", "ROBO", "CIBR"],
  "stop_loss_pct": 7.0,
  "risk_per_trade_pct": 8.0,
  "max_position_pct": 12.0
}
```

Implementation:
- Single Claude call using **Opus 4.6** model (`claude-opus-4-6`)
- Timeout: **60 seconds** on Anthropic client
- `max_tokens`: **1024** (structured JSON response doesn't need more)
- Prompt instructs Claude to infer portfolio name, universe (must be one of: microcap, smallcap, midcap, largecap, allcap), relevant ETFs (4-6 real tickers), and risk parameters from the DNA text
- `suggest_config_for_dna()` validates the returned universe against `UNIVERSE_PRESETS` keys; falls back to "allcap" if Claude returns an unexpected value
- JSON parsing uses existing `_clean_json_response()` utility (kept from current `strategy_generator.py`)
- Lives in `strategy_generator.py` as `suggest_config_for_dna(strategy_dna, starting_capital)`
- Called from a new route in `api/routes/portfolios.py`

### Hardened Creation Defaults

**Intentional change from previous behavior.** Previously AI-driven portfolios were created with `extended_max=6000`. This caused repeated scan timeouts (12-minute limit). All AI-driven portfolios created going forward will use reduced defaults:

- `extended_max: 3000` (was 6000 — intentional reduction)
- `scan_frequency: "rotating_3day"` (never `daily` on extended)
- `exchange_listings: false` (ETFs are the universe for thesis portfolios)
- `total_watchlist_slots: 500` (already exists)

Existing portfolios are not retroactively modified — these defaults only apply to new creations.

These defaults are applied in `portfolio_registry.py` within the AI-driven code path.

### Code Deletion

**Frontend — deleted files:**
- `dashboard/src/components/StrategyReviewCard.tsx` (entire file)

**Frontend — deleted from `CreatePortfolioModal.tsx`:**
- Wizard mode (6-step form, sector multi-select, weight sliders, trading style cards)
- AI Strategy mode (prompt, generate-strategy call, review)
- Mode switcher toggle (Wizard | AI Strategy | AI-Driven)
- Style/scan constants (`STYLE_WEIGHTS`, `STYLE_RISK`, `STYLE_SCANS`)

**Frontend — deleted from types/api:**
- `GenerateStrategyRequest` interface
- `GeneratedStrategy` interface
- `generateStrategy` API call

**Backend — deleted endpoints:**
- `POST /api/portfolios/generate-strategy`
- `GET /api/portfolios/trading-styles`
- `GET /api/portfolios/sectors`

**Backend — deleted from `strategy_generator.py`:**
- `generate_strategy()` function
- `suggest_etfs_for_dna()` function (replaced by `suggest_config_for_dna()`)
- `GeneratedStrategy` dataclass
- `STRATEGY_SYSTEM_PROMPT`
- Validation/normalization functions that only served `generate_strategy()`: `_validate_weights()`, `_normalize_sector_weights()`

**Backend — kept from `strategy_generator.py`:**
- `_clean_json_response()` (needed by new `suggest_config_for_dna()`)
- `get_api_key()` (needed by new function)

**Backend — kept but no longer called by new code paths:**
- `TRADING_STYLES` dict in `portfolio_registry.py` (existing portfolios may reference these styles in their config)
- `SECTOR_ETF_MAP` (used by existing portfolios)
- All universe presets (Claude picks from them; `create_portfolio()` still applies them)

### Unchanged

- AI-driven pipeline (`ai_allocator.py`, `ai_review.py`)
- Scan/discovery system (gets better defaults, no code changes)
- Dashboard layout (positions grid, actions tab, activity, performance, overview)
- `PortfolioSettingsModal.tsx` (minimal DNA textarea, gear icon)
- TopBar (gear icon behavior)
- Overview page ("+ New Portfolio" button opens the simplified modal)
- `create_portfolio()` function signature and config layering logic

## Files Modified

| File | Change |
|------|--------|
| `dashboard/src/components/CreatePortfolioModal.tsx` | Rewrite: ~954 lines → ~250 lines |
| `dashboard/src/components/StrategyReviewCard.tsx` | Delete entire file |
| `dashboard/src/lib/api.ts` | Remove `generateStrategy`, add `suggestConfig` |
| `dashboard/src/lib/types.ts` | Remove `GenerateStrategyRequest`, `GeneratedStrategy`; add `SuggestConfigResponse` |
| `scripts/strategy_generator.py` | Replace contents with `suggest_config_for_dna()`, keep `_clean_json_response()` and `get_api_key()` |
| `scripts/portfolio_registry.py` | Harden AI-driven defaults in `create_portfolio()` |
| `api/routes/portfolios.py` | Remove 3 endpoints, add `suggest-config` endpoint |
| `CLAUDE.md` | Update API endpoint table: remove 3 deleted endpoints, add `suggest-config` |
