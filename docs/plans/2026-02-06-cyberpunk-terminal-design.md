# Cyberpunk Trading Terminal Dashboard

**Date:** 2026-02-06
**Status:** Design Complete
**Target:** Dashboard UI/UX overhaul

## Overview

Transform the MicroCapRebuilder dashboard into a cyberpunk trading terminal with professional data density and futuristic aesthetics. Add live charts, market context, and visual freshness indicators while maintaining manual control.

## Design Goals

1. **Information Density** - Surface more data without clutter (charts, metrics, time-based insights)
2. **Professional + Cyberpunk Aesthetic** - Bloomberg Terminal functionality meets sci-fi HUD visuals
3. **Contextual Awareness** - Always show market context (indices) and data freshness
4. **Depth on Demand** - Sparklines for scanning, full candlestick charts for analysis

## Visual Design System

### Color Palette

```
Primary Accents:
- Cyan: #22D3EE (borders, chart lines, primary glow)
- Magenta: #E879F9 (highlights, exceptional metrics)
- Neon Green: #10B981 (profit, success, terminal aesthetic)

Status Colors:
- Profit/Up: #10B981 (neon green)
- Loss/Down: #EF4444 (red)
- Warning: #F59E0B (amber/orange)
- Neutral: #6B7280 (gray)

Backgrounds:
- Primary: #000000 (pure black)
- Surface: #0A0A0A (slightly lighter panels)
- Elevated: #141414 (cards, modals)

Text:
- Primary: #FFFFFF (white, 100%)
- Secondary: #A1A1AA (gray, 70%)
- Muted: #52525B (dim gray, 40%)
```

### Visual Effects

**Glow Effects:**
- Accent colors: `box-shadow: 0 0 8px rgba(color, 0.4)`
- Hover states: `box-shadow: 0 0 12px rgba(color, 0.6)`
- Chart lines: `filter: drop-shadow(0 0 2px rgba(color, 0.5))`

**Transparency & Glass:**
- Panel backgrounds: `rgba(10, 10, 10, 0.8)` with `backdrop-filter: blur(10px)`
- Borders: `1px solid rgba(34, 211, 238, 0.2)` with glow

**Typography:**
- Headers: Existing sans-serif
- Numbers/Metrics: Monospace (Space Mono or JetBrains Mono)
- Body text: Existing sans-serif

**Animations:**
- Transitions: `all 0.2s cubic-bezier(0.4, 0, 0.2, 1)`
- Pulse: Slow opacity fade (100% → 70% → 100%) for staleness
- Chart drawing: Animate-in on load (0.5s line draw)

## Layout Structure

```
┌─────────────────────────────────────────────────────────┐
│ Market Ticker Banner (60px)                            │
│ S&P 500 ↗ | Russell 2000 ↗ | VIX ↘ [sparklines]       │
├─────────────────────────────────────────────────────────┤
│ TopBar (existing + freshness indicator)                │
│ [Logo] [Metrics] ... [Updated 3m ago ⟳] [UPDATE][PAPER]│
├────────────────────────┬────────────────────────────────┤
│ Positions Panel        │ Right Panel                    │
│ [rows with sparklines] │ [Candlestick Chart]            │
│                        │ OR [Risk/Perf/Actions tabs]    │
├────────────────────────┼────────────────────────────────┤
│ Activity Feed          │ Mommy Co-pilot                 │
└────────────────────────┴────────────────────────────────┘
```

## Component 1: Market Ticker Banner

**Location:** Always-visible strip at very top (60px height, full width)

**Content (left to right):**

1. **S&P 500 (^GSPC)**
   - Current value: Large text (e.g., `4,521.23`)
   - Day change: Color-coded `+0.85%` (neon green up, red down)
   - Mini sparkline: 40px × 30px, 20 bars (5-min candles)

2. **Russell 2000 (^RUT)**
   - Same format as S&P 500
   - Portfolio benchmark - slightly brighter glow

3. **VIX (^VIX)**
   - Current value + day change
   - Sparkline (volatility context)

**Visual Treatment:**
- Background: Pure black with 10% cyan bottom border glow
- Text: White values, colored change %
- Sparklines: Cyan line with glow, gradient fill to transparent
- Separators: Thin vertical magenta lines (1px with glow)
- Update indicator: Small status dot (green < 2min, yellow 2-5min, orange 5-15min)

**Data Source:** New API endpoint `/api/market/indices` returning:
```typescript
{
  sp500: { value: 4521.23, change_pct: 0.85, sparkline: [/* 20 prices */] },
  russell2000: { value: 2145.67, change_pct: 1.2, sparkline: [...] },
  vix: { value: 18.42, change_pct: -2.1, sparkline: [...] }
}
```

**Behavior:**
- Static (not scrolling) - all three visible at once
- Updates when user clicks UPDATE or loads dashboard
- Future: Click to open larger modal chart

## Component 2: Enhanced Position Rows

**Current state:** Ticker, Qty, Price, P&L%, Progress bar, Weight

**New additions:**

### Mini Sparkline
- **Size:** 60px wide × 30px tall
- **Data:** 20-day closing prices
- **Style:** Cyan line with subtle glow, gradient fill (cyan → transparent)
- **Position:** Between Ticker and Qty columns
- **Visibility:** Always visible (not hover-only)

### Time-Based Metrics
- **Entry price:** Small gray text under current price: `(Entry: $257.64)`
- **Days held:** Replace or supplement entry_date: `12d` in compact format
- **Holding period return (APR):** Annualized return rate: `+47% APR`
  - Standard color if < 50% APR
  - Magenta color if exceptional (>100% APR)

### Updated Row Layout

```
┌──────────────────────────────────────────────────────┐
│ AEIS  [sparkline]  19  $270.45  +4.9%  +47% APR    │
│       ~~~~^~~~~         (Entry: $257.64)   12d      │
│       [━━━━●────] Stop→Target  10.2%                │
└──────────────────────────────────────────────────────┘
```

**Row Height:** Increase from ~50px to ~60px to accommodate sparkline

**Hover State:** Row border glows cyan, sparkline brightness increases

**Data Source:**
- Sparkline: New endpoint `/api/chart/{ticker}?range=20D&interval=1d`
- Time metrics: Calculated from existing transaction data + current position

## Component 3: Position Detail Candlestick Chart

**Trigger:** User clicks a position row → right panel shows full chart view

### Layout (top to bottom)

**1. Header (enhanced)**
- Existing: Ticker + P&L badge + [SELL] + [Back] buttons
- New: Time range selector chips below header
  - `[1D] [5D] [1M] [3M] [YTD] [ALL]`
  - Active chip: Cyan background with glow
  - Inactive: Dim border, white text

**2. Main Candlestick Chart (~300px height)**
- **Candles:** Green (up) / Red (down) with bright glow
- **Grid:** Subtle cyan grid lines (10% opacity)
- **Axes:**
  - Y-axis: Price labels on right (white text)
  - X-axis: Date labels on bottom
- **Crosshair:** Cyan lines on hover, floating tooltip shows price + date
- **Entry annotation:** Horizontal dotted amber line at entry price with label
- **Stop/Target lines:** Red (stop) and green (target) horizontal dotted lines

**3. Volume Bars (below main chart, ~60px)**
- Green/red bars matching candle colors
- Gradient fill (solid → transparent at bottom)
- Y-axis shows volume scale

**4. Indicators Panel (~80px)**
- **RSI (14):** Line chart, cyan line
  - Overbought zone (70+): Light red tint
  - Oversold zone (<30): Light green tint
- **Moving Averages (overlaid on main chart):**
  - 20 SMA: Cyan line
  - 50 SMA: Magenta line

**5. Metrics Summary (existing detail rows stay below chart)**

### Chart Library

**Primary Choice: Lightweight Charts (TradingView)**
- Professional candlestick + volume support
- Performant (canvas-based)
- Customizable styling
- MIT license

**Implementation:**
```bash
npm install lightweight-charts
```

Create wrapper component `CandlestickChart.tsx`:
```typescript
import { createChart } from 'lightweight-charts';

interface Props {
  ticker: string;
  range: '1D' | '5D' | '1M' | '3M' | 'YTD' | 'ALL';
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
}
```

**Data Source:** `/api/chart/{ticker}?range={range}`
Returns OHLCV data:
```typescript
{
  ticker: "AEIS",
  range: "1M",
  data: [
    { time: "2025-12-06", open: 250.0, high: 252.0, low: 248.0, close: 251.0, volume: 125000 },
    // ...
  ],
  indicators: {
    rsi: [45.2, 47.1, ...],
    sma_20: [248.5, 249.0, ...],
    sma_50: [245.0, 246.0, ...]
  }
}
```

## Component 4: Staleness System

**Goal:** Visual awareness of data freshness without nagging.

### Primary Indicator (TopBar)

**Badge location:** Next to UPDATE button

**Format:** `Updated 3m ago`

**Color coding by age:**
- **< 2 min:** Dim text (gray), no animation (fresh)
- **2-5 min:** Yellow text, subtle pulse (1s interval)
- **5-15 min:** Orange text, stronger pulse (0.7s interval)
- **> 15 min:** Red text, urgent pulse + UPDATE button gets cyan glow ring

**Pulse animation:**
```css
@keyframes staleness-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
```

### Component-Level Tracking

Each data type tracks its own `lastUpdated` timestamp:
- Market indices
- Position prices
- Chart data

**Zustand store addition:**
```typescript
interface FreshnessStore {
  lastUpdated: {
    marketData: Date | null;
    positions: Date | null;
    charts: Record<string, Date>; // per ticker
  };
  updateTimestamp: (key: string) => void;
  getStalenessSeverity: (key: string) => 'fresh' | 'stale' | 'very-stale' | 'critical';
}
```

**Tooltip on hover:** Shows breakdown:
```
Market data: 2m ago
Positions: 3m ago
Charts: 3m ago
```

### Market Hours Awareness

**When market closed:**
- Badge shows: `Market Closed • Updated 3m ago` (dim gray)
- No pulse animation (staleness matters less off-hours)

**Detection:** Check current time against market hours (9:30 AM - 4:00 PM ET, Mon-Fri)

## Technical Implementation

### New Components

| Component | Purpose | Location |
|-----------|---------|----------|
| `MarketTickerBanner.tsx` | Top banner with 3 index sparklines | New, above TopBar |
| `PositionRowSparkline.tsx` | Mini chart for position rows | Embedded in PositionsPanel |
| `CandlestickChart.tsx` | Full chart with indicators | Replaces progress viz in PositionDetail |
| `FreshnessIndicator.tsx` | Staleness badge + pulse | TopBar enhancement |

### Modified Components

| Component | Changes |
|-----------|---------|
| `App.tsx` | Add MarketTickerBanner above TopBar |
| `TopBar.tsx` | Integrate FreshnessIndicator near UPDATE button |
| `PositionsPanel.tsx` | Add sparklines + time metrics to rows, increase row height |
| `PositionDetail.tsx` | Replace progress visualization with CandlestickChart |

### New API Endpoints

**1. Market Indices**
```
GET /api/market/indices
Response: { sp500: {...}, russell2000: {...}, vix: {...} }
```

**2. Historical Chart Data**
```
GET /api/chart/{ticker}?range=1M&interval=1d
Response: { ticker, range, data: [OHLCV], indicators: {...} }
```

Parameters:
- `range`: 1D, 5D, 1M, 3M, YTD, ALL
- `interval`: 1m, 5m, 15m, 1h, 1d (auto-selected based on range)

**3. Position Update Enhancement**
```
POST /api/state/update
(existing endpoint - ensure it returns lastUpdated timestamps)
```

### Data Flow

**On dashboard load:**
1. Fetch market indices → render MarketTickerBanner
2. Fetch positions (existing) → render rows
3. Lazy-load sparklines per position (as they scroll into view)
4. Store all `lastUpdated` timestamps in Zustand

**On UPDATE button click:**
1. Fetch fresh market indices
2. Fetch fresh position prices (existing flow)
3. Update all `lastUpdated` timestamps
4. Reset staleness pulse animations

**On position row click:**
1. Open PositionDetail in right panel
2. Fetch chart data for selected ticker + default range (1M)
3. Render CandlestickChart with indicators
4. Store chart `lastUpdated` timestamp

**Chart range change:**
- Re-fetch chart data with new range parameter
- Update chart view (no full component remount)

### Performance Considerations

**Chart data caching:**
- Cache chart responses in Zustand (keyed by `{ticker}:{range}`)
- TTL: 5 minutes for intraday ranges (1D, 5D), 1 hour for longer ranges
- Sparkline data cached separately (20-day window)

**Bundle size:**
- Lightweight Charts: ~60KB gzipped
- Load chart library lazily (code-split)
- Only load when user opens position detail for first time

**API rate limits:**
- Market indices: Max 1 req/min (low frequency)
- Position updates: Manual only (user-controlled)
- Chart data: Cached aggressively, max 20 concurrent charts

## Implementation Phases

### Phase 1: Visual Foundation (2-3 days)
- Implement color palette + glow effects in Tailwind config
- Create shared chart styles/themes
- Update all backgrounds to pure black (#000000)
- Add monospace font for metrics

### Phase 2: Market Ticker Banner (1-2 days)
- Create MarketTickerBanner component
- Add `/api/market/indices` endpoint
- Integrate mini sparklines (simple line charts)
- Wire up to App.tsx layout

### Phase 3: Position Row Sparklines (2-3 days)
- Create PositionRowSparkline component
- Add `/api/chart/{ticker}` endpoint (basic OHLCV)
- Calculate time-based metrics (entry price, days held, APR)
- Integrate into PositionsPanel rows
- Adjust row height + hover effects

### Phase 4: Staleness System (1-2 days)
- Create FreshnessIndicator component
- Add Zustand freshness store
- Implement pulse animations + color coding
- Wire up to UPDATE button workflow
- Add market hours detection

### Phase 5: Candlestick Chart (3-4 days)
- Install + wrap Lightweight Charts library
- Create CandlestickChart component
- Add volume bars + RSI indicator panel
- Implement time range selector
- Add entry/stop/target line annotations
- Integrate into PositionDetail view

### Phase 6: Polish & Testing (2-3 days)
- Fine-tune glow effects + animations
- Test staleness system edge cases
- Verify chart performance with multiple positions
- Mobile/responsive adjustments (if needed)
- API error handling + loading states

**Total Estimate:** 11-17 days (2-3 weeks)

## Success Metrics

**Qualitative:**
- Dashboard feels "professional" and "futuristic"
- Information density increases without feeling cluttered
- Data freshness is always clear at a glance

**Quantitative:**
- Chart load time: < 500ms (with caching)
- Sparkline render: < 100ms per row
- Market ticker update: < 200ms
- No performance degradation with 15+ positions

## Future Enhancements (Out of Scope)

- Real-time WebSocket price streaming
- Click market ticker to open larger modal chart
- Customizable indicators (user chooses which to show)
- Multiple chart layouts (side-by-side comparison)
- Heatmap view for all positions
- Animated trade execution flow visualization
- Voice commands ("Mommy, show me AEIS chart")

## References

- TradingView Lightweight Charts: https://tradingview.github.io/lightweight-charts/
- Cyberpunk color palette inspiration: https://www.cyberpunk.net
- Professional terminal aesthetics: Bloomberg Terminal, ThinkorSwim
