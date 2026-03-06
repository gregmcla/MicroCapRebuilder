# Update All Button — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an "Update All" button to the Overview page's AggregateBar that refreshes live prices for all active portfolios in parallel and then re-renders the overview.

**Architecture:** Purely frontend change. When clicked, fire `api.updatePrices(pid)` in parallel for every active portfolio ID sourced from the existing `portfolioList`. Track per-request completion with a counter. On all-settled, invalidate the `["overview"]` TanStack Query to re-fetch the overview with fresh prices. No new API endpoints or backend changes needed.

**Tech Stack:** React 19, TanStack Query (useQueryClient), TypeScript — all in `dashboard/src/components/OverviewPage.tsx`

---

### Task 1: Add "Update All" button to AggregateBar

**Files:**
- Modify: `dashboard/src/components/OverviewPage.tsx`

**Step 1: Add state and handler to `OverviewPage`**

In `OverviewPage` (the default export), add two state variables and a handler just below the existing `useState(false)` for `showCreate`:

```tsx
const [updatingAll, setUpdatingAll] = useState(false);
const [updateResult, setUpdateResult] = useState<string | null>(null);
const queryClient = useQueryClient();

const handleUpdateAll = async () => {
  const ids = (portfolioList?.portfolios ?? []).map((p) => p.id);
  if (ids.length === 0) return;
  setUpdatingAll(true);
  setUpdateResult(null);
  let done = 0;
  setUpdateResult(`0 / ${ids.length}`);
  await Promise.allSettled(
    ids.map((pid) =>
      api.updatePrices(pid).then(() => {
        done += 1;
        setUpdateResult(`${done} / ${ids.length}`);
      })
    )
  );
  queryClient.invalidateQueries({ queryKey: ["overview"] });
  setUpdateResult(`${ids.length} updated`);
  setTimeout(() => setUpdateResult(null), 3000);
  setUpdatingAll(false);
};
```

**Step 2: Thread `updatingAll`, `updateResult`, and `onUpdateAll` into `AggregateBar`**

Pass the new props to the `<AggregateBar>` call inside the return statement:

```tsx
<AggregateBar
  totalEquity={totalEquity}
  totalCash={overview?.total_cash ?? 0}
  totalDayPnl={overview?.total_day_pnl ?? 0}
  totalUnrealizedPnl={overview?.total_unrealized_pnl ?? 0}
  totalAllTimePnl={overview?.total_all_time_pnl ?? 0}
  totalPositions={overview?.total_positions ?? 0}
  portfolioCount={enriched.length}
  onNewPortfolio={() => setShowCreate(true)}
  onUpdateAll={handleUpdateAll}
  updatingAll={updatingAll}
  updateResult={updateResult}
/>
```

**Step 3: Update `AggregateBar` props type and add the button**

Add three new props to the `AggregateBar` function signature:

```tsx
function AggregateBar({
  totalEquity, totalCash, totalDayPnl, totalUnrealizedPnl, totalAllTimePnl,
  totalPositions, portfolioCount, onNewPortfolio,
  onUpdateAll, updatingAll, updateResult,
}: {
  totalEquity: number; totalCash: number; totalDayPnl: number;
  totalUnrealizedPnl: number; totalAllTimePnl: number; totalPositions: number;
  portfolioCount: number;
  onNewPortfolio: () => void;
  onUpdateAll: () => void;
  updatingAll: boolean;
  updateResult: string | null;
})
```

In the `AggregateBar` return JSX, inside the `style={{ marginLeft: "auto" }}` div (right next to the "+ New Portfolio" button), add the Update All button **before** the New Portfolio button:

```tsx
<div style={{ marginLeft: "auto", display: "flex", gap: "8px", alignItems: "center" }}>
  <button
    onClick={onUpdateAll}
    disabled={updatingAll}
    style={{
      display: "inline-flex", alignItems: "center", gap: "5px",
      padding: "0 12px", height: "28px",
      background: "transparent",
      border: "1px solid var(--border-1)",
      borderRadius: "6px",
      color: updatingAll ? "var(--accent)" : "var(--text-1)",
      fontSize: "11px", fontWeight: 600,
      letterSpacing: "0.06em", textTransform: "uppercase",
      cursor: updatingAll ? "not-allowed" : "pointer",
      transition: "border-color 0.15s, color 0.15s",
      opacity: updatingAll ? 0.75 : 1,
    }}
    onMouseEnter={(e) => {
      if (!updatingAll) {
        e.currentTarget.style.borderColor = "var(--accent)";
        e.currentTarget.style.color = "var(--accent)";
      }
    }}
    onMouseLeave={(e) => {
      if (!updatingAll) {
        e.currentTarget.style.borderColor = "var(--border-1)";
        e.currentTarget.style.color = "var(--text-1)";
      }
    }}
  >
    <svg
      width="11" height="11" viewBox="0 0 12 12" fill="none"
      style={{ flexShrink: 0 }}
      className={updatingAll ? "animate-spin" : ""}
    >
      <path
        d="M10 6A4 4 0 1 1 6 2a4 4 0 0 1 2.83 1.17L10 2v4H6"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
    {updateResult ?? "Update All"}
  </button>
  <button
    onClick={onNewPortfolio}
    style={{
      display: "inline-flex", alignItems: "center", gap: "5px",
      padding: "0 12px", height: "28px",
      background: "transparent",
      border: "1px solid var(--border-1)",
      borderRadius: "6px",
      color: "var(--text-1)",
      fontSize: "11px", fontWeight: 600,
      letterSpacing: "0.06em", textTransform: "uppercase",
      cursor: "pointer", transition: "border-color 0.15s, color 0.15s",
    }}
    onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--accent)"; }}
    onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; e.currentTarget.style.color = "var(--text-1)"; }}
  >
    + New Portfolio
  </button>
</div>
```

**Step 4: Verify in browser**

1. Open http://localhost:5173 and navigate to Overview
2. Click "Update All" — button should spin and show "0 / 4", "1 / 4", etc.
3. After ~10s all portfolios should show "4 updated", then revert to "Update All"
4. Numbers on portfolio cards should reflect freshly fetched prices

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/OverviewPage.tsx
git commit -m "feat: add Update All button to overview page

Refreshes live prices for all portfolios in parallel from the
overview page, removing the need to navigate into each portfolio."
```
