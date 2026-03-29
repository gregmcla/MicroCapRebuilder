# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**Operational — cron automation running daily. 16 active portfolios as of 2026-03-29.**

---

## Recently Completed (2026-03-29) — Dashboard UI + New Portfolios

### Dashboard Bug Fixes
- **React hooks violation (OverviewPage)** — `const sorted = useMemo(...)` was declared AFTER `if (isLoading) return`. Caused "Rendered more hooks than during the previous render" crash on every load. Fixed by moving `sorted` above the loading guard.
- **ConstellationMap hover flash** — `portIds` new array every render → `rebuildLayout` invalidated → `canvas.width` cleared canvas. Fixed with `useMemo` on `portIds`.
- **"Overview" ghost tooltip** — Native browser `title="Overview"` on logo button appearing mid-screen. Removed.
- **Matrix cell toggle-close** — Clicking a selected cell again now closes the bottom panel.

### Dashboard UI Improvements
- **GScottLogo** — "Terminal" font 38→62px. Viewbox widened.
- **PositionPulse wired in** — 36px kinetic strip renders in MatrixGrid. Glyphs show `perf%` not `day%` (zeros when market closed).
- **Large treemap cells** (≥150×110px) — show current price, value, shares@avgcost, full-width sparkline, held + SL distance.

### ETF Holdings — New ETFs Added to DEFAULT_ETFS
`VTI`, `IWC`, `PAVE`, `GRID`, `IFRA`, `IGF`, `SOXX`, `SMH`, `XME`, `ITA`, `RSPT`

**Root cause of empty universes on new portfolios**: ETFs specified in portfolio config but absent from DEFAULT_ETFS were silently ignored, leaving 28-ticker universes.

### New Portfolios
| ID | Capital | Strategy |
|----|---------|----------|
| `tariff-moat-industrials` | $100K | Domestic manufacturers with tariff moat |
| `pre-earnings-momentum` | $1M | Pre-earnings momentum, all caps |
| `ai-pickaxe-infrastructure` | $2M | AI infrastructure picks & shovels |

All three: `extended scan_frequency: daily`, `min_score_threshold: {BULL:35, SIDEWAYS:40, BEAR:50}`, `volume_anomalies: true`.

### Capital Adjustment
- `asymmetric-microcap-compounder` — $1,000 → $10,000 (positions were < $250 minimum, getting skipped at execute)

---

## Recently Completed (2026-03-27) — AI-Generated Sell Reasoning + Discovery/Exit Upgrade

- Layer 1 mechanical sells get AI-generated reasoning (not static labels)
- Fixed O(n×m) RSI bug in discovery scanner
- Fixed 52wk high using 3mo data instead of 1y
- Enabled `scan_volume_anomalies` by default
- New `scan_relative_volume_surge` (4x+ volume vs 30d baseline)
- Ported stagnation + liquidity drop exits to active pipeline
- New momentum fade exit (3 closes below 5d SMA)
- Regime weights removed from scoring — flat default_weights + flat threshold

---

## Previously Completed (2026-03-26)

- Cron automation (scan 6:30AM / execute 9:35AM / update 12PM+4:15PM / watchdog)
- Reentry Guard (`scripts/reentry_guard.py`)
- System Logs Page (`/logs` route)
- VCX same-run reentry veto + min_stop_loss_pct floor
- yf.download() 60s timeout
- Public.com cross-validation (>15% divergence → use yfinance)
- ETF holdings global cache (`data/etf_holdings_cache.json`)
- 5 new prompt context blocks sent to Claude at execute time

---

## Open Bugs / Known Issues

- `ALE`, `JBT` delisted — fail price fetch consistently (ignore)
- Stocktwits 403s broadly — social heat won't populate (DISABLE_SOCIAL workaround)
- No tests for `_validate_allocation()` / `_parse_json()` in `ai_allocator.py`
- `tariff-moat-industrials` finding few candidates — tariff selloff killed momentum signals. Will populate when tape turns.
- `ai-pickaxe-infrastructure` — semis/AI infra crushed in selloff. Same situation.
- `pre-earnings-momentum` — no actual earnings-date awareness in scanner; relies on momentum building pre-earnings. Q1 earnings season starts mid-April.

---

## Active Portfolios (16)

| ID | Notes |
|----|-------|
| `microcap` | Small-cap momentum, ^RUT benchmark |
| `adjacent-supporters-of-ai` | AI infra, allcap, AI-driven |
| `boomers` | General momentum allcap |
| `max` | AI-driven allcap, rotating_3day |
| `defense-tech` | Defense tech, AI-driven |
| `cash-cow-compounders` | Cash-printing businesses |
| `asymmetric-catalyst-hunters` | <$300M mktcap violent re-ratings |
| `catalyst-momentum-scalper` | Intraday momentum on catalysts |
| `momentum-scalper` | Technical breakout scalper |
| `asymmetric-microcap-compounder` | $10K capital, max 2 positions |
| `vcx-ai-concentration` | min_stop_loss_pct=-0.35 |
| `microcap-momentum-compounder` | Focused microcap momentum |
| `yolo-degen-momentum` | 2 positions @ 50% each |
| `tariff-moat-industrials` | $100K, daily scan |
| `pre-earnings-momentum` | $1M, daily scan, allcap |
| `ai-pickaxe-infrastructure` | $2M, daily scan, allcap |

---

## Architecture Decisions

- **DISABLE_SOCIAL=true** — always set
- **Scan timing**: 6:30 AM ET
- **ETF holdings cache** global: `data/etf_holdings_cache.json`
- **Regime weights removed** — flat defaults only
- **yf.download() 60s timeout** — thread-based in `yf_session.py`
- **New portfolios** must use `extended scan_frequency: daily` (rotating_3day causes near-empty universes until 3 scans run)
- **ETF DEFAULT_ETFS** — any ETF in portfolio config must also be in DEFAULT_ETFS or holdings silently ignored
- Dashboard API on port 8001

---

## Key Constraints

- Python 3 only
- Paper mode — no real broker
- Never pass `session=` to yfinance
- `react-resizable-panels` v4: `Group`, `Panel`, `Separator`
- Build check: `npx tsc --noEmit 2>&1 | grep -v 'CreatePortfolioModal\|OverviewPage\|PortfolioSettingsModal\|TopBar'`

---

## Pending Features (backlog)

1. Post-trade review — user requested, not yet designed
2. Earnings date awareness — pre-earnings-momentum has no explicit earnings-date filter in scanner
