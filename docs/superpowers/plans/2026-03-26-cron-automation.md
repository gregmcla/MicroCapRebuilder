# Cron Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up four local cron jobs that automate the daily GScott trading pipeline — pre-market scan, market-open execute, position updates, and API watchdog.

**Architecture:** Four standalone bash scripts in `cron/` wrap existing Python pipeline scripts (`watchlist_manager.py`, `unified_analysis.py`, `update_positions.py`). Each script logs to a dated file in `cron/logs/`. A crontab installs five schedule entries (4 trading jobs + API watchdog). No new Python code is needed — this is pure shell orchestration over the existing system.

**Tech Stack:** bash, macOS cron (local ET timezone), existing Python pipeline scripts, `curl` for watchdog health check.

---

## Context for the implementer

This is MicroCapRebuilder (GScott), a paper trading system with 8+ active portfolios. The project root is `/Users/gregmclaughlin/MicroCapRebuilder`. Python lives in `.venv/`. Environment variables (ANTHROPIC_API_KEY, PUBLIC_API_KEY) live in `.env`. All Python scripts must be run from the project root with the venv activated.

Key scripts being called by the cron jobs:
- `python3 scripts/list_portfolios.py` — prints active portfolio IDs one per line
- `python3 scripts/watchlist_manager.py --update --portfolio <ID>` — scan/discovery
- `python3 scripts/unified_analysis.py --execute --portfolio <ID>` — AI analyze + execute
- `python3 scripts/update_positions.py --portfolio <ID>` — update prices + EOD snapshot
- `python3 scripts/factor_learning.py --portfolio <ID>` — update factor weights (non-fatal if < 5 trades)

The API (uvicorn on port 8001) must be started with `DISABLE_SOCIAL=true` — this is already baked into `run_dashboard.sh` but the watchdog must set it explicitly too.

macOS cron uses **local system time** (currently EDT, UTC-4). All cron schedule times in this plan are in Eastern Time and will remain correct through DST transitions automatically.

---

## Schedule

| Time (ET) | Days | Job |
|---|---|---|
| 6:30 AM | Mon–Fri | `scan.sh` — pre-market watchlist refresh |
| 9:35 AM | Mon–Fri | `execute.sh` — AI analyze + execute all portfolios |
| 12:00 PM | Mon–Fri | `update.sh` — mid-day P&L refresh |
| 4:15 PM | Mon–Fri | `update.sh` — post-close snapshot + factor learning |
| every 15 min | all days | `api_watchdog.sh` — restart API if down |
| midnight | Sunday | log cleanup — delete logs older than 30 days |

---

## Task 1: cron/ scripts + tests

**Files:**
- Create: `cron/scan.sh`
- Create: `cron/execute.sh`
- Create: `cron/update.sh`
- Create: `cron/api_watchdog.sh`
- Create: `tests/test_cron_scripts.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cron_scripts.py`:

```python
"""Tests for cron/ shell scripts — syntax, permissions, and watchdog behavior."""
import subprocess
import os
import stat
from pathlib import Path

CRON_DIR = Path(__file__).parent.parent / "cron"
SCRIPTS = ["scan.sh", "execute.sh", "update.sh", "api_watchdog.sh"]


def test_cron_dir_exists():
    """cron/ directory must exist."""
    assert CRON_DIR.is_dir(), f"cron/ directory not found at {CRON_DIR}"


def test_all_scripts_exist():
    """All four scripts must be present."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        assert path.exists(), f"Missing script: {path}"


def test_all_scripts_executable():
    """All scripts must have the executable bit set."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        if path.exists():
            mode = os.stat(path).st_mode
            assert mode & stat.S_IXUSR, f"{name} is not executable (chmod +x missing)"


def test_all_scripts_pass_syntax_check():
    """All scripts must pass bash -n (syntax validation)."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        if path.exists():
            result = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"{name} failed bash syntax check:\n{result.stderr}"
            )


def test_all_scripts_have_shebang():
    """All scripts must start with #!/usr/bin/env bash."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        if path.exists():
            first_line = path.read_text().splitlines()[0]
            assert first_line == "#!/usr/bin/env bash", (
                f"{name} missing shebang, got: {first_line!r}"
            )


def test_watchdog_exits_cleanly_when_api_healthy():
    """
    Watchdog must exit 0 without modifying logs when API is up.
    Assumes the API is running (integration test — skip if port 8001 not listening).
    """
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    api_up = sock.connect_ex(("localhost", 8001)) == 0
    sock.close()

    if not api_up:
        import pytest
        pytest.skip("API not running on port 8001 — skipping watchdog live test")

    watchdog = CRON_DIR / "api_watchdog.sh"
    if not watchdog.exists():
        import pytest
        pytest.skip("api_watchdog.sh not yet created")

    result = subprocess.run(
        ["bash", str(watchdog)],
        capture_output=True,
        text=True,
        cwd=str(CRON_DIR.parent),
    )
    assert result.returncode == 0, (
        f"Watchdog exited non-zero when API was healthy:\n{result.stderr}"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pytest tests/test_cron_scripts.py -v
```

Expected: `FAILED` on `test_cron_dir_exists` and `test_all_scripts_exist` — cron/ doesn't exist yet.

- [ ] **Step 3: Create cron/scan.sh**

```bash
mkdir -p cron
```

Create `cron/scan.sh` with this exact content:

```bash
#!/usr/bin/env bash
# Pre-market discovery scan — refreshes all active portfolio watchlists
# Scheduled: 6:30 AM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/scan_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=========================================="
log "PRE-MARKET SCAN START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")
COUNT=0
FAILED=0

for PORTFOLIO in $PORTFOLIOS; do
    log "Scanning: $PORTFOLIO"
    if python3 scripts/watchlist_manager.py --update --portfolio "$PORTFOLIO" >> "$LOG" 2>&1; then
        log "  ok: $PORTFOLIO"
        COUNT=$((COUNT + 1))
    else
        log "  FAILED: $PORTFOLIO (continuing)"
        FAILED=$((FAILED + 1))
    fi
done

log "=========================================="
log "SCAN COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="
```

- [ ] **Step 4: Create cron/execute.sh**

Create `cron/execute.sh` with this exact content:

```bash
#!/usr/bin/env bash
# Market-open analyze + execute — AI allocation for all active portfolios
# Scheduled: 9:35 AM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/execute_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Belt-and-suspenders: skip weekends (cron 1-5 already handles this)
DOW=$(date +%u)
if [ "$DOW" -ge 6 ]; then
    log "Weekend detected -- skipping"
    exit 0
fi

log "=========================================="
log "MARKET-OPEN EXECUTE START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")
COUNT=0
FAILED=0

for PORTFOLIO in $PORTFOLIOS; do
    log "Executing: $PORTFOLIO"
    if python3 scripts/unified_analysis.py --execute --portfolio "$PORTFOLIO" >> "$LOG" 2>&1; then
        log "  ok: $PORTFOLIO"
        COUNT=$((COUNT + 1))
    else
        log "  FAILED: $PORTFOLIO (continuing)"
        FAILED=$((FAILED + 1))
    fi
done

log "=========================================="
log "EXECUTE COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="
```

- [ ] **Step 5: Create cron/update.sh**

Create `cron/update.sh` with this exact content:

```bash
#!/usr/bin/env bash
# Position update + factor learning — runs at noon and post-close
# Scheduled: 12:00 PM ET and 4:15 PM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/update_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=========================================="
log "POSITION UPDATE START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")

for PORTFOLIO in $PORTFOLIOS; do
    log "Updating: $PORTFOLIO"
    python3 scripts/update_positions.py --portfolio "$PORTFOLIO" >> "$LOG" 2>&1 \
        || log "  FAILED: update_positions for $PORTFOLIO"
    # factor_learning is non-fatal (needs >= 5 completed trades)
    python3 scripts/factor_learning.py --portfolio "$PORTFOLIO" >> "$LOG" 2>&1 \
        || true
done

log "=========================================="
log "UPDATE COMPLETE"
log "=========================================="
```

- [ ] **Step 6: Create cron/api_watchdog.sh**

Create `cron/api_watchdog.sh` with this exact content:

```bash
#!/usr/bin/env bash
# API health check — restarts uvicorn if the health endpoint stops responding
# Scheduled: every 15 minutes via crontab

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$DIR/cron/logs/api_watchdog.log"
mkdir -p "$(dirname "$LOG")"

HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null || echo "")

if [ "$HEALTH" = '{"status":"ok"}' ]; then
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] API down -- restarting..." >> "$LOG"

cd "$DIR"
source .venv/bin/activate

if [ -f .env ]; then
    set -a; source .env; set +a
fi

pkill -f "uvicorn api.main:app" 2>/dev/null || true
sleep 1

DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 \
    >> "$LOG" 2>&1 &

sleep 8
HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null || echo "")
if [ "$HEALTH" = '{"status":"ok"}' ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restarted OK" >> "$LOG"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restart FAILED" >> "$LOG"
fi
```

- [ ] **Step 7: Make all scripts executable**

```bash
chmod +x cron/scan.sh cron/execute.sh cron/update.sh cron/api_watchdog.sh
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_cron_scripts.py -v
```

Expected output:
```
tests/test_cron_scripts.py::test_cron_dir_exists PASSED
tests/test_cron_scripts.py::test_all_scripts_exist PASSED
tests/test_cron_scripts.py::test_all_scripts_executable PASSED
tests/test_cron_scripts.py::test_all_scripts_pass_syntax_check PASSED
tests/test_cron_scripts.py::test_all_scripts_have_shebang PASSED
tests/test_cron_scripts.py::test_watchdog_exits_cleanly_when_api_healthy PASSED
```

- [ ] **Step 9: Commit**

```bash
git add cron/scan.sh cron/execute.sh cron/update.sh cron/api_watchdog.sh tests/test_cron_scripts.py
git commit -m "feat: add cron automation scripts for trading pipeline"
```

---

## Task 2: .gitignore + crontab

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add cron/logs/ to .gitignore**

Open `.gitignore` and add this block after the existing `data/` entries (or at the end):

```
# Cron logs
cron/logs/
```

Verify by running:
```bash
git check-ignore -v cron/logs/scan_20260326.log
```
Expected: `.gitignore:XX:cron/logs/  cron/logs/scan_20260326.log`

- [ ] **Step 2: Install the crontab**

⚠️ **This command appends to the existing crontab and is NOT idempotent.** Run it exactly once. First verify the GScott block is not already present:
```bash
crontab -l 2>/dev/null | grep -c "GScott"
```
Expected: `0`. If you see `1` or more, the entries are already installed — skip the install command.

Back up the existing crontab first:
```bash
crontab -l > /tmp/crontab_backup.txt 2>/dev/null || true
```

Then install the new crontab:

```bash
(crontab -l 2>/dev/null; cat << 'EOF'

# ── GScott Trading System ──────────────────────────────────────────
MAILTO=""

# Pre-market scan (6:30 AM ET, Mon-Fri)
30 6 * * 1-5 /Users/gregmclaughlin/MicroCapRebuilder/cron/scan.sh

# Market-open execute (9:35 AM ET, Mon-Fri)
35 9 * * 1-5 /Users/gregmclaughlin/MicroCapRebuilder/cron/execute.sh

# Mid-day position update (12:00 PM ET, Mon-Fri)
0 12 * * 1-5 /Users/gregmclaughlin/MicroCapRebuilder/cron/update.sh

# Post-close position update + factor learning (4:15 PM ET, Mon-Fri)
15 16 * * 1-5 /Users/gregmclaughlin/MicroCapRebuilder/cron/update.sh

# API watchdog (every 15 min, all days)
*/15 * * * * /Users/gregmclaughlin/MicroCapRebuilder/cron/api_watchdog.sh

# Log cleanup: delete logs older than 30 days (Sunday midnight)
0 0 * * 0 find /Users/gregmclaughlin/MicroCapRebuilder/cron/logs -name "*.log" -mtime +30 -delete
# ───────────────────────────────────────────────────────────────────
EOF
) | crontab -
```

- [ ] **Step 3: Verify crontab was installed**

```bash
crontab -l
```

Expected: Shows the GScott block with all 6 entries.

- [ ] **Step 4: Smoke-test the watchdog right now**

```bash
bash cron/api_watchdog.sh
echo "Exit code: $?"
```

Expected: exits 0 silently (API is running). No output to terminal, no new lines in `cron/logs/api_watchdog.log`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "feat: install crontab for GScott trading automation (scan/execute/update/watchdog)"
```

- [ ] **Step 6: Push**

```bash
git push
```

---

## Verification checklist

After completing both tasks, confirm:

- [ ] `crontab -l` shows all 6 GScott entries
- [ ] `bash -n cron/scan.sh && bash -n cron/execute.sh && bash -n cron/update.sh && bash -n cron/api_watchdog.sh` — all exit 0
- [ ] `pytest tests/test_cron_scripts.py -v` — all 6 tests pass
- [ ] `bash cron/api_watchdog.sh` — exits cleanly when API is up
- [ ] `cat cron/logs/api_watchdog.log` — no entries (watchdog found API healthy, wrote nothing)
- [ ] `git check-ignore -v cron/logs/` — confirms logs are gitignored
