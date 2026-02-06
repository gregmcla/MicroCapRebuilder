# Session Notes: Unified Analysis Architecture

**Date**: 2026-01-31
**Branch**: claude/add-claude-documentation-SJTa1

## What Was Built

### Unified Analysis System
- Created `scripts/unified_analysis.py` - Single source of truth for trading decisions
- Created `scripts/ai_review.py` - AI review layer that can APPROVE/MODIFY/VETO trades
- Modified `run_daily.sh` to use unified mode when API keys available

### Dashboard Improvements
- Moved action buttons (ANALYZE, EXECUTE, DISCOVER, UPDATE, REFRESH) to top
- Fixed HTML rendering issues (single-line string concatenation)
- Fixed Mommy chat auto-triggering (wrapped in form)
- Added DISCOVER output display
- Fixed cash limit enforcement in position sizing

## Key Decisions

1. **AI Review Batching**: Large numbers of actions (>10) are batched to avoid overwhelming the AI
2. **Fallback Strategy**: When AI fails, approves based on quant score with adjusted confidence
3. **Cash Tracking**: Remaining cash is tracked as buys are proposed to prevent over-allocation

## Known Issues

1. **AI JSON Parsing**: Still occasionally fails with malformed JSON from LLMs
   - Workaround: Auto-approves on error with lower confidence
   - Future: Consider simpler prompt or structured outputs

2. **JBT Ticker**: Shows "possibly delisted" - should be removed from watchlist

## Files Changed

- `scripts/ai_review.py` (new)
- `scripts/unified_analysis.py` (new)
- `scripts/webapp.py` (major updates)
- `run_daily.sh` (unified mode)
- `CLAUDE.md` (documentation)

## Next Steps

1. Test EXECUTE flow end-to-end in paper mode
2. Debug AI review JSON parsing or disable temporarily
3. Remove stale tickers from watchlist
4. Add sector exposure tracking
