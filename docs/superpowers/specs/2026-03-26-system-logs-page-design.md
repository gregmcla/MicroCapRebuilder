# System Logs Page — Design Spec

## Goal

Add a LOGS page to the GScott dashboard that shows:
1. Daily pipeline health (did scan/execute/update run, how many portfolios ok/failed)
2. A chronological event timeline (trades, restarts, failures)
3. A Claude-generated daily narrative — what happened, why trades were made, patterns Claude has noticed, insights across portfolios

Accessible via a LOGS button in the TopBar between VIX and CLOSE ALL.

---

## Architecture

### New files
- `api/routes/system.py` — `GET /api/system/logs` and `GET /api/system/narrative` endpoints
- `scripts/log_parser.py` — parse cron log files into structured dicts
- `dashboard/src/components/LogsPage.tsx` — full-page view
- `dashboard/src/hooks/useSystemLogs.ts` — TanStack Query hook

### Modified files
- `api/main.py` — register system router
- `dashboard/src/App.tsx` — add `portfolioId === "logs"` render case; extend non-portfolio guard
- `dashboard/src/components/TopBar.tsx` — add LOGS button
- `dashboard/src/lib/api.ts` — add `getSystemLogs()` and `generateNarrative()` typed methods
- `dashboard/src/lib/types.ts` — add `SystemLogsResponse`, `NarrativeResponse`, `DayLog`, `PipelineJob`, `LogEvent` TypeScript types
- `dashboard/src/hooks/usePortfolioState.ts` — extend `enabled` guard to also exclude `portfolioId === "logs"`

---

## Backend

### Log sources

| Source | Path | Content |
|--------|------|---------|
| Scan logs | `cron/logs/scan_YYYYMMDD_*.log` | Pipeline start/complete lines, per-portfolio ok/failed |
| Execute logs | `cron/logs/execute_YYYYMMDD_*.log` | Pipeline start/complete, per-portfolio ok/failed |
| Update logs | `cron/logs/update_YYYYMMDD_*.log` | Per-portfolio update lines (no count summary — see note below) |
| Watchdog log | `cron/logs/api_watchdog.log` | Timestamped restart events |
| Transactions | `data/portfolios/{id}/transactions.csv` | Trades with ISO datetime — used for execute event trade counts |

### Log file formats

**scan.sh / execute.sh** — have count summary lines:
```
[HH:MM:SS] SCAN COMPLETE -- X ok, Y failed
[HH:MM:SS] EXECUTE COMPLETE -- X ok, Y failed
```
Parser extracts ok/failed from the COMPLETE line.

**update.sh** — no count summary. COMPLETE line is simply:
```
[HH:MM:SS] UPDATE COMPLETE
```
Parser counts individual lines: `failed` = count of lines containing `  FAILED: `; `ok` = count of lines containing `Updating: ` minus `failed`. If COMPLETE line is missing entirely, status = "failed".

**api_watchdog.log** — full timestamps:
```
[YYYY-MM-DD HH:MM:SS] API down -- restarting...
[YYYY-MM-DD HH:MM:SS] API restarted OK
[YYYY-MM-DD HH:MM:SS] API restart FAILED
```
Correct path: `cron/logs/api_watchdog.log` (not `cron/api_watchdog.log` — the watchdog script writes to the `cron/logs/` subdirectory).

### `scripts/log_parser.py`

```python
def parse_scan_execute_log(log_path: Path) -> dict:
    """
    Parse a scan or execute log file (has count summary line).
    Returns: { ran_at, status, ok, failed }
    - ran_at: HH:MM string from COMPLETE line timestamp
    - status: "ok" if COMPLETE line present and failed==0, "failed" otherwise
    - ok: int, failed: int
    """

def parse_update_log(log_path: Path) -> dict:
    """
    Parse an update log file (no count summary — count individual lines).
    Returns: { ran_at, status, ok, failed }
    - ran_at: HH:MM from UPDATE COMPLETE line timestamp (or last line if missing)
    - status: "ok" if COMPLETE line present and failed==0, "failed" otherwise
    - failed: count of lines containing "  FAILED: "
    - ok: count of lines containing "Updating: " minus failed
    """

def parse_watchdog_log(log_path: Path) -> list[dict]:
    """
    Parse cron/logs/api_watchdog.log.
    Returns list of { date (YYYY-MM-DD), time (HH:MM), result ("ok"|"failed") }
    Only includes "restarted OK" and "restart FAILED" lines (not "API down" lines).
    """

def count_trades_for_date(portfolios_dir: Path, date: str) -> int:
    """
    Count BUY+SELL transactions across all portfolios for a given date (YYYY-MM-DD).
    Reads transactions.csv for each portfolio, filters rows where date column starts with date.
    Returns 0 if any CSV is unreadable (graceful degradation per portfolio).
    """

def build_day_summary(cron_logs_dir: Path, portfolios_dir: Path, date: str) -> dict:
    """
    Build full day summary for one date. Returns the day dict shape below.
    Handles missing log files gracefully (status: "missing").
    For update logs: if two files exist for a date, sort by file mtime and assign
    first (earlier mtime) = midday, second (later mtime) = close.
    If only one exists, assign to midday; close remains "missing".
    """
```

### API response shape

`GET /api/system/logs` — returns last 30 days, newest first.

```json
{
  "days": [
    {
      "date": "2026-03-26",
      "pipeline": {
        "scan":          { "status": "ok|failed|missing", "ok": 11, "failed": 0, "ran_at": "06:31" },
        "execute":       { "status": "ok|failed|missing", "ok": 11, "failed": 0, "ran_at": "09:36", "trades": 8 },
        "update_midday": { "status": "ok|failed|missing", "ok": 11, "failed": 0, "ran_at": "12:01" },
        "update_close":  { "status": "ok|failed|missing", "ok": 11, "failed": 0, "ran_at": "16:16" }
      },
      "watchdog_restarts": 1,
      "events": [
        { "time": "06:31", "type": "scan",        "detail": "11/11 portfolios ok" },
        { "time": "09:36", "type": "execute",     "detail": "8 trades across 4 portfolios" },
        { "time": "10:14", "type": "api_restart", "detail": "API restarted OK" },
        { "time": "12:01", "type": "update",      "detail": "11/11 ok" },
        { "time": "16:16", "type": "update",      "detail": "11/11 ok" }
      ]
    }
  ]
}
```

Status values:
- `"ok"` — ran, all portfolios succeeded
- `"failed"` — ran but at least one portfolio failed, or COMPLETE line missing
- `"missing"` — no log file found for this date

Trade counts for the execute event come from `count_trades_for_date()` against transactions CSVs, not from parsing the execute log body.

---

## Claude Narrative

### Endpoint

`GET /api/system/narrative?date=YYYY-MM-DD` (defaults to today)

Calls Claude (claude-opus-4-6, max_tokens=1024, timeout=60s) with a structured prompt built from:
- Today's pipeline status (did everything run, any failures)
- All trades executed today (ticker, portfolio, action, reason, price) from transactions CSVs
- Cross-portfolio P&L snapshot for today from daily_snapshots CSVs
- Recent factor learning summaries (from `FactorLearner.get_factor_summary()` for each portfolio)
- Active early warning alerts — call `get_warnings(portfolio_id=None)` once globally (returns alerts across all portfolios)

Claude is instructed to write a concise daily briefing covering:
1. **What happened** — pipeline ran cleanly / any issues, how many trades
2. **Why trades were made** — synthesized from trade rationale JSON in transactions
3. **Cross-portfolio patterns** — what themes are emerging across portfolios today
4. **What Claude is learning** — factor weight shifts, which strategies are working
5. **Anything notable** — unusual positions, regime changes, alerts firing

Response shape:
```json
{
  "date": "2026-03-26",
  "narrative": "string — 3-5 paragraphs of markdown",
  "generated_at": "2026-03-26T16:30:00",
  "cached": false
}
```

**Caching:** Narrative is cached in memory (per date) for 10 minutes. Cached responses include `"cached": true`. A "Regenerate" button on the frontend bypasses cache.

**Graceful degradation:** If Claude call fails or times out, return `{"narrative": null, "error": "narrative unavailable"}` with HTTP 200. Frontend shows a muted "Narrative unavailable" placeholder rather than an error state.

---

## Frontend

### `dashboard/src/lib/types.ts`

Add these types:
```ts
export interface PipelineJob {
  status: "ok" | "failed" | "missing";
  ok: number;
  failed: number;
  ran_at: string;       // "HH:MM"
  trades?: number;      // execute only
}

export interface LogEvent {
  time: string;         // "HH:MM"
  type: "scan" | "execute" | "update" | "api_restart" | "failed";
  detail: string;
}

export interface DayLog {
  date: string;         // "YYYY-MM-DD"
  pipeline: {
    scan: PipelineJob;
    execute: PipelineJob;
    update_midday: PipelineJob;
    update_close: PipelineJob;
  };
  watchdog_restarts: number;
  events: LogEvent[];
}

export interface SystemLogsResponse {
  days: DayLog[];
}

export interface NarrativeResponse {
  date: string;
  narrative: string | null;
  generated_at: string;
  cached: boolean;
  error?: string;
}
```

### `dashboard/src/lib/api.ts`

Add two typed methods to the `api` object:
```ts
getSystemLogs: (): Promise<SystemLogsResponse> =>
  get<SystemLogsResponse>("/api/system/logs"),

generateNarrative: (date?: string): Promise<NarrativeResponse> =>
  get<NarrativeResponse>(`/api/system/narrative${date ? `?date=${date}` : ""}`),
```

### `dashboard/src/hooks/useSystemLogs.ts`

```ts
export function useSystemLogs() {
  return useQuery({
    queryKey: ["system-logs"],
    queryFn: () => api.getSystemLogs(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useSystemNarrative(date?: string) {
  return useQuery({
    queryKey: ["system-narrative", date],
    queryFn: () => api.generateNarrative(date),
    staleTime: 10 * 60 * 1000,  // 10 min — matches server cache
    retry: false,  // don't retry Claude failures
  });
}
```

### `dashboard/src/components/LogsPage.tsx`

Three sections stacked vertically, same dark background as the rest of the dashboard.

**Header**
```
SYSTEM LOGS          last updated 4:16 PM
```

**1. Claude Narrative (top)**

Rendered as markdown. Shows a subtle pulsing skeleton while loading. "Regenerate" button in the section header invalidates the query and refetches. If `narrative` is null, shows muted placeholder text.

```
TODAY'S BRIEFING                    [Regenerate ↺]

The pipeline ran cleanly today. Eleven portfolios scanned at 6:31 AM
and executed at 9:36 AM, placing 8 trades across 4 portfolios...
```

**2. Pipeline Status Grid**

Table: DATE | SCAN 6:30 | EXECUTE 9:35 | UPDATE 12:00 | UPDATE 4:15 | WATCHDOG

Cell display:
- `✓ 11/11` green — ok, no failures
- `⚠ 9/11` amber — ok but some portfolios failed
- `✗` red — failed (COMPLETE line missing or all portfolios failed)
- `—` muted gray — missing (job didn't run)
- Watchdog: `0` muted gray, `1+` amber with bolt icon

Today's row: slightly brighter background tint.
Last 14 days shown.

**3. Event Timeline**

Grouped by date, today expanded by default, older days collapsed. Click group header to toggle.

Each event row: `HH:MM  [TYPE BADGE]  detail text`

Badge colors: SCAN=blue, EXECUTE=green, UPDATE=teal, RESTART=amber, FAILED=red

**Empty state** (no log files found):
```
No logs yet
Pipeline activity will appear here after the first cron run (6:30 AM tomorrow).
```

### App.tsx change

```tsx
// Extend non-portfolio guard to include "logs"
const isPortfolioView = portfolioId !== "overview" && portfolioId !== "logs";

// Render switch
{portfolioId === "logs" ? (
  <LogsPage />
) : portfolioId === "overview" ? (
  <OverviewPage ... />
) : (
  <PortfolioView ... />
)}
```

The `isPortfolioView` flag must be applied in **two places** in App.tsx:
1. The JSX render switch (shown above)
2. The `enabled` guards on the inline `useQuery` calls for watchlist and scanStatus — change `enabled: !isOverview && !!portfolioId` to `enabled: isPortfolioView && !!portfolioId` on both

Additionally, `usePortfolioState.ts` must extend its own `enabled` guard from `portfolioId !== "overview"` to `portfolioId !== "overview" && portfolioId !== "logs"` — otherwise it will fire a request to `GET /api/logs/state` which doesn't exist.

### TopBar.tsx change

Add LOGS button between VIX display and CLOSE ALL:
```tsx
<button onClick={() => setPortfolio("logs")}>
  LOGS
</button>
```
Use `setPortfolio` from the Zustand store (same method used by PortfolioSwitcher). Same muted style as other control buttons. Active state (slightly brighter) when `activePortfolioId === "logs"`.

---

## Error handling

- Missing `cron/logs/` directory → return empty days array, frontend shows empty state
- Malformed log line → skip silently, continue parsing
- transactions.csv unreadable for a portfolio → treat trade count as 0 for that portfolio
- Watchdog log unreadable → `watchdog_restarts: 0` for all days
- Claude narrative timeout/failure → `narrative: null`, frontend shows placeholder
- API route exception → return `{"days": []}` with HTTP 200 (page still loads)

---

## Testing

`tests/test_log_parser.py` — all use fixture files in `tests/fixtures/cron_logs/`, never real cron logs:

- `test_parse_scan_execute_log_ok` — log with COMPLETE line, no failures → status "ok", correct counts
- `test_parse_scan_execute_log_with_failures` — some FAILED lines → status "failed", correct counts
- `test_parse_scan_execute_log_truncated` — no COMPLETE line → status "failed"
- `test_parse_update_log_counts_lines` — update log (no summary line) → ok/failed derived from individual lines
- `test_parse_update_log_missing_complete` — update log without COMPLETE line → status "failed"
- `test_parse_watchdog_log` — multiple restart entries → correct date/time/result list
- `test_count_trades_for_date` — transactions CSV with mixed dates → correct count for target date
- `test_build_day_summary_missing_logs` — no log files → all statuses "missing", empty events
- `test_api_system_logs_endpoint` — integration test using `fastapi.testclient.TestClient` with fixture log files patched via monkeypatch on `CRON_LOGS_DIR`

---

## Constraints

- Read-only — this page never writes anything
- No new data generated — everything parsed from existing files
- Log files are gitignored — tests must use fixture files in `tests/fixtures/`
- Narrative uses `CLAUDE_MODEL` constant from `schema.py` (same as rest of project)
- Update midday/close disambiguation uses file mtime only (not PID — PIDs are not time-sortable)
