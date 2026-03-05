# Scan All Portfolios Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Scan All" button to the overview aggregate bar that sequentially scans every active portfolio's watchlist and shows live per-portfolio feedback on the button and each portfolio card.

**Architecture:** Frontend-orchestrated — no new API endpoints. `handleScanAll` in `OverviewPage.tsx` iterates active portfolio IDs sequentially, calling existing `api.scan()` + polling `api.scanStatus()` for each. Per-portfolio scan results are tracked in a `scanAllState` object and passed down to `AggregateBar` and `PortfolioCard` as props.

**Tech Stack:** React 19, TanStack Query (`useQueryClient`), TypeScript. No backend changes except lowering the scan timeout constant.

---

## Task 1: Lower backend scan timeout

**Files:**
- Modify: `api/routes/discovery.py:17`

**Step 1: Change the constant**

In `api/routes/discovery.py`, change line 17:
```python
# Before
SCAN_TIMEOUT_SECONDS = 900  # 15 minutes

# After
SCAN_TIMEOUT_SECONDS = 480  # 8 minutes — covers cold-cache scans with margin
```

**Step 2: Verify**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
grep "SCAN_TIMEOUT_SECONDS" api/routes/discovery.py
```
Expected output: `SCAN_TIMEOUT_SECONDS = 480`

**Step 3: Commit**

```bash
git add api/routes/discovery.py
git commit -m "Lower scan timeout 900→480s (8 min covers cold-cache with margin)"
```

---

## Task 2: Add scan-all state and orchestration logic to OverviewPage

**Files:**
- Modify: `dashboard/src/components/OverviewPage.tsx`

This task adds the data model and `handleScanAll` function. No UI changes yet.

**Step 1: Add the `ScanAllState` interface and state**

At the top of `OverviewPage.tsx`, after the existing imports, add:

```typescript
import type { ScanJobStatus } from "../lib/types";

interface ScanAllPortfolioResult {
  status: "running" | "complete" | "error";
  added: number;
  active: number;
  error: string | null;
}

interface ScanAllState {
  running: boolean;
  currentId: string | null;
  results: Record<string, ScanAllPortfolioResult>;
}
```

Inside `OverviewPage()`, alongside the existing `updatingAll` state, add:

```typescript
const [scanAll, setScanAll] = useState<ScanAllState>({
  running: false,
  currentId: null,
  results: {},
});
const scanCancelledRef = useRef(false);
```

**Step 2: Add `handleScanAll`**

Add this function inside `OverviewPage()`, after `handleUpdateAll`:

```typescript
const handleScanAll = async () => {
  const ids = (portfolioList?.portfolios ?? [])
    .filter((p) => p.active)
    .map((p) => p.id);
  if (ids.length === 0) return;

  scanCancelledRef.current = false;
  setScanAll({ running: true, currentId: ids[0], results: {} });

  for (const id of ids) {
    if (scanCancelledRef.current) break;

    // Mark this portfolio as running
    setScanAll((prev) => ({
      ...prev,
      currentId: id,
      results: {
        ...prev.results,
        [id]: { status: "running", added: 0, active: 0, error: null },
      },
    }));

    try {
      // Fire the scan
      await api.scan(id);

      // Poll until complete or timeout (9 min frontend guard)
      const FRONTEND_TIMEOUT_MS = 9 * 60 * 1000;
      const POLL_INTERVAL_MS = 3000;
      const deadline = Date.now() + FRONTEND_TIMEOUT_MS;

      let finalStatus: ScanJobStatus = { status: "running" };
      while (Date.now() < deadline && !scanCancelledRef.current) {
        await new Promise((res) => setTimeout(res, POLL_INTERVAL_MS));
        finalStatus = await api.scanStatus(id);
        if (finalStatus.status !== "running") break;
      }

      if (finalStatus.status === "complete" && finalStatus.result) {
        setScanAll((prev) => ({
          ...prev,
          results: {
            ...prev.results,
            [id]: {
              status: "complete",
              added: finalStatus.result!.added,
              active: finalStatus.result!.total_active,
              error: null,
            },
          },
        }));
        // Refresh overview data so card stats update live
        queryClient.invalidateQueries({ queryKey: ["overview"] });
      } else {
        // Timeout or backend error — non-fatal, continue chain
        setScanAll((prev) => ({
          ...prev,
          results: {
            ...prev.results,
            [id]: {
              status: "error",
              added: 0,
              active: 0,
              error: finalStatus.error ?? "Scan timed out",
            },
          },
        }));
      }
    } catch (err) {
      setScanAll((prev) => ({
        ...prev,
        results: {
          ...prev.results,
          [id]: {
            status: "error",
            added: 0,
            active: 0,
            error: err instanceof Error ? err.message : "Unknown error",
          },
        },
      }));
    }
  }

  // Chain complete — compute summary
  setScanAll((prev) => ({ ...prev, running: false, currentId: null }));
  // Clear results after 5s so badges don't linger forever
  setTimeout(() => {
    if (!scanCancelledRef.current) {
      setScanAll({ running: false, currentId: null, results: {} });
    }
  }, 5000);
};
```

**Step 3: Add cleanup on unmount**

Add a `useEffect` after the `handleScanAll` definition:

```typescript
useEffect(() => {
  return () => { scanCancelledRef.current = true; };
}, []);
```

**Step 4: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npx tsc --noEmit
```
Expected: no errors.

**Step 5: Commit**

```bash
git add dashboard/src/components/OverviewPage.tsx
git commit -m "Add scan-all state and sequential orchestration logic to OverviewPage"
```

---

## Task 3: Add "Scan All" button to AggregateBar

**Files:**
- Modify: `dashboard/src/components/OverviewPage.tsx` (AggregateBar component + its call site)

**Step 1: Add props to AggregateBar**

Find the `AggregateBar` function signature (around line 147) and add three new props:

```typescript
function AggregateBar({
  totalEquity, totalCash, totalDayPnl, totalUnrealizedPnl, totalAllTimePnl,
  totalPositions, portfolioCount, onNewPortfolio,
  onUpdateAll, updatingAll, updateResult,
  // ── new ──
  onScanAll, scanAllRunning, scanAllLabel,
}: {
  // ... existing props ...
  onScanAll: () => void;
  scanAllRunning: boolean;
  scanAllLabel: string | null; // null = show default "Scan All"
}) {
```

**Step 2: Add the Scan All button**

Inside `AggregateBar`, after the existing "Update All" button and before "+ New Portfolio", add:

```tsx
<button
  onClick={onScanAll}
  disabled={scanAllRunning}
  style={{
    display: "inline-flex", alignItems: "center", gap: "5px",
    padding: "0 12px", height: "28px",
    background: "transparent",
    border: "1px solid var(--border-1)",
    borderRadius: "6px",
    color: scanAllRunning ? "var(--accent)" : "var(--text-1)",
    fontSize: "11px", fontWeight: 600,
    letterSpacing: "0.06em", textTransform: "uppercase",
    cursor: scanAllRunning ? "not-allowed" : "pointer",
    transition: "border-color 0.15s, color 0.15s",
    opacity: scanAllRunning ? 0.75 : 1,
    maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
  }}
  onMouseEnter={(e) => {
    if (!scanAllRunning) {
      e.currentTarget.style.borderColor = "var(--accent)";
      e.currentTarget.style.color = "var(--accent)";
    }
  }}
  onMouseLeave={(e) => {
    if (!scanAllRunning) {
      e.currentTarget.style.borderColor = "var(--border-1)";
      e.currentTarget.style.color = "var(--text-1)";
    }
  }}
>
  {/* Radar dot */}
  <span
    style={{
      width: "6px", height: "6px", borderRadius: "50%",
      background: "currentColor", opacity: scanAllRunning ? 1 : 0.6, flexShrink: 0,
      animation: scanAllRunning ? "pulse 1s ease-in-out infinite" : "none",
    }}
  />
  {scanAllLabel ?? "Scan All"}
</button>
```

**Step 3: Compute the inline button label and pass all props**

In the `OverviewPage` return block, before the `<AggregateBar>` JSX, derive the label:

```typescript
const portfolioNames = new Map(
  (portfolioList?.portfolios ?? []).map((p) => [p.id, p.name])
);
const scanAllLabel = useMemo(() => {
  if (!scanAll.running && Object.keys(scanAll.results).length > 0) {
    // Done — show summary
    const totalAdded = Object.values(scanAll.results).reduce(
      (sum, r) => sum + r.added, 0
    );
    const n = Object.keys(scanAll.results).length;
    return `+${totalAdded} added · ${n} scanned`;
  }
  if (scanAll.running && scanAll.currentId) {
    const name = portfolioNames.get(scanAll.currentId) ?? scanAll.currentId;
    return `Scanning ${name}…`;
  }
  return null; // idle — show default "Scan All"
}, [scanAll, portfolioNames]);
```

Note: `portfolioNames` must be derived before this (it already is via `names` in the existing code — just reuse that map or rename consistently).

Then update the `<AggregateBar>` call:

```tsx
<AggregateBar
  {/* ...existing props... */}
  onScanAll={handleScanAll}
  scanAllRunning={scanAll.running}
  scanAllLabel={scanAllLabel}
/>
```

**Step 4: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npx tsc --noEmit
```
Expected: no errors.

**Step 5: Commit**

```bash
git add dashboard/src/components/OverviewPage.tsx
git commit -m "Add Scan All button to overview aggregate bar with inline progress label"
```

---

## Task 4: Add per-portfolio scan badge to PortfolioCard

**Files:**
- Modify: `dashboard/src/components/OverviewPage.tsx` (PortfolioCard component + its call site)

**Step 1: Add `scanResult` prop to PortfolioCard**

Find the `PortfolioCard` function signature and add:

```typescript
function PortfolioCard({
  summary, totalEquity,
  scanResult,  // ── new ──
}: {
  summary: PortfolioSummary;
  totalEquity: number;
  scanResult?: ScanAllPortfolioResult;
}) {
```

**Step 2: Add the scan badge**

Inside `PortfolioCard`, after the closing `</div>` of the existing bottom stats section (the last `!summary.error &&` block), add:

```tsx
{/* Scan badge — only shown when there is scan-all state for this card */}
{scanResult && (
  <div
    style={{
      padding: "5px 14px 7px",
      borderTop: "1px solid var(--border-0)",
      display: "flex", alignItems: "center", gap: "6px",
      fontSize: "10px", color: "var(--text-1)",
    }}
  >
    {/* Status dot */}
    <span
      style={{
        width: "6px", height: "6px", borderRadius: "50%", flexShrink: 0,
        background:
          scanResult.status === "complete" ? "var(--green)"
          : scanResult.status === "error"    ? "var(--red)"
          : "var(--amber)",
        animation: scanResult.status === "running"
          ? "pulse 1s ease-in-out infinite"
          : "none",
      }}
    />
    {scanResult.status === "running" && (
      <span style={{ color: "var(--amber)" }}>Scanning…</span>
    )}
    {scanResult.status === "complete" && (
      <span style={{ color: "var(--green)" }}>
        +{scanResult.added} added · {scanResult.active} active
      </span>
    )}
    {scanResult.status === "error" && (
      <span style={{ color: "var(--red)" }}>
        Scan error{scanResult.error ? ` — ${scanResult.error.slice(0, 40)}` : ""}
      </span>
    )}
  </div>
)}
```

**Step 3: Pass `scanResult` at the call site**

In `OverviewPage`, find the `<PortfolioCard>` usage (inside `enriched.map(...)`) and add the prop:

```tsx
<PortfolioCard
  key={s.id}       {/* already present on the parent div */}
  summary={s}
  totalEquity={totalEquity}
  scanResult={scanAll.results[s.id]}
/>
```

**Step 4: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npx tsc --noEmit
```
Expected: no errors.

**Step 5: Manual smoke test**

With both API and dev server running (`./run_dashboard.sh`):
1. Navigate to the overview page
2. Click "Scan All"
3. Verify: button shows "Scanning [portfolio name]…" as it progresses
4. Verify: each portfolio card shows pulsing amber "Scanning…" while running, then green "+N added · M active" when done
5. Verify: any errored portfolio shows red "Scan error" badge
6. Verify: after 5s idle the badges clear and button resets to "Scan All"
7. Verify: the portfolio cards refresh their data (watchlist counts, etc.) after each scan completes

**Step 6: Commit**

```bash
git add dashboard/src/components/OverviewPage.tsx
git commit -m "Add per-portfolio scan badge to PortfolioCard for scan-all feedback"
```

---

## Task 5: Push to GitHub

```bash
git push origin main
```

---

## Summary of changes

| File | What changed |
|------|-------------|
| `api/routes/discovery.py` | `SCAN_TIMEOUT_SECONDS` 900 → 480 |
| `dashboard/src/components/OverviewPage.tsx` | `ScanAllState` interface, `scanAll` state, `handleScanAll`, `scanAllLabel` memo, `AggregateBar` Scan All button, `PortfolioCard` scan badge |

Total: 2 files, ~120 lines added.
