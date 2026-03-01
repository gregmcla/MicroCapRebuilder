# Phosphor Jade Dashboard Polish — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Retheme the dashboard to Phosphor Jade — a premium dark terminal aesthetic with jade (#00D488) as the primary accent and profit color, true blacks, sharp buttons, and hairline borders.

**Architecture:** Pure frontend changes only. CSS token update cascades to most components automatically; a few files have hardcoded hex values that need manual updates. No backend changes, no layout changes, no new components.

**Tech Stack:** Tailwind v4 CSS variables (`@theme` block in `index.css`), React TSX components

---

## Task 1: Update CSS Color Tokens

**Files:**
- Modify: `dashboard/src/index.css`

The `@theme` block defines all Tailwind color tokens. Update them all in one pass. This cascades to fix every component using CSS variables.

**Step 1: Replace the entire `@theme` block**

```css
@theme {
  /* Backgrounds — true black foundation */
  --color-bg-primary: #000000;
  --color-bg-surface: #0A0A0A;
  --color-bg-elevated: #111111;

  /* Borders — felt, not seen */
  --color-border: #1E1E1E;
  --color-border-hover: #2A2A2A;

  /* Jade accent — also IS profit */
  --color-cyber-cyan: #00D488;
  --color-cyber-magenta: #00A86B;
  --color-cyber-green: #00D488;
  --color-accent: #00D488;
  --color-accent-dim: #003D27;

  /* Status Colors */
  --color-profit: #00D488;
  --color-profit-dim: #003D27;
  --color-loss: #FF4458;
  --color-loss-dim: #4D0010;
  --color-warning: #F59E0B;
  --color-warning-dim: #78350F;

  /* Text */
  --color-text-primary: #F5F5F5;
  --color-text-secondary: #6A6A6A;
  --color-text-muted: #3A3A3A;

  /* Typography */
  --font-sans: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  /* Glow Shadows — whisper level only */
  --shadow-glow-cyan: 0 0 0 1px rgba(0, 212, 136, 0.4);
  --shadow-glow-cyan-lg: 0 0 8px rgba(0, 212, 136, 0.12);
  --shadow-glow-magenta: 0 0 0 1px rgba(0, 212, 136, 0.2);
  --shadow-glow-green: 0 0 6px rgba(0, 212, 136, 0.12);

  /* Animations */
  --animate-pulse-slow: pulse-slow 1s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  --animate-pulse-fast: pulse-fast 0.7s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
```

**Step 2: Update scrollbar — narrower, jade on hover**

Replace the scrollbar block:
```css
::-webkit-scrollbar {
  width: 3px;
  height: 3px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #1E1E1E;
  border-radius: 2px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--color-accent);
}
```

**Step 3: Add tabular-nums utility class** (after the `.font-data` class)

```css
/* Tabular numbers for financial data */
.tabular-nums {
  font-variant-numeric: tabular-nums;
}
```

**Step 4: Verify build passes**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```
Expected: `✓ built in ~Xs` with no TS errors.

**Step 5: Commit**
```bash
git add dashboard/src/index.css
git commit -m "feat: phosphor jade — CSS token update"
```

---

## Task 2: ANALYZE Button — Solid Jade Fill

**Files:**
- Modify: `dashboard/src/components/TopBar.tsx`

The ANALYZE button should be a solid jade-filled button with black text — the single most prominent CTA on screen. EXECUTE follows suit as a ghost jade. Other buttons get squared off and neutralized.

**Step 1: Update AnalyzeExecuteButtons in TopBar.tsx**

Find this ANALYZE button className:
```
"px-3 py-1 text-xs font-semibold bg-accent/15 text-accent rounded hover:bg-accent/25 shadow-[0_0_8px_rgba(34,211,238,0.5)] disabled:opacity-50 transition-colors"
```

Replace with:
```
"px-3 py-1 text-xs font-bold bg-accent text-black rounded-sm hover:bg-accent/90 disabled:opacity-40 transition-colors"
```

Find the EXECUTE button className:
```
"px-3 py-1 text-xs font-semibold bg-profit/15 text-profit rounded hover:bg-profit/25 shadow-[0_0_8px_rgba(16,185,129,0.5)] disabled:opacity-50 transition-colors"
```

Replace with:
```
"px-3 py-1 text-xs font-semibold border border-accent/40 text-accent rounded-sm hover:bg-accent/10 disabled:opacity-40 transition-colors"
```

**Step 2: Square off UPDATE and SCAN buttons**

Both currently have `rounded` — change to `rounded-sm`. Also update their className to use neutral border style:

UPDATE button className:
```
"px-3 py-1 text-xs font-semibold border border-border text-text-secondary rounded-sm hover:border-border-hover hover:text-text-primary disabled:opacity-50 transition-colors"
```

SCAN button className (same):
```
"px-3 py-1 text-xs font-semibold border border-border text-text-secondary rounded-sm hover:border-border-hover hover:text-text-primary disabled:opacity-50 transition-colors"
```

**Step 3: Update CLOSE ALL button — outlined destructive**

Find className:
```
"text-xs px-2 py-0.5 rounded font-semibold tracking-wider bg-loss/15 text-loss hover:bg-loss/25 transition-colors disabled:opacity-50"
```

Replace with:
```
"text-xs px-2 py-0.5 rounded-sm font-semibold tracking-wider border border-loss/40 text-loss hover:bg-loss/10 transition-colors disabled:opacity-50"
```

**Step 4: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 5: Commit**
```bash
git add dashboard/src/components/TopBar.tsx
git commit -m "feat: phosphor jade — solid ANALYZE button, squared buttons"
```

---

## Task 3: Position Progress Bars → Hairline Row Border

**Files:**
- Modify: `dashboard/src/components/PositionsPanel.tsx`

Replace the chunky `ProgressBar` component with a 1px bottom border on the row itself, color-coded by progress. Also add tabular-nums to financial values.

**Step 1: Remove ProgressBar component entirely**

Delete lines 26–39 (the `ProgressBar` function):
```tsx
function ProgressBar({ pct }: { pct: number }) {
  // Progress from stop loss (0%) to take profit (100%)
  const clamped = Math.max(0, Math.min(100, pct));
  const color =
    clamped > 60 ? "bg-profit" : clamped > 30 ? "bg-accent" : "bg-loss";
  return (
    <div className="w-16 h-1.5 rounded-full bg-bg-primary overflow-hidden">
      <div
        className={`h-full rounded-full ${color}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
```

**Step 2: Update PositionRow — remove ProgressBar usage, add border + tabular-nums**

The outer div of PositionRow currently is:
```tsx
<div onClick={onClick} className="group px-3 py-2 cursor-pointer hover:bg-bg-elevated/50 hover:shadow-[0_0_12px_rgba(34,211,238,0.4)] transition-all border-b border-border/50">
```

Replace with (note: `borderBottomColor` set inline based on progress, removes glow):
```tsx
<div
  onClick={onClick}
  className="group px-3 py-2 cursor-pointer hover:bg-bg-elevated transition-colors"
  style={{ borderBottom: `1px solid ${progress > 60 ? 'rgba(0,212,136,0.5)' : progress > 30 ? '#1E1E1E' : 'rgba(255,68,88,0.4)'}` }}
>
```

Remove `<ProgressBar pct={progress} />` from the return JSX (it's the last element before closing `</div>`).

**Step 3: Add tabular-nums to financial value spans in PositionRow**

These spans need `tabular-nums` class added:
- Current price: `className="font-mono text-sm text-text-primary"` → add `tabular-nums`
- Entry price: `className="font-mono text-[10px] text-text-muted"` → add `tabular-nums`
- P&L pct: `className={`font-mono text-sm font-semibold ${pnlColor} w-16 text-right`}` → add `tabular-nums`
- Day change dollar: `className="font-mono text-xs font-semibold"` → add `tabular-nums`
- Day change pct: `className="font-mono text-[10px]"` → add `tabular-nums`

**Step 4: Update profit/loss color classes in PositionRow**

Find all `text-green-400` → replace with `text-profit`
Find all `text-red-400` → replace with `text-loss`
(These are the pnlColor and dayColor variables — update their string values)

**Step 5: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 6: Commit**
```bash
git add dashboard/src/components/PositionsPanel.tsx
git commit -m "feat: phosphor jade — hairline progress border, tabular-nums, semantic colors"
```

---

## Task 4: Update Hardcoded Hex Colors in Sparkline Components

**Files:**
- Modify: `dashboard/src/components/PositionRowSparkline.tsx`
- Modify: `dashboard/src/components/MarketTickerBanner.tsx`

Both have hardcoded `#FF6600` orange. Update to jade.

**Step 1: PositionRowSparkline.tsx — update stroke and gradient**

Find and replace:
- `stroke="#FF6600"` → `stroke="#00D488"`
- `stopColor="#FF6600"` (appears twice in linearGradient) → `stopColor="#00D488"`
- `rgba(255,102,0,0.4)` in the drop-shadow className → `rgba(0,212,136,0.3)`

After changes the polyline should be:
```tsx
<polyline
  points={points}
  fill="none"
  stroke="#00D488"
  strokeWidth="1.5"
  className="drop-shadow-[0_0_1px_rgba(0,212,136,0.3)]"
/>
```

And the gradient stops:
```tsx
<stop offset="0%" stopColor="#00D488" stopOpacity="0.15" />
<stop offset="100%" stopColor="#00D488" stopOpacity="0" />
```

**Step 2: MarketTickerBanner.tsx — check for any remaining hardcoded orange**

The file already uses `var(--color-accent)` for sparklines (updated in previous session). Verify no remaining `#FF6600` references:
```bash
grep -n "FF6600\|22D3EE\|cyan" /Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/MarketTickerBanner.tsx
```
Expected: no matches. If any found, update to `#00D488` or `var(--color-accent)`.

**Step 3: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 4: Commit**
```bash
git add dashboard/src/components/PositionRowSparkline.tsx dashboard/src/components/MarketTickerBanner.tsx
git commit -m "feat: phosphor jade — sparkline colors"
```

---

## Task 5: Update MommyAvatar and CandlestickChart

**Files:**
- Modify: `dashboard/src/components/MommyAvatar.tsx`
- Modify: `dashboard/src/components/CandlestickChart.tsx`

**Step 1: MommyAvatar.tsx — jade fill + ambient glow**

Find the outer glow div's `style`:
```tsx
background: "radial-gradient(circle, rgba(34,211,238,0.25) 0%, rgba(34,211,238,0) 70%)",
```

Replace with:
```tsx
background: "radial-gradient(circle, rgba(0,212,136,0.08) 0%, rgba(0,212,136,0) 70%)",
```

Change `animationDuration: "3s"` to `animationDuration: "4s"` — slower, more subtle.

Find the SVG background circle:
```tsx
<circle cx="24" cy="24" r="23" fill="#141920" stroke="#FF6600" strokeWidth="1.5" strokeOpacity="0.4" />
```

Replace with:
```tsx
<circle cx="24" cy="24" r="23" fill="#0A0A0A" stroke="#00D488" strokeWidth="1" strokeOpacity="0.3" />
```

Find all `fill="#FF6600"` in the `<g>` silhouette → replace with `fill="#00D488"`
Find `fillOpacity="0.85"` on the face overlay ellipse → keep as-is

**Step 2: CandlestickChart.tsx — jade crosshair**

Find `#FF6600` crosshair color reference and replace with `#00D488`.

Run:
```bash
grep -n "FF6600" /Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/CandlestickChart.tsx
```

Replace each occurrence with `#00D488`.

**Step 3: Verify build**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```

**Step 4: Commit**
```bash
git add dashboard/src/components/MommyAvatar.tsx dashboard/src/components/CandlestickChart.tsx
git commit -m "feat: phosphor jade — avatar and chart colors"
```

---

## Task 6: Final Sweep — Remove Remaining Orange/Cyan References

**Files:**
- Search all `dashboard/src/` files

**Step 1: Find any remaining hardcoded orange or cyan**
```bash
grep -rn "FF6600\|22D3EE\|rgba(34,211,238\|rgba(255,102,0" /Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/
```

**Step 2: Fix any matches found**

For each match, replace the color value:
- `#FF6600` → `#00D488`
- `#22D3EE` → `#00D488`
- `rgba(34,211,238,X)` → `rgba(0,212,136,X)`
- `rgba(255,102,0,X)` → `rgba(0,212,136,X)`

**Step 3: Final build verify**
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build
```
Expected: `✓ built` with zero TS errors and zero warnings about colors.

**Step 4: Final commit**
```bash
git add -p  # stage only changed files
git commit -m "feat: phosphor jade — final color sweep"
```

---

## Verification Checklist

After all tasks complete, visually confirm in the running dashboard (`npm run dev`):

- [ ] Background is true black, panels slightly lighter
- [ ] Accent/jade appears on: ANALYZE button (solid fill), active tab underline, sparklines, avatar border, progress hairlines on good positions
- [ ] ANALYZE button: solid jade background, black text, sharp corners
- [ ] Position row borders: red for stop-loss risk, invisible neutral in middle, jade near take-profit
- [ ] Numbers in positions panel align cleanly in columns (tabular-nums working)
- [ ] No orange visible anywhere
- [ ] Scrollbar is thin (3px) and barely visible
- [ ] Glow effects are subtle/absent at rest, crisp ring on hover
