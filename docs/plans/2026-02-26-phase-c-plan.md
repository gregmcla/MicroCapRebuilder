# Phase C: Signal Dashboard Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the dashboard from four competing panels into a focused signal layout: dense positions left, context-sensitive focus pane right, Mommy as a persistent strip.

**Architecture:** Remove react-resizable-panels entirely. CSS flex layout with fixed 55/45 split. New FocusPane component replaces RightPanel + tabs. MommyCoPilot compresses to a 36px strip. ActivityFeed moves to a slide-over overlay.

**Tech Stack:** React 19, Tailwind v4, Zustand, TanStack Query, JetBrains Mono

---

## Task 1: Update CSS Color Tokens

**Files:**
- Modify: `dashboard/src/index.css`

Separate jade accent from profit green. Kill all glows.

**Step 1: Replace the entire `@theme` block with:**

```css
@theme {
  /* Backgrounds */
  --color-bg-primary:    #000000;
  --color-bg-surface:    #080808;
  --color-bg-elevated:   #101010;

  /* Borders — barely there */
  --color-border:        #151515;
  --color-border-hover:  #222222;

  /* Jade — UI chrome ONLY (ANALYZE button + selected position) */
  --color-cyber-cyan:    #00D488;
  --color-cyber-magenta: #00D488;
  --color-cyber-green:   #00D488;
  --color-accent:        #00D488;
  --color-accent-dim:    #003D27;

  /* Profit/loss — DATA only, separate from accent */
  --color-profit:        #4ADE80;
  --color-profit-dim:    #14532D;
  --color-loss:          #F87171;
  --color-loss-dim:      #4D0010;
  --color-warning:       #FBBF24;
  --color-warning-dim:   #78350F;

  /* Text */
  --color-text-primary:   #EDEDED;
  --color-text-secondary: #4A4A4A;
  --color-text-muted:     #282828;

  /* Typography */
  --font-sans: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  /* Glows — NONE */
  --shadow-glow-cyan:    none;
  --shadow-glow-cyan-lg: none;
  --shadow-glow-magenta: none;
  --shadow-glow-green:   none;

  /* Animations */
  --animate-pulse-slow: pulse-slow 1s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  --animate-pulse-fast: pulse-fast 0.7s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
```

**Step 2: Verify build passes**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/index.css && git commit -m "feat: phase-c — separate accent from profit, kill glows"
```

---

## Task 2: Update Store — Add mommyExpanded + activityOpen

**Files:**
- Modify: `dashboard/src/lib/store.ts`

**Step 1: Extend the `UIStore` interface and implementation**

Find the `UIStore` interface:
```typescript
interface UIStore {
  rightTab: RightTab;
  setRightTab: (tab: RightTab) => void;
  selectedPosition: Position | null;
  selectPosition: (pos: Position | null) => void;
}
```

Replace with:
```typescript
interface UIStore {
  rightTab: RightTab;
  setRightTab: (tab: RightTab) => void;
  selectedPosition: Position | null;
  selectPosition: (pos: Position | null) => void;
  mommyExpanded: boolean;
  toggleMommy: () => void;
  activityOpen: boolean;
  toggleActivity: () => void;
}
```

Find the `useUIStore` implementation:
```typescript
export const useUIStore = create<UIStore>((set) => ({
  rightTab: "actions",
  setRightTab: (tab) => set({ rightTab: tab, selectedPosition: null }),
  selectedPosition: null,
  selectPosition: (pos) => set({ selectedPosition: pos }),
}));
```

Replace with:
```typescript
export const useUIStore = create<UIStore>((set) => ({
  rightTab: "actions",
  setRightTab: (tab) => set({ rightTab: tab, selectedPosition: null }),
  selectedPosition: null,
  selectPosition: (pos) => set({ selectedPosition: pos }),
  mommyExpanded: false,
  toggleMommy: () => set((s) => ({ mommyExpanded: !s.mommyExpanded })),
  activityOpen: false,
  toggleActivity: () => set((s) => ({ activityOpen: !s.activityOpen })),
}));
```

**Step 2: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/lib/store.ts && git commit -m "feat: phase-c — store: mommyExpanded, activityOpen"
```

---

## Task 3: Keyboard Shortcuts — Add F for Activity Feed

**Files:**
- Modify: `dashboard/src/hooks/useKeyboardShortcuts.ts`

**Step 1: Add toggleActivity to the hook**

Find the line:
```typescript
const setRightTab = useUIStore((s) => s.setRightTab);
```

Add below it:
```typescript
const toggleActivity = useUIStore((s) => s.toggleActivity);
```

Find the switch statement and add the `f` case before the closing brace:
```typescript
case "f":
  toggleActivity();
  break;
```

Also add `toggleActivity` to the `useEffect` dependency array.

**Step 2: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/hooks/useKeyboardShortcuts.ts && git commit -m "feat: phase-c — F key toggles activity feed"
```

---

## Task 4: Compress TopBar to 36px Inline Metrics

**Files:**
- Modify: `dashboard/src/components/TopBar.tsx`

This is a substantial rewrite of the visual layer. The `UpdatePricesButton`, `ScanButton`, `EmergencyClose`, `ModeToggle` component logic stays intact — only the visual presentation of the wrapper and metric display changes.

**Step 1: Delete the `MetricPill` component entirely** (lines 12–29)

**Step 2: Replace `RegimeBadge` with inline text (no background)**

```tsx
function RegimeBadge({ regime }: { regime: string }) {
  const cfg: Record<string, { icon: string; cls: string }> = {
    BULL: { icon: "🐂", cls: "text-profit" },
    BEAR: { icon: "🐻", cls: "text-loss" },
    SIDEWAYS: { icon: "↔️", cls: "text-warning" },
  };
  const { icon, cls } = cfg[regime] ?? cfg.SIDEWAYS;
  return (
    <span className={`text-xs font-semibold ${cls}`}>
      {icon} {regime}
    </span>
  );
}
```

**Step 3: Replace `RiskBadge` with inline text (no border/background)**

```tsx
function RiskBadge() {
  const { data: risk } = useRisk();
  const score = risk?.overall_score;
  const color =
    score == null ? "text-text-muted"
    : score >= 70 ? "text-profit"
    : score >= 40 ? "text-warning"
    : "text-loss";
  return (
    <span className={`font-mono text-xs ${color}`}>
      {score != null ? Math.round(score) : "--"}
    </span>
  );
}
```

**Step 4: Update `UpdatePricesButton` — plain text style**

Change the button className to:
```
"text-xs text-text-secondary hover:text-text-primary disabled:opacity-40 transition-colors"
```
Remove the surrounding `<div className="flex items-center gap-1.5">` wrapper — keep only the button and result span.

**Step 5: Update `ScanButton` — same plain text style**

Same className as UPDATE button above. Remove outer div wrapper, keep button + result span.

**Step 6: Update `AnalyzeExecuteButtons` — keep ANALYZE solid jade, tighten gap**

Change outer div gap: `gap-1.5` → `gap-2`

ANALYZE button: keep `"px-3 py-1 text-xs font-bold bg-accent text-black rounded-sm hover:bg-accent/90 disabled:opacity-40 transition-colors"` (already correct from phase B)

EXECUTE button: keep `"px-3 py-1 text-xs font-semibold border border-accent/40 text-accent rounded-sm hover:bg-accent/10 disabled:opacity-40 transition-colors"` (already correct)

Remove `<FreshnessIndicator />` from inside `AnalyzeExecuteButtons` — it moves to inline in the header.

**Step 7: Rewrite the main `TopBar` return JSX**

Replace the loading state return:
```tsx
if (isLoading || !state) {
  return (
    <header className="h-9 flex items-center gap-3 px-4 bg-bg-surface border-b border-border shrink-0">
      <div className="flex items-center gap-1.5">
        <span className="text-sm font-bold text-accent font-mono">M</span>
        <span className="text-[10px] font-semibold text-text-secondary tracking-widest uppercase">MOMMY</span>
      </div>
      <span className="text-text-muted text-[10px]">|</span>
      <PortfolioSwitcher />
      {isLoading && <span className="text-[10px] text-text-muted animate-pulse">Loading...</span>}
    </header>
  );
}
```

Replace the full loaded state return with:
```tsx
const pnlColor = state.day_pnl >= 0 ? "text-profit" : "text-loss";
const overallPnl = state.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
const overallColor = overallPnl >= 0 ? "text-profit" : "text-loss";
const returnColor = state.total_return_pct >= 0 ? "text-profit" : "text-loss";

return (
  <header className="h-9 flex items-center gap-3 px-4 bg-bg-surface border-b border-border shrink-0 shrink-0">
    {/* Logo */}
    <div className="flex items-center gap-1.5 shrink-0">
      <span className="text-sm font-bold text-accent font-mono">M</span>
      <span className="text-[10px] font-semibold text-text-secondary tracking-widest uppercase">MOMMY</span>
    </div>
    <span className="text-border text-xs">|</span>
    <PortfolioSwitcher />
    <span className="text-border text-xs">·</span>

    {/* Inline metrics */}
    <span className="font-mono text-xs text-text-primary tabular-nums">
      ${state.total_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
    </span>
    <span className={`font-mono text-xs tabular-nums ${pnlColor}`}>
      {state.day_pnl >= 0 ? "+" : ""}${state.day_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
    </span>
    <span className={`font-mono text-xs tabular-nums ${returnColor}`}>
      {state.total_return_pct >= 0 ? "+" : ""}{state.total_return_pct.toFixed(1)}%
    </span>
    <span className="text-border text-xs">·</span>

    <RegimeBadge regime={state.regime ?? "SIDEWAYS"} />
    <RiskBadge />
    <span className="text-border text-xs">·</span>

    {/* Freshness */}
    <FreshnessIndicator />

    {/* Action buttons */}
    <div className="flex items-center gap-2">
      <UpdatePricesButton />
      <ScanButton />
      <AnalyzeExecuteButtons />
    </div>

    <div className="flex-1" />

    {/* Warnings */}
    {state.stale_alerts.length > 0 && (
      <span className="text-[10px] text-warning">{state.stale_alerts.length} stale</span>
    )}
    {state.price_failures.length > 0 && (
      <span className="text-[10px] text-loss">{state.price_failures.length} failed</span>
    )}

    <EmergencyClose positions={state.positions} />
    <ModeToggle paperMode={state.paper_mode} />
  </header>
);
```

**Step 8: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```
Fix any TypeScript errors — the main risk is unused imports after removing MetricPill.

**Step 9: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/TopBar.tsx && git commit -m "feat: phase-c — topbar 36px inline metrics"
```

---

## Task 5: PositionRowSparkline — Accept Height Prop

**Files:**
- Modify: `dashboard/src/components/PositionRowSparkline.tsx`

**Step 1: Change the component to accept a height prop**

Find:
```typescript
const WIDTH = 60;
const HEIGHT = 30;
const PADDING = 5;

interface PositionRowSparklineProps {
  ticker: string;
}

function PositionRowSparkline({ ticker }: PositionRowSparklineProps) {
```

Replace with:
```typescript
const WIDTH = 60;
const PADDING = 2;

interface PositionRowSparklineProps {
  ticker: string;
  height?: number;
}

function PositionRowSparkline({ ticker, height = 30 }: PositionRowSparklineProps) {
  const HEIGHT = height;
```

Update the loading state div height:
```tsx
<div className="w-[60px] bg-bg-surface rounded animate-pulse" style={{ height }} />
```

Update the error state div:
```tsx
<div className="w-[60px] bg-bg-surface rounded opacity-30 border border-loss/30" style={{ height }} />
```

Update the no-data state div:
```tsx
<div className="w-[60px] bg-bg-surface rounded opacity-40" style={{ height }} />
```

Update the SVG element:
```tsx
<svg width={WIDTH} height={height} ...>
```

**Step 2: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PositionRowSparkline.tsx && git commit -m "feat: phase-c — sparkline height prop"
```

---

## Task 6: Redesign PositionsPanel — 28px Rows, 4 Columns, Dot

**Files:**
- Modify: `dashboard/src/components/PositionsPanel.tsx`

This is the most visible change. Rows go from ~56px to 28px. Columns reduce from 7 to 4.

**Step 1: Replace the entire `PositionRow` component**

Remove the old `PositionRow` function and replace with:

```tsx
function PositionRow({ pos, onClick, isSelected }: { pos: Position; onClick: () => void; isSelected: boolean }) {
  const pnlColor = pos.unrealized_pnl_pct > 0 ? "text-profit" : pos.unrealized_pnl_pct < 0 ? "text-loss" : "text-text-secondary";

  const range = pos.take_profit - pos.stop_loss;
  const progress = range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;
  const dotColor = progress > 60 ? "#4ADE80" : progress > 30 ? "#282828" : "#F87171";

  return (
    <div
      onClick={onClick}
      className={`flex items-center h-7 px-3 gap-2 cursor-pointer transition-colors ${
        isSelected
          ? "bg-bg-elevated border-l-2 border-accent"
          : "hover:bg-bg-elevated border-l-2 border-transparent"
      }`}
    >
      <span className="w-12 font-mono text-[13px] font-bold text-text-primary shrink-0">
        {pos.ticker}
      </span>
      <div className="flex-1 min-w-0">
        <PositionRowSparkline ticker={pos.ticker} height={22} />
      </div>
      <span className="w-20 font-mono text-[13px] text-text-primary text-right tabular-nums shrink-0">
        ${pos.current_price.toFixed(2)}
      </span>
      <span className={`w-14 font-mono text-[13px] font-semibold text-right tabular-nums shrink-0 ${pnlColor}`}>
        {pos.unrealized_pnl_pct >= 0 ? "+" : ""}{pos.unrealized_pnl_pct.toFixed(1)}%
      </span>
      <div className="w-3 flex items-center justify-center shrink-0">
        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: dotColor }} />
      </div>
    </div>
  );
}
```

**Step 2: Update `PositionsPanel` to pass `isSelected`**

The `PositionsPanel` component needs to read `selectedPosition` from store and pass `isSelected` to each row.

Add to imports:
```typescript
import { useUIStore } from "../lib/store";
```

In the `PositionsPanel` function body, add:
```typescript
const selectedPosition = useUIStore((s) => s.selectedPosition);
const selectPosition = useUIStore((s) => s.selectPosition);
```

In the sorted.map call, update:
```tsx
sorted.map((pos) => (
  <PositionRow
    key={pos.ticker}
    pos={pos}
    isSelected={selectedPosition?.ticker === pos.ticker}
    onClick={() => selectPosition(selectedPosition?.ticker === pos.ticker ? null : pos)}
  />
))
```
(Clicking the selected row deselects it — toggle behavior.)

**Step 3: Update column headers to match new 4-column layout**

Replace the column header div with:
```tsx
<div className="flex items-center gap-2 px-3 py-1 text-[10px] text-text-muted uppercase tracking-wider border-b border-border">
  <span className="w-12">Ticker</span>
  <span className="flex-1">Trend</span>
  <span className="w-20 text-right">Price</span>
  <span className="w-14 text-right">P&L</span>
  <span className="w-3" />
</div>
```

**Step 4: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 5: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PositionsPanel.tsx && git commit -m "feat: phase-c — 28px position rows, 4 cols, dot indicator"
```

---

## Task 7: Create PortfolioSummary Component

**Files:**
- Create: `dashboard/src/components/PortfolioSummary.tsx`

This is the default state of the FocusPane. Hero equity number + key metrics + nav links.

**Step 1: Create the file**

```tsx
/** Default focus pane state — portfolio hero metrics + nav. */

import { usePortfolioState } from "../hooks/usePortfolioState";
import { useRisk } from "../hooks/useRisk";
import { useUIStore } from "../lib/store";
import type { RightTab } from "../lib/store";

function NavLink({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-[10px] uppercase tracking-wider transition-colors ${
        active ? "text-text-primary font-semibold" : "text-text-muted hover:text-text-secondary"
      }`}
    >
      {label}
    </button>
  );
}

export default function PortfolioSummary() {
  const { data: state } = usePortfolioState();
  const { data: risk } = useRisk();
  const rightTab = useUIStore((s) => s.rightTab);
  const setRightTab = useUIStore((s) => s.setRightTab);

  const overallPnl = state?.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0) ?? 0;
  const overallColor = overallPnl >= 0 ? "text-profit" : "text-loss";
  const dayColor = (state?.day_pnl ?? 0) >= 0 ? "text-profit" : "text-loss";
  const returnColor = (state?.total_return_pct ?? 0) >= 0 ? "text-profit" : "text-loss";

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      {/* Nav links */}
      <div className="flex items-center gap-4">
        <NavLink label="Summary" active={rightTab === "actions"} onClick={() => setRightTab("actions")} />
        <NavLink label="Risk" active={false} onClick={() => setRightTab("risk")} />
        <NavLink label="Performance" active={false} onClick={() => setRightTab("performance")} />
      </div>

      {/* Hero equity */}
      <div>
        <div className="font-mono text-[32px] font-semibold text-text-primary leading-none tabular-nums">
          ${(state?.total_equity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </div>
        <div className="text-[10px] text-text-muted uppercase tracking-wider mt-1">
          Portfolio Equity
        </div>
      </div>

      {/* P&L row */}
      <div className="flex items-center gap-4">
        <div>
          <div className={`font-mono text-sm tabular-nums font-semibold ${overallColor}`}>
            {overallPnl >= 0 ? "+" : ""}${overallPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Total P&L</div>
        </div>
        <div>
          <div className={`font-mono text-sm tabular-nums font-semibold ${dayColor}`}>
            {(state?.day_pnl ?? 0) >= 0 ? "+" : ""}${(state?.day_pnl ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Today</div>
        </div>
        <div>
          <div className={`font-mono text-sm tabular-nums font-semibold ${returnColor}`}>
            {(state?.total_return_pct ?? 0) >= 0 ? "+" : ""}{(state?.total_return_pct ?? 0).toFixed(1)}%
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Return</div>
        </div>
        <div>
          <div className="font-mono text-sm tabular-nums text-text-primary">
            ${(state?.cash ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Cash</div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Status row */}
      <div className="flex items-center gap-3 text-xs">
        <span className={`font-semibold ${
          state?.regime === "BULL" ? "text-profit"
          : state?.regime === "BEAR" ? "text-loss"
          : "text-warning"
        }`}>
          {state?.regime ?? "—"}
        </span>
        <span className="text-text-muted">·</span>
        <span className="text-text-secondary">
          Risk <span className={`font-mono font-semibold ${
            (risk?.overall_score ?? 0) >= 70 ? "text-profit"
            : (risk?.overall_score ?? 0) >= 40 ? "text-warning"
            : "text-loss"
          }`}>{risk?.overall_score != null ? Math.round(risk.overall_score) : "—"}</span>
        </span>
        <span className="text-text-muted">·</span>
        <span className="text-text-secondary">
          <span className="font-mono font-semibold text-text-primary">{state?.positions.length ?? 0}</span> positions
        </span>
        <span className="text-text-muted">·</span>
        <span className={state?.paper_mode ? "text-warning text-[10px] uppercase tracking-wider" : "text-loss text-[10px] uppercase tracking-wider font-bold"}>
          {state?.paper_mode ? "Paper" : "Live"}
        </span>
      </div>

      {/* Warnings */}
      {(state?.stale_alerts.length ?? 0) > 0 && (
        <div className="text-[11px] text-warning">
          {state!.stale_alerts.length} stale alert{state!.stale_alerts.length > 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PortfolioSummary.tsx && git commit -m "feat: phase-c — PortfolioSummary component"
```

---

## Task 8: Create FocusPane Component

**Files:**
- Create: `dashboard/src/components/FocusPane.tsx`

Replaces RightPanel. Context-sensitive — shows the right thing without tabs.

**Step 1: Create the file**

```tsx
/** Context-sensitive focus pane — replaces tab-based RightPanel. */

import { useUIStore } from "../lib/store";
import { useAnalysisStore } from "../lib/store";
import ActionsTab from "./ActionsTab";
import RiskTab from "./RiskTab";
import PerformanceTab from "./PerformanceTab";
import PositionDetail from "./PositionDetail";
import PortfolioSummary from "./PortfolioSummary";

interface FocusPaneProps {
  className?: string;
}

export default function FocusPane({ className = "" }: FocusPaneProps) {
  const selectedPosition = useUIStore((s) => s.selectedPosition);
  const rightTab = useUIStore((s) => s.rightTab);
  const { result, isAnalyzing } = useAnalysisStore();

  // Priority: position detail > analysis > tab content > summary
  if (selectedPosition) {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <PositionDetail pos={selectedPosition} />
      </div>
    );
  }

  if (isAnalyzing || result) {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <ActionsTab />
      </div>
    );
  }

  if (rightTab === "risk") {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <div className="flex items-center gap-2 px-4 pt-3 pb-1">
          <button
            onClick={() => useUIStore.getState().setRightTab("actions")}
            className="text-[10px] text-text-muted hover:text-text-secondary uppercase tracking-wider transition-colors"
          >
            ← Summary
          </button>
          <span className="text-[10px] text-text-muted uppercase tracking-wider">/ Risk</span>
        </div>
        <RiskTab />
      </div>
    );
  }

  if (rightTab === "performance") {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <div className="flex items-center gap-2 px-4 pt-3 pb-1">
          <button
            onClick={() => useUIStore.getState().setRightTab("actions")}
            className="text-[10px] text-text-muted hover:text-text-secondary uppercase tracking-wider transition-colors"
          >
            ← Summary
          </button>
          <span className="text-[10px] text-text-muted uppercase tracking-wider">/ Performance</span>
        </div>
        <PerformanceTab />
      </div>
    );
  }

  return (
    <div className={`overflow-y-auto ${className}`}>
      <PortfolioSummary />
    </div>
  );
}
```

**Step 2: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/FocusPane.tsx && git commit -m "feat: phase-c — FocusPane context-sensitive pane"
```

---

## Task 9: MommyStrip — Compress to 36px Strip with Expand

**Files:**
- Modify: `dashboard/src/components/MommyCoPilot.tsx`

Add a `MommyStrip` export (collapsed 36px bar) while keeping full `MommyCoPilot` for the expanded state.

**Step 1: Add `MommyStrip` as a named export at the bottom of MommyCoPilot.tsx**

First, add the import for `useUIStore` at the top of the file (it already imports from `"../lib/store"` — add `useUIStore` to that import).

Then add this component at the very end of the file (before the final export default):

```tsx
/** Collapsed 36px strip — always visible at bottom of right column. */
export function MommyStrip() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const toggleMommy = useUIStore((s) => s.toggleMommy);
  const mommyExpanded = useUIStore((s) => s.mommyExpanded);

  const { data: insight } = useQuery<MommyInsight>({
    queryKey: ["mommyInsight", portfolioId],
    queryFn: () => api.getMommyInsight(portfolioId),
    refetchInterval: 60_000,
    enabled: portfolioId !== "overview",
  });

  const text = insight?.insight ?? "Mommy's watching the market...";

  return (
    <div className="h-9 flex items-center gap-2 px-3 border-t border-border bg-bg-surface shrink-0">
      {/* Jade dot */}
      <div className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
      <span className="text-[10px] text-text-muted uppercase tracking-wider shrink-0">MOMMY</span>
      <span className="text-[10px] text-text-muted mx-1 shrink-0">—</span>
      {/* Insight text truncated */}
      <span className="flex-1 text-[11px] text-text-secondary italic truncate min-w-0">
        {text}
      </span>
      {/* Expand/collapse button */}
      <button
        onClick={toggleMommy}
        className="shrink-0 text-[10px] text-text-muted hover:text-text-secondary transition-colors px-1"
        title={mommyExpanded ? "Collapse" : "Expand chat"}
      >
        {mommyExpanded ? "↓" : "↑"}
      </button>
    </div>
  );
}
```

**Step 2: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/MommyCoPilot.tsx && git commit -m "feat: phase-c — MommyStrip collapsed bar"
```

---

## Task 10: New App Layout — Remove Resizable Panels

**Files:**
- Modify: `dashboard/src/App.tsx`

This brings everything together. Remove `react-resizable-panels`, use CSS flex.

**Step 1: Replace the entire file content**

```tsx
/** Signal layout — positions left, focus pane right, Mommy strip. */

import { usePortfolioState } from "./hooks/usePortfolioState";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { usePortfolioStore, useUIStore } from "./lib/store";
import MarketTickerBanner from "./components/MarketTickerBanner";
import TopBar from "./components/TopBar";
import PositionsPanel from "./components/PositionsPanel";
import FocusPane from "./components/FocusPane";
import MommyCoPilot, { MommyStrip } from "./components/MommyCoPilot";
import ActivityFeed from "./components/ActivityFeed";
import OverviewPage from "./components/OverviewPage";

export default function App() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const isOverview = portfolioId === "overview";
  const { data: state, isLoading } = usePortfolioState();
  const mommyExpanded = useUIStore((s) => s.mommyExpanded);
  const activityOpen = useUIStore((s) => s.activityOpen);
  const toggleActivity = useUIStore((s) => s.toggleActivity);
  useKeyboardShortcuts();

  return (
    <div className="h-screen flex flex-col bg-bg-primary overflow-hidden">
      <MarketTickerBanner />
      <TopBar state={isOverview ? undefined : state} isLoading={isOverview ? false : isLoading} />

      {isOverview ? (
        <OverviewPage />
      ) : (
        <div className="flex flex-1 overflow-hidden">
          {/* Left: positions — always 55% */}
          <div className="w-[55%] flex flex-col border-r border-border bg-bg-surface overflow-hidden">
            <PositionsPanel
              positions={state?.positions ?? []}
              isLoading={isLoading}
            />
          </div>

          {/* Right: focus pane + mommy strip */}
          <div className="flex-1 flex flex-col bg-bg-surface overflow-hidden">
            {mommyExpanded ? (
              <MommyCoPilot />
            ) : (
              <FocusPane className="flex-1" />
            )}
            <MommyStrip />
          </div>
        </div>
      )}

      {/* Activity feed slide-over */}
      {activityOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={toggleActivity}
          />
          <div className="fixed left-0 top-0 bottom-0 w-72 z-50 bg-bg-surface border-r border-border flex flex-col shadow-xl overflow-hidden"
            style={{ top: "calc(28px + 36px)" }} // below banner + topbar
          >
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <span className="text-[10px] text-text-muted uppercase tracking-wider">Activity</span>
              <button onClick={toggleActivity} className="text-text-muted hover:text-text-primary text-xs">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <ActivityFeed transactions={state?.transactions ?? []} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

**Step 2: Verify build — this is the critical integration step**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

Fix any TypeScript errors. Common issues:
- `MommyCoPilot` is default export, `MommyStrip` is named — import as `import MommyCoPilot, { MommyStrip } from "./components/MommyCoPilot"`
- ActivityFeed might not accept `transactions` prop directly — check its props interface

**Step 3: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/App.tsx && git commit -m "feat: phase-c — new signal layout, remove resizable panels"
```

---

## Task 11: Delete RightPanel.tsx

**Files:**
- Delete: `dashboard/src/components/RightPanel.tsx`

**Step 1: Verify nothing imports RightPanel**
```bash
grep -r "RightPanel" /Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/
```
Expected: zero results (App.tsx no longer imports it after Task 10).

**Step 2: Delete the file**
```bash
rm /Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/RightPanel.tsx
```

**Step 3: Final build verify**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```
Expected: `✓ built` clean.

**Step 4: Commit**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add -A && git commit -m "feat: phase-c — delete RightPanel (replaced by FocusPane)"
```

---

## Verification Checklist

After all tasks, visually inspect at `http://localhost:5173`:

- [ ] TopBar is visibly shorter (36px), metrics are inline text, no pill backgrounds
- [ ] Positions panel is ~55% of screen width
- [ ] Position rows are visibly denser — ~28px height, 4 columns only (ticker, sparkline, price, P&L%)
- [ ] Selected position: jade left border, row elevated
- [ ] Dot indicator visible at end of each row (green/gray/red)
- [ ] Focus pane shows portfolio summary by default (hero equity number)
- [ ] Clicking a position: focus pane shows position detail + chart
- [ ] Hitting ANALYZE: focus pane shows analysis results
- [ ] Summary → Risk link navigates to risk view with ← back link
- [ ] Summary → Performance link navigates to performance view
- [ ] Mommy strip visible as 36px bar at bottom of right column
- [ ] Clicking ↑ in Mommy strip: expands to full chat
- [ ] Clicking ↓: collapses back
- [ ] F key toggles activity feed slide-over
- [ ] No orange or cyan anywhere — only jade on ANALYZE + selected row border
- [ ] Profit numbers are `#4ADE80` (muted green), distinct from jade accent
