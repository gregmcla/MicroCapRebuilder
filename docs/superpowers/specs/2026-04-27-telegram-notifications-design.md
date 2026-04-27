# Telegram Bot Notifications — Design Spec
**Date:** 2026-04-27  
**Status:** Approved

---

## Overview

Add Telegram bot notifications to MicroCapRebuilder so Greg receives real-time updates on scans, position snapshots, and proposed trades — with inline APPROVE/REJECT buttons before any trade executes. All trades (buys, sells, stop-losses) require explicit confirmation. Nothing auto-executes.

---

## Requirements

- After scans run → send consolidated summary (watchlist changes + portfolio stats + intraday delta)
- After analyses run → send per-portfolio proposal messages with APPROVE / REJECT buttons
- After position updates run → send portfolio snapshot (intraday delta)
- All trades require explicit APPROVE tap — no auto-execution under any circumstances
- REJECT = silent skip, no follow-up interaction
- Pending approvals expire after 60 minutes (configurable)
- Works for cron-triggered and dashboard-triggered scans

---

## Architecture

### Option Selected: Long-running polling bot

A persistent `scripts/telegram_bot.py` process using `python-telegram-bot` v20 with long polling. No public URL required — works behind Tailscale/NAT. The existing `api_watchdog.sh` is extended to monitor and restart it.

---

## Components

### New Files

| File | Purpose |
|------|---------|
| `scripts/telegram_notifier.py` | Thin send-only module. No bot logic. Called by cron scripts to fire notifications. Builds messages from portfolio state and `.last_analysis.json`. |
| `scripts/telegram_bot.py` | Long-running async bot process. Handles callback queries (APPROVE/REJECT), runs execute on approval, manages 60-min expiry via asyncio background task. |
| `cron/analyze.sh` | New cron script replacing `execute.sh` in the schedule. Runs `unified_analysis.py --analyze` (dry run) per portfolio, then sends proposal messages with buttons. |
| `data/telegram/pending/{portfolio_id}.json` | Lightweight state file per pending approval. Written at analyze time, deleted on APPROVE/REJECT/expiry. |

### Modified Files

| File | Change |
|------|--------|
| `cron/scan.sh` | Add scan summary notification call after the scan loop. Collect per-portfolio results during the loop for the summary. |
| `cron/update.sh` | Add portfolio snapshot notification call after the update loop. |
| `cron/api_watchdog.sh` | Extend to also monitor `telegram_bot.py` — restart if not running. |
| `crontab` | Swap `execute.sh` → `analyze.sh` at 9:35 AM when cron is re-enabled. |

### Unchanged Files

| File | Notes |
|------|-------|
| `cron/execute.sh` | Kept but removed from cron schedule. Bot calls `unified_analysis.py --execute` directly via subprocess. |
| `scripts/unified_analysis.py` | No changes. `--analyze` (dry run) and `--execute` already exist. |

### New `.env` Variables

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_APPROVAL_TIMEOUT_MINUTES=60
```

---

## Data Flow

### Scan (6:30 AM cron — consolidated) 

```
cron/scan.sh
  for each portfolio:
    watchlist_manager.py --update --portfolio {id}
    collect: tickers_added, watchlist_size, error flag
  done
  telegram_notifier.py --scan-summary
    → fetches live prices via portfolio_state.py
    → computes intraday delta vs prev_close for each portfolio
    → sends ONE consolidated message (no buttons)
```

### Scan (dashboard SCAN button — single portfolio)

```
api/routes/discovery.py  POST /api/{portfolio_id}/scan
  watchlist_manager.py --update --portfolio {id}
  telegram_notifier.py --scan-summary --portfolio {id}
    → fetches live prices for that portfolio only
    → sends a single-portfolio version of the scan message
```

### Analyze (9:35 AM cron — new)

```
cron/analyze.sh
  for each portfolio:
    unified_analysis.py --analyze --portfolio {id}
      → writes data/portfolios/{id}/.last_analysis.json
    telegram_notifier.py --proposals --portfolio {id}
      → reads .last_analysis.json
      → fetches live prices for intraday delta
      → sends per-portfolio message with [APPROVE] [REJECT] buttons
      → writes data/telegram/pending/{id}.json
  done
  (no execution happens in this script)
```

`data/telegram/pending/{portfolio_id}.json` schema:
```json
{
  "portfolio_id": "max",
  "message_id": 12345,
  "chat_id": "...",
  "analyzed_at": "2026-04-28T09:35:00",
  "expires_at": "2026-04-28T10:35:00"
}
```

### Bot Process (always running)

```
scripts/telegram_bot.py  ← long polling

  on APPROVE callback:
    read data/telegram/pending/{id}.json
    check not expired
    edit message → "⏳ Executing..."
    subprocess: unified_analysis.py --execute --portfolio {id}  ← fresh prices
    edit message → "✅ Executed — N trades at HH:MM"
    delete pending file

  on REJECT callback:
    edit message → "❌ Rejected"
    delete pending file

  background task (runs every 60s):
    for each pending/{id}.json:
      if expires_at < now:
        edit message → "⏱ Expired — no trades fired"
        delete pending file

  on startup:
    scan data/telegram/pending/ for unexpired files → re-attach buttons
    clean up expired files immediately
```

### Position Update (noon + 4:15 PM cron)

```
cron/update.sh
  for each portfolio:
    update_positions.py --portfolio {id}
    factor_learning.py --portfolio {id}
  done
  telegram_notifier.py --update-snapshot
    → fetches live prices via portfolio_state.py
    → computes intraday delta vs prev_close
    → sends ONE consolidated snapshot message (no buttons)
```

### Watchdog Extension

```
cron/api_watchdog.sh (runs every 15 min)
  existing: check API health, restart uvicorn if down
  new:
    if ! pgrep -f "telegram_bot.py" > /dev/null; then
      nohup python3 scripts/telegram_bot.py >> cron/logs/telegram_bot.log 2>&1 &
    fi
```

---

## Message Formats

### Scan Summary

```
🔍 Scan Complete — Mon Apr 28, 10:47 AM

MAX
  Watchlist: 47  +3 new  NVDA · AMD · INTC
  8 positions · $1.24M equity · total +12.3% (+$136K)
  Today: +0.82% (+$10,100) vs yesterday's close

GOV-INFRA
  Watchlist: 38  +1 new  GD
  5 positions · $284K equity · total +4.1% (+$11K)
  Today: −0.3% (−$850) vs yesterday's close

ASYMMETRIC-CATALYST
  Watchlist: 52  ↔ no change
  3 positions · $98K equity · total −2.1% (−$2.1K)
  Today: +0.6% (+$590) vs yesterday's close

CASH-COWS
  Watchlist: 41  +2 new  MMM · CVX
  6 positions · $412K equity · total +7.8% (+$31K)
  Today: +0.4% (+$1,650) vs yesterday's close

MAX2
  Watchlist: 44  +1 new  META
  4 positions · $5.1M equity · total −1.2% (−$62K)
  Today: −0.8% (−$41K) vs yesterday's close

5 portfolios · 2m 14s
```

Failed portfolios show: `⚠️ scan failed` in place of stats.

### Analysis Proposal (per portfolio, only sent if proposals exist)

```
📊 MAX · BULL · AI mode
Analyzed 9:35 AM · expires 10:35 AM

BUYS (2)
  NVDA   $2,500   score 78   breakout momentum
  AMD    $1,800   score 71   RS vs peers

SELLS (1)
  INTC   100%   stop-loss   held 14d · −8.2% (−$1,240)

Cash after: $142,500
Today: +0.82% (+$10,100) vs yesterday's close
```
Buttons: `[ ✅ APPROVE ]   [ ❌ REJECT ]`

**Terminal states (buttons removed, message edited):**
- APPROVE tap → `📊 MAX · ⏳ Executing...` → `📊 MAX · ✅ Executed — 3 trades at 10:07 AM`
- REJECT tap → `📊 MAX · ❌ Rejected`
- Expiry → `📊 MAX · ⏱ Expired — no trades fired`
- Execute failed → `📊 MAX · ❌ Execute failed — check logs`

### Position Update Snapshot

```
📈 Portfolio Update — Mon Apr 28, 4:15 PM

MAX
  8 positions · $1.24M equity · total +12.3% (+$136K)
  Today: +1.2% (+$14,800) vs yesterday's close

GOV-INFRA
  5 positions · $284K equity · total +4.1% (+$11K)
  Today: −0.1% (−$284) vs yesterday's close

ASYMMETRIC-CATALYST
  3 positions · $98K equity · total −2.1% (−$2.1K)
  Today: +0.6% (+$590) vs yesterday's close

CASH-COWS
  6 positions · $412K equity · total +7.8% (+$31K)
  Today: +0.4% (+$1,650) vs yesterday's close

MAX2
  4 positions · $5.1M equity · total −1.2% (−$62K)
  Today: −0.8% (−$41K) vs yesterday's close

5 portfolios · 4:15 PM update
```

---

## Notification Inventory

| Trigger | Message | Buttons |
|---------|---------|---------|
| `scan.sh` or dashboard SCAN | Watchlist changes + portfolio stats + intraday delta | None |
| `analyze.sh` (9:35 AM) | Per-portfolio proposals (only if proposals exist) | APPROVE / REJECT |
| `update.sh` (noon + 4:15 PM) | Portfolio snapshot + intraday delta | None |
| Bot APPROVE tap → execute succeeds | Edit proposal → "✅ Executed" | None |
| Bot APPROVE tap → execute fails | Edit proposal → "❌ Execute failed" | None |
| Bot REJECT tap | Edit proposal → "❌ Rejected" | None |
| 60-min expiry | Edit proposal → "⏱ Expired" | None |

---

## Error Handling

| Scenario | Behavior |
|----------|---------|
| Bot process crashes | Watchdog restarts within 15 min. On startup, bot re-attaches to unexpired pending files. |
| One portfolio fails during scan/analyze/update | Loop continues. Failed portfolio shows `⚠️ scan failed` in notification. |
| Execute fails after APPROVE | Message edited to `❌ Execute failed — check logs`. Pending file deleted. No retry. |
| Telegram API unreachable | `telegram_notifier.py` retries 3× with exponential backoff. Failure logged, cron script continues. |
| APPROVE after expiry | Pending file already gone. Bot no-ops, edits message to `⏱ Already expired`. |
| Double APPROVE tap | Pending file deleted before subprocess starts. Second tap finds no file → no-op. |

---

## Execute Behavior on APPROVE

When APPROVE is tapped, the bot calls `unified_analysis.py --execute` with **fresh prices** — it does not replay the 9:35 AM decisions verbatim. "APPROVE" means "I agree with this strategy direction, go execute now." Prices and final allocations are computed at tap time.

---

## Setup Prerequisites

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) → get `TELEGRAM_BOT_TOKEN`
2. Get your `TELEGRAM_CHAT_ID` (message the bot, call `getUpdates`)
3. Add both to `.env`
4. Install dependency: `pip install python-telegram-bot==20.*`
5. Bot process auto-starts via watchdog once `.env` vars are present

---

## Dependencies

- `python-telegram-bot==20.*` (async, long polling, inline keyboards)
- No new infrastructure required — works behind Tailscale/NAT

---

## Gitignore

Add to `.gitignore`:
```
data/telegram/
```
