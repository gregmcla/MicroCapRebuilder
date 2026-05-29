# Daily Digest Home — Design Spec

**Date:** 2026-05-29
**Status:** Design approved (visual), pending spec review
**Visual source of truth:** `.superpowers/brainstorm/22132-1780085549/content/digest-design-v6.html` (the "v6 cinematic cut")

---

## 1. Summary

Replace the current Overview landing screen with a **Daily Digest** — an *observational* home that answers, in one scroll, "how is my whole operation doing, what changed, and what's working?" It is **not** a to-do list, alert center, or approval queue. No actions are taken from this screen; it is for understanding state.

The Digest becomes the default view when the dashboard opens (`portfolioId === "overview"`). The existing 35-card **Grid** is preserved as a one-click secondary view. The **Map (ConstellationMap)** and **Chart (multi-portfolio PerformanceChart)** views are **retired from the landing** (code retained but unlinked — see §8).

Scope is the **6 active portfolios** (`active: true` in `data/portfolios.json`), not all 37 registered. Docs claiming 16/35 are stale.

## 2. Goals & non-goals

**Goals**
- One screen that layers **forest → trees**: whole-book rollup on top, per-portfolio comparison below.
- Three observational lenses: **status** (how things are now), **what changed** (since yesterday's close), **performance story** (is it working, vs SPY).
- A distinctive, premium feel native to GScott's existing design system (DM Sans / JetBrains Mono, violet accent, dark) — not a generic admin dashboard.
- A standout **narrative panel ("GScott's Read")** that explains the book in plain English — the centerpiece.

**Non-goals**
- No trade approval, execution, sell/buy, or alert-acknowledgement from this screen.
- No per-position drill-down beyond click-through navigation to an existing portfolio view.
- No mobile-specific layout in this spec (desktop-first; mobile is a separate future effort).

## 3. Layout (four stacked regions)

Top to bottom, full-width card with the existing app chrome (TopBar) above it:

1. **Book Hero** — whole operation as one.
2. **GScott's Read** — full-width narrative centerpiece.
3. **Portfolio Comparison** — ranked, scannable table of the 6 active portfolios.
4. **Since Yesterday's Close** — horizontal timeline strip footer.

### Region 1 — Book Hero
- Left block: label "Total Book · 6 active", hero equity number (gradient-filled, JetBrains Mono), today's $ + % change, and three stat chips: **Health** (green/red portfolio count), **vs SPY · all-time**, **vs SPY · today**.
- Right block: a combined **book equity curve** with a dashed **SPY benchmark** line underneath, a You/SPY legend (top-left), a range segmented control (1W/1M/3M/YTD/ALL, default 3M, top-right), and a floating **+$ delta bubble** at the line's endpoint. Subtle glow-pulse on the line + endpoint. A faint violet "aurora" gradient drifts behind the whole region.

### Region 2 — GScott's Read (full width)
- Header: glowing avatar ("G"), name "GScott", subtitle "Daily intelligence · the whole book, in plain English", and a pulsing **"Live read · {time}"** indicator (right).
- Body is a two-zone grid so prose stays readable (~62ch max), not edge-to-edge:
  - **Main column**: a bold **thesis line** (one-sentence take, with a violet highlight swipe on the key phrase), a body paragraph synthesizing what's carrying the book, and a **red watch-callout box** isolating the single strategy worth questioning.
  - **Right rail**: a **posture gauge** (red→amber→green track, glowing thumb, label e.g. "Risk-on · leaning momentum") and **Working / Watching** tags, each with its own mini-sparkline.

### Region 3 — Portfolio Comparison
- Sort segmented control: **Working** (default), Today, Equity, vs SPY, Name. "Grid view" toggle (right) switches to the preserved 35-card grid.
- Columns: `#` (rank), Portfolio (name + strategy), Equity, Today, Total, **vs Bench** (each portfolio's configured benchmark, named per row; rendered as a diverging bar around the benchmark midpoint), 30d sparkline (glowing endpoint), Trend pill (ahead / flat / fading).
- Rank #1 row gets a violet→cyan accent rail + gradient wash ("leader").

### Region 4 — Since Yesterday's Close
- Label, then a horizontal 4-node **timeline strip** connected by a line: buys executed · exits · biggest swings · regime/risk shift. Each node = colored dot + bold label + timestamp + one detail line. Read-only; click-through to detail.

## 4. Design system (use existing tokens — do not invent)

From `dashboard/src/index.css`:
- **Fonts:** `--font-sans: DM Sans`, `--font-mono: JetBrains Mono`. Mono for all numbers/tickers with `tabular-nums`.
- **Accent:** violet `#7c5cfc` / bright `#917aff`; secondary cyan `#5ce0d6`. **Interactive + highlight color is violet.**
- **Semantics:** green `#34d399` and red `#f87171` reserved **only** for P&L/up-down; amber `#fbbf24` for caution. Do not use green as a general accent.
- **Surfaces:** void `#0a0a0b`, surface-0/1/2/3. **Text:** opacity ramp (`--text-0..4`). **Radius:** 8/6/4 (`--radius*`). **Ease:** `cubic-bezier(.16,1,.3,1)`.
- Motion (aurora drift, line glow-pulse, live dot) must be gated behind `prefers-reduced-motion` (see §7).

## 5. Backend / data flow

### 5.1 New aggregation endpoint — `GET /api/digest`
Returns everything the four regions need for the active portfolios, NaN-sanitized through the existing `_f()` helper pattern in `portfolios.py`. Shape:
```
{
  "book": {
    "equity": float, "day_pnl": float, "day_pnl_pct": float,
    "health": {"green": int, "red": int},
    "vs_spy_alltime_pct": float, "vs_spy_today_pct": float,
    "curve": {                      // for the range-toggled chart
      "range": "3M",
      "book":  [float, ...],        // combined equity (indexed/normalized)
      "spy":   [float, ...]         // SPY over same dates
    }
  },
  "portfolios": [                   // active only, sorted by current sort key server-side or client-side
    {"id","name","strategy","equity","day_pct","total_pct",
     "vs_bench_pct": float, "bench_symbol": str,   // each portfolio's configured benchmark
     "sparkline":[float],"trend":"ahead|flat|fading"}
  ],
  "recap": {                        // "since yesterday's close"
    "buys":  {"count": int, "detail": str, "ts": str},
    "exits": {"count": int, "detail": str, "ts": str},
    "swings": [{"ticker","pct"}],
    "regime": {"label": str, "risk": int, "risk_prev": int, "ts": str}
  }
}
```
- **Aggregation source:** reuse the overview computation in `api/routes/portfolios.py` (equity, day_pnl, total_return_pct, sparkline) but restrict to `active: true` and respect `exclude_from_aggregates`.
- **Combined book curve:** sum per-portfolio `daily_snapshots.total_equity` aligned by date (active, non-excluded). Normalize to % for comparability.
- **SPY line:** fetch SPY closes for the range via `yf_session.cached_download` and index to the same start. (Decision in §9: book-level benchmark is **SPY**, regardless of each portfolio's configured benchmark.)
- **Recap (since yesterday's close):** read each active portfolio's `transactions.csv`, filter `date >= prior trading session close`; classify BUY vs SELL; pull biggest movers from current day_change; read regime + risk from existing regime/risk scoreboard (book-level or representative). Reuse logic already in `api/routes/system.py:_get_trades_for_date` where possible.
- **`trend` derivation:** compare 30d sparkline slope and recent vs-SPY → ahead / flat / fading (deterministic helper).
- **Trade-offs:** one endpoint keeps the screen to a single round-trip (simpler caching, no waterfall). Internally it composes existing functions; no new business logic in the route layer (per project convention).

### 5.2 Structured narrative — extend `GET /api/system/narrative` (or new `GET /api/digest/narrative`)
The current endpoint returns free **text** + 10-min in-memory cache. The Read needs **structured** output:
```
{
  "thesis": str,                 // one-sentence headline take
  "body": str,                   // 2-4 sentence synthesis
  "callout": str,                // the one thing to question (the watch item)
  "posture": float,              // 0..1 → gauge thumb position (0=defensive,1=aggressive)
  "posture_label": str,          // e.g. "Risk-on · leaning momentum"
  "working": [str],              // portfolio ids/names carrying the book
  "watching": [str],             // portfolio id(s) to question
  "updated_at": str
}
```
- Add a **book-level** prompt variant that feeds Claude the §5.1 aggregate (book stats + per-portfolio vs-SPY + recap) and requests JSON. Reuse the existing Claude call pattern, model from `CLAUDE_MODEL`, 180s timeout, and the JSON-cleaning helper used elsewhere (strip markdown, find boundaries, trailing commas).
- Keep the existing free-text `/narrative` behavior intact for the Logs page; add the structured variant under a distinct path or a `?format=digest` flag so existing callers are unaffected.
- Cache: 10-min in-memory keyed by date (same pattern). `posture` may be computed deterministically (regime + net deployed + momentum tilt) and passed into the prompt for consistency rather than asked of the model — TBD in implementation, but the field is server-authoritative.
- **Failure mode:** if the model call fails, return a deterministic fallback (thesis from the numbers, no callout) so the panel never blanks. Never throw to the client.

## 6. Frontend

- **New default route:** in `App.tsx`, when `isOverview` (portfolioId === "overview"), render `<DailyDigest/>` instead of `<OverviewPage/>`.
- **New components** (`dashboard/src/components/Digest/`):
  - `DailyDigest.tsx` — orchestrator + data fetch.
  - `BookHero.tsx` — region 1 (equity, chips, curve+SPY, range toggle).
  - `GScottRead.tsx` — region 2 (thesis, prose, callout, posture gauge, working/watching).
  - `PortfolioCompare.tsx` — region 3 table (rank, diverging vs-SPY bar, sparkline, trend pill, sort control, Grid toggle).
  - `SinceYesterdayStrip.tsx` — region 4 timeline footer.
- **Reuse:** existing `PortfolioCard` grid from `OverviewPage` becomes the "Grid view" secondary (extract or import). `AggregateBar`/`AttentionPanel`/`MoversPanel`/`ReviewQueuePanel` are superseded on the landing — keep the components but stop rendering them in the digest path.
- **Data hooks:** `useDigest()` (TanStack Query, ~30–60s staleTime) hitting `/api/digest`; `useDigestNarrative()` hitting the structured narrative (longer staleTime, matches 10-min server cache). Types added to `dashboard/src/lib/types.ts`; fetchers in `api.ts`.
- **State handling:** loading skeletons per region (reserve space — no layout jump); empty/error states in the existing sci-fi "BOOT LINES" voice; narrative panel shows a graceful fallback if the structured call errors. Wrapped by the existing `ErrorBoundary` in `App.tsx`.

## 7. Accessibility & polish (carry the audit's quick wins here)
- Text contrast ≥ 4.5:1 (the `--text-0` 32% muted is borderline — use it only for non-essential labels, not data).
- Visible `:focus-visible` rings (2px violet) on the range toggle, sort control, grid toggle, and clickable rows/nodes.
- `prefers-reduced-motion`: disable aurora drift, line glow-pulse, and the live-dot pulse.
- All numbers `tabular-nums`. Color is never the sole signal (trend pills carry text labels; vs-SPY bar pairs with the signed number).
- Clickable rows/nodes get `cursor: pointer`, `role="button"`, `tabIndex`, keyboard handlers.

## 8. What is removed / preserved (explicit)
- **Removed from landing:** Map (ConstellationMap) and Chart (multi-portfolio PerformanceChart) view modes. The components are **not deleted** — they remain in the codebase, just unlinked from the default landing. (User explicitly chose to retire them from the overview.)
- **Preserved:** the 35-card Grid, reachable via the "Grid view" toggle in region 3.
- **Superseded but not deleted:** AggregateBar / AttentionPanel / MoversPanel / ReviewQueuePanel on the landing (their data is folded into the digest regions).

## 9. Resolved decisions (2026-05-29)
1. **Benchmark — RESOLVED.** The **book hero curve uses SPY** as the single yardstick for the whole operation. The **per-portfolio comparison column uses each portfolio's own configured benchmark** (e.g. microcap `^RUT`), labeled to match — column header reads "vs Bench" with the specific benchmark named per row (tooltip or sublabel), rather than mislabeling everything "vs SPY". The two book-level chips ("vs SPY · all-time/today") stay SPY-based.
2. **`posture` — RESOLVED.** Computed **deterministically** server-side (regime + net deployed exposure + momentum tilt → 0..1) and passed into the narrative prompt for consistency. Server-authoritative; the model does not invent it.
3. **Endpoint shape — RESOLVED.** Build a **new `GET /api/digest`** endpoint; leave `/api/portfolios/overview` untouched for any remaining callers.

## 10. Testing
- **Backend:** unit tests for the digest aggregation (active-only filter, `exclude_from_aggregates` respected, combined-curve alignment, vs-SPY math, NaN-safety), recap classification (BUY/SELL since prior close, multi-portfolio), and trend derivation. Structured-narrative test with **mocked Anthropic** (valid JSON, malformed JSON → fallback, model-error → fallback). Follow the hermetic `tests/integration/` fixture pattern.
- **Frontend:** `npx tsc --noEmit` clean; manual verification each region renders with real data from the running API (per project "verify before claiming success" rule).

## 11. Out of scope (future)
- Mobile-first layout.
- Click-through deep-linking refinements beyond navigating to an existing portfolio view.
- Any alerting/approval surfacing (separate roadmap items).
