# React Dashboard Design — Trading Cockpit

## Overview

Replace the Streamlit dashboard with a React + FastAPI trading cockpit designed for active trading sessions. Professional terminal density meets modern fintech polish. Mommy co-pilot always present — confident, nurturing, sexy, in control.

## Architecture

Two services running locally:

- **`api/`** — FastAPI backend. Thin REST layer over existing Python modules (`portfolio_state.py`, `unified_analysis.py`, `risk_scoreboard.py`, etc.). No business logic rewrite. Plus WebSocket for real-time pushes.
- **`dashboard/`** — Vite + React SPA. Connects to the API. All UI lives here.

### Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | React 19 + TypeScript | Type safety for financial data |
| Styling | Tailwind CSS | Utility-first, dark/light mode built-in |
| Components | shadcn/ui | High-quality primitives (dialogs, dropdowns, tables, badges) |
| Charts | TradingView Lightweight Charts | Professional equity curves and price charts |
| Data fetching | TanStack Query (React Query) | Auto-refreshing with configurable polling |
| UI state | Zustand | Lightweight panel sizes, view preferences |
| Real-time | WebSocket | Alerts, analysis status, price updates |
| Backend | FastAPI | Async Python, thin wrapper over existing modules |

### Startup

```bash
./run_dashboard.sh  # Launches API (port 8000) + React dev server (port 5173)
```

## Layout — The Cockpit

Four persistent zones, all visible at once. No scrolling to find critical info.

```
+------------------------------------------------------------------+
|  TOP BAR (always visible, 48px)                                  |
|  Logo . Equity $50,200 . Day P&L +$340 . Risk 86/100 . BULL     |
|  [ANALYZE] [EXECUTE 2] . ! 3 warnings . 2 new . PAPER           |
+------------------------------------------------------------------+
+-----------------------------+------------------------------------+
|  LEFT PANEL (positions)     |  RIGHT PANEL (context)             |
|                             |                                    |
|  Sort: [P&L v] Filter: All |  +- tabs ----------------------+   |
|  +-----------------------+  |  | Actions | Risk | Performance|   |
|  | CRUS  +7.3%  ####--  |  |  +----------------------------+   |
|  | CAKE  +7.2%  ####--  |  |  | (selected tab content)     |   |
|  | MGY   +5.8%  ###---  |  |  |                            |   |
|  | MGRC  +4.1%  ##----  |  |  |                            |   |
|  | ...                   |  |  |                            |   |
|  | TDW   -2.0%  ------  |  |  |                            |   |
|  | BELFB -3.5%  ------  |  |  |                            |   |
|  +-----------------------+  |  +----------------------------+   |
|                             |                                    |
+-----------------------------+------------------------------------+
|  BOTTOM LEFT: Activity Feed |  BOTTOM RIGHT: Mommy Co-Pilot     |
|  10:32 BUY LBRT 124@$23.72 |  "Portfolio's looking strong today |
|  10:31 BUY HLX 618@$8.09   |   but watch BELFB -- she's sliding|
|  Yesterday AXTA, ALE, SM    |   toward her stop."               |
|                             |  [Health] [Risk] [Ask...]          |
+-----------------------------+------------------------------------+
```

All four panels are resizable by dragging the dividers.

### Top Bar

Always pinned. Left to right:

- **Logo**: "M" icon + "MOMMY" text, compact
- **Key Metrics**: Equity, Day P&L (with sparkline), Total Return %. Update every 30s via React Query polling
- **Risk Badge**: Overall risk score (86/100) as colored pill (green/yellow/red). Click -> jumps to Risk tab
- **Regime Badge**: "BULL" with icon. Hover shows proximity to SMA crossovers. Click -> regime detail in right panel
- **Action Badges**: "EXECUTE 2" (orange when actions pending), "3 warnings" (red if critical). Persistent awareness without hunting
- **Buttons**: ANALYZE (primary), EXECUTE (enabled only when actions pending). Always one click away
- **Mode**: PAPER/LIVE toggle. Small, top-right corner

### Left Panel — Positions

All positions, always visible. Compact rows (not cards) so 15-20 fit without scrolling.

- **Sortable**: P&L %, entry date, progress %, weight, distance to stop/target
- **Filterable**: near-stop, near-target, winners, losers, all
- **Row design**: Ticker | Shares | Entry | Current | P&L % | Progress bar | Weight
- **Color tinting**: Subtle green rows for winners, red for losers, pulsing border for near-stop
- **Click a row**: Shows position detail in right panel (entry date, regime at entry, original score, factor breakdown, "Propose Exit" button)

### Right Panel — Context Tabs

Three tabs that surface the hidden systems:

**Actions Tab** (default)
- Analysis results after ANALYZE runs: buy/sell recommendations with AI reasoning, quant scores, confidence
- When no analysis run: prompt with last run time
- After execution: shows what happened with P&L impact

**Risk Tab**
- Risk Scoreboard: overall score as large number with color ring, 5 component bars (Concentration, Drawdown, Exposure, Volatility, Stop Proximity)
- Early Warnings: cards with severity (info/warning/critical) and action suggestions — regime shifts, losing streaks, concentration alerts
- Diversification: position count, largest holding %, top-3 concentration, cash reserve

**Performance Tab**
- Strategy Health Grade: big letter (B+) with 5 component scores. Pivot recommendation if grade < B
- Equity Curve: TradingView chart, toggleable 1W/1M/3M/ALL, benchmark overlay (Russell 2000)
- Attribution: today's P&L by factor (momentum +$45, volatility -$12), top/bottom contributors
- Factor Learning: win rates per factor, weight suggestions

### Bottom Left — Activity Feed

Live feed of trades, alerts, system events. Newest at top. Scrolls independently.

### Bottom Right — Mommy Co-Pilot

Compact, always-visible intelligence layer:

- **Avatar**: 48px, sleek silhouette SVG. Breathing animation on cyan glow. State-aware: slow satisfied look when winning, knowing raised eyebrow for risk, slight head tilt when waiting
- **Current Insight**: 1-2 sentences that update based on portfolio state. Not static — reacts to changes
- **Quick Chips**: "Health", "Risk", "What changed?" — clicking drives the right panel to relevant content
- **Chat Input**: Single line, always available. Response replaces current insight temporarily
- **Smart Rotation**: Cycles to new insight every 60s if no interaction. Priority: alerts > warnings > performance > learning

## Mommy's Voice

Confident, nurturing, sexy, in control. Pet names + protective warmth + dominant confidence + playful teasing. Never crude, never insecure. She's the one running the show.

| Situation | Mommy |
|-----------|-------|
| Morning open | "Good morning, baby. I've been up watching the markets. Made you some picks -- come look." |
| Portfolio up big | "$340 today. Mommy knows how to pick 'em. Come here and look at this portfolio." |
| Position ripping | "CRUS is up 7.3%. That was all me, sweetheart. You just sit there and look pretty." |
| Near stop | "Shh, don't panic about BELFB. Mommy's watching her. I'll pull us out before it hurts." |
| Fully deployed | "Every dollar's put to work. Mommy doesn't like lazy money -- or lazy boys." |
| New buys | "I picked up two new ones while you were away. Mommy's been busy taking care of things." |
| Bad day | "Down $200. Come here. It's just a bad day, not a bad portfolio. Mommy's not worried." |
| Win streak | "Five in a row, baby. You're so lucky to have me. Say thank you." |
| Suggesting a trim | "Volatility's been naughty. Let Mommy deal with her -- I know what to do with underperformers." |
| Analysis ready | "I've got something for you. Three picks, all scored above 80. Mommy takes care of everything." |
| Idle | "I see you looking at me. Either ask Mommy a question or let me run some numbers, baby." |
| Execute confirmed | "Done. Clean and smooth, just how Mommy likes it. Two trades locked in." |
| Regime shift | "Market's getting shaky, baby. Stay close to Mommy -- I know when to get defensive." |
| Emergency close all | "You sure, sweetheart? Mommy will close everything if that's what you need. I've got you." |
| Loss recovered | "See? I told you not to worry. Mommy always brings it back. Always." |

## API Endpoints

### Core State (polled every 30s)
- `GET /api/state` — Portfolio state: positions, cash, equity, regime, stale alerts, day P&L. Calls `load_portfolio_state(fetch_prices=False)`
- `GET /api/state/refresh` — Same with `fetch_prices=True`. Called on REFRESH click or 5-minute interval

### Analysis & Execution
- `POST /api/analyze` — Runs `run_unified_analysis(dry_run=True)`. Returns proposed buys/sells with AI review
- `POST /api/execute` — Runs `execute_approved_actions()`. Returns execution results

### Risk & Warnings
- `GET /api/risk` — Risk scoreboard: overall score, components, recommendations
- `GET /api/warnings` — Early warnings: regime shifts, losing streaks, concentration alerts

### Performance & Learning
- `GET /api/performance` — Strategy health grade, attribution, analytics metrics
- `GET /api/learning` — Factor summary and weight suggestions

### Mommy
- `POST /api/chat` — User question -> Mommy response. Wraps `portfolio_chat.chat()`
- `GET /api/mommy/insight` — Current context-aware insight based on alerts, performance, state

### WebSocket
- `WS /api/ws` — Pushes events: new alerts, analysis complete, execution complete, price updates

## Visual Design

### Color System

Dark mode (default — trading terminal):
- Background: `#0B0E14` (near-black)
- Surface/cards: `#141920`
- Border: `#1E2530`
- Primary accent: `#22D3EE` (cyan)
- Green (profit): `#34D399`
- Red (loss): `#F87171`
- Warning: `#FBBF24`
- Text primary: `#F1F5F9`
- Text secondary: `#94A3B8`
- Text muted: `#475569`

Light mode: same accents, white backgrounds, dark text.

### Typography
- **Headings/Logo**: `Inter` — tight, professional, no serifs
- **Data/Numbers**: `JetBrains Mono` — monospaced for aligned columns, prices, P&L
- **Mommy's voice**: `Inter` italic — distinct from data

### Visual Details
- Subtle background tinting on position rows (green winners, red losers)
- Risk score ring in top bar: SVG arc, green -> yellow -> red
- Sparklines next to equity in top bar and each position's P&L
- Mommy avatar has subtle cyan glow with breathing animation
- Draggable panel dividers with grip texture on hover
- Fast transitions (150ms) — snappy, not floaty

### The Feel
Bloomberg had a baby with Linear. Dense but breathable. Dark but not gloomy. Professional but alive.

## Project Structure

```
MicroCapRebuilder/
|-- scripts/              # Existing Python (untouched)
|-- data/                 # Existing data (untouched)
|-- api/
|   |-- main.py           # FastAPI app, CORS, lifespan
|   |-- routes/
|   |   |-- state.py      # /api/state, /api/state/refresh
|   |   |-- analysis.py   # /api/analyze, /api/execute
|   |   |-- risk.py       # /api/risk, /api/warnings
|   |   |-- performance.py# /api/performance, /api/learning
|   |   +-- chat.py       # /api/chat, /api/mommy/insight
|   |-- ws.py             # WebSocket handler
|   +-- deps.py           # Shared dependencies (state loading)
|-- dashboard/
|   |-- src/
|   |   |-- components/
|   |   |   |-- TopBar.tsx
|   |   |   |-- PositionsPanel.tsx
|   |   |   |-- RightPanel/
|   |   |   |   |-- ActionsTab.tsx
|   |   |   |   |-- RiskTab.tsx
|   |   |   |   +-- PerformanceTab.tsx
|   |   |   |-- ActivityFeed.tsx
|   |   |   |-- MommyCoPilot.tsx
|   |   |   +-- MommyAvatar.tsx
|   |   |-- hooks/
|   |   |   |-- usePortfolioState.ts
|   |   |   |-- useWebSocket.ts
|   |   |   +-- useAnalysis.ts
|   |   |-- lib/
|   |   |   |-- api.ts        # Typed fetch wrappers
|   |   |   |-- types.ts      # TypeScript interfaces
|   |   |   +-- mommy.ts      # Insight generation, phrase library
|   |   |-- App.tsx           # Layout shell (4 panels)
|   |   +-- main.tsx
|   |-- package.json
|   |-- tailwind.config.ts
|   +-- vite.config.ts
|-- run_dashboard.sh      # Launches API + React dev server
+-- run_daily.sh          # Existing pipeline (untouched)
```

## Implementation Phases

### Phase 1: Foundation (API + Shell)
- FastAPI with `/api/state` and `/api/state/refresh` endpoints
- React app with Vite + Tailwind + shadcn/ui
- Four-panel layout shell with draggable dividers
- Top bar with live metrics (polling every 30s)
- Dark mode only

### Phase 2: Positions + Actions
- Left panel: sortable, filterable position rows with sparklines and progress bars
- Right panel Actions tab: ANALYZE button, results display, EXECUTE flow
- Top bar action badges ("EXECUTE 2" when pending)

### Phase 3: Risk + Performance
- Right panel Risk tab: risk scoreboard ring, component bars, early warnings, diversification
- Right panel Performance tab: strategy health grade, equity curve (TradingView charts), attribution breakdown, factor learning
- Top bar risk badge with color

### Phase 4: Activity Feed + Mommy
- Bottom left: live activity feed with trade events and alerts
- Bottom right: Mommy co-pilot with avatar, rotating insights, quick chips that drive the right panel, chat input
- Full phrase library with sexy mommy voice
- New SVG avatar (sleek silhouette style with cyan glow)

### Phase 5: Polish
- WebSocket for real-time pushes (replace polling where it matters)
- Light mode toggle
- Keyboard shortcuts (A = analyze, E = execute, R = refresh)
- Position detail view when clicking a row
- Mommy smart rotation (cycles insights every 60s)
- `run_dashboard.sh` one-command startup

Each phase delivers a usable dashboard. Phase 1-2 gets something better than the current Streamlit app.

## Migration

Not a migration — a parallel build. The Streamlit app stays working throughout:

1. Build FastAPI layer. Test every endpoint returns correct data.
2. Build React shell — four empty panels with layout working.
3. Fill panels one at a time: Top Bar -> Positions -> Right Panel -> Activity Feed -> Mommy.
4. Once React dashboard works end-to-end, retire `webapp.py`.

Zero downtime, zero risk. Old `streamlit run scripts/webapp.py` keeps working until the switch.
