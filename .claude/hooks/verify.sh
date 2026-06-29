#!/usr/bin/env bash
# Claude Code Stop hook — MicroCapRebuilder verification gate (Boris-style).
#
# Fires when Claude finishes a turn. If the turn touched any Python file, it runs
# the regression-critical integration suite. On failure it BLOCKS turn-end
# (exit 2) and feeds the failures back to Claude, so Claude keeps fixing until
# the suite is green. On a chat / read-only / docs-only turn it does nothing.
#
# Switch scope: change PYTEST_ARGS below (e.g. to the full suite).
# Interrupt anytime with Esc if Claude gets stuck on an unfixable failure.
set -uo pipefail

PYTEST_ARGS="tests/integration/ -q"   # full suite: "tests/ scripts/tests/ -q"

# Repo root = two levels up from this script (.claude/hooks/verify.sh).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)" || exit 0
cd "$ROOT" || exit 0   # can't locate repo → never block

# Read hook input (JSON on stdin). Captured but currently only used by the
# optional infinite-loop guard below.
INPUT="$(cat)"

# This gate intentionally keeps blocking until tests pass. To make it back off
# after a single retry instead, uncomment:
# if printf '%s' "$INPUT" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
#   exit 0
# fi

# Only run when Python actually changed (tracked edits OR new untracked files).
changed_py=0
git diff --name-only HEAD 2>/dev/null | grep -q '\.py$' && changed_py=1
git ls-files --others --exclude-standard 2>/dev/null | grep -q '\.py$' && changed_py=1
[ "$changed_py" -eq 1 ] || exit 0   # no Python touched → allow stop

# Pick interpreter: prefer the project venv.
if [ -x .venv/bin/python ]; then PY=".venv/bin/python"; else PY="python3"; fi

OUT="$("$PY" -m pytest $PYTEST_ARGS 2>&1)"
CODE=$?

# Pytest itself missing = infra problem, not a code regression → don't block.
if printf '%s' "$OUT" | grep -q 'No module named pytest'; then
  echo "verify.sh: pytest not available in $PY — skipping gate." >&2
  exit 0
fi

[ "$CODE" -eq 0 ] && exit 0   # green → allow stop

# Red → block turn-end and tell Claude what to fix.
{
  echo "Stop blocked: the integration suite is RED. Fix it before finishing."
  echo "Command: $PY -m pytest $PYTEST_ARGS"
  echo "----- last lines of pytest output -----"
  printf '%s\n' "$OUT" | tail -30
} >&2
exit 2
