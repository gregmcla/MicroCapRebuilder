# Layer 4: Execution Sequencer - Design

## Context

**What we've built (Phases 1-4):**
- ✅ Layer 1 Risk Management - Dynamic stops, deterioration detection
- ✅ Layer 2 Opportunity Management - Conviction scoring, pattern detection
- ✅ Layer 3 Portfolio Composition - Sector limits, top-3 concentration, rebalancing
- ✅ Enhanced structures for all layers

**What's missing:**
- No strategic execution ordering - actions executed in arbitrary order
- No priority scoring - all actions treated equally
- No cash tracking - might approve buys without checking cumulative cash impact
- No collision detection - could propose buy AND sell for same ticker

**Goal:** Add execution sequencing intelligence that prioritizes actions strategically, tracks cash availability, and prevents execution conflicts.

---

## Design

### Architecture

Layer 4 processes **last** after all other layers, taking their outputs and creating a final sequenced execution plan:

```
Input: All proposed actions from Layers 1-3
  ↓
Layer 4: Execution Sequencer
  1. Assign priority scores to all actions
  2. Sort by priority (high → low)
  3. Detect collisions (buy+sell same ticker)
  4. Track cash availability sequentially
  5. Skip actions that would overdraw cash
  ↓
Output: ExecutionPlan {
  sequenced_actions: List[PrioritizedAction],  # Final ordered list
  skipped_actions: List[Dict],  # Actions skipped due to cash/collisions
  execution_notes: List[str]  # Human-readable explanations
}
```

### Priority Scoring System

**Priority Levels (0-100):**

| Action Type | Priority | Reason |
|-------------|----------|--------|
| Emergency sell (urgency 90+) | 100 | Immediate risk - exit now |
| Deteriorating sell (urgency 70-89) | 85-95 | High risk - exit soon |
| Stop loss trigger | 80 | Defined risk limit hit |
| Take profit trigger | 75 | Lock in gains |
| Rebalancing sell | 50 | Reduce concentration |
| High conviction buy (80+) | 85 | Strong opportunity |
| Medium conviction buy (70-79) | 70 | Good opportunity |
| Low conviction buy (60-69) | 55 | Acceptable opportunity |

**Tie-breaking:** When priorities equal, use:
1. Urgency score (for sells)
2. Conviction score (for buys)
3. Ticker alphabetically

### Cash Tracking

**Sequential cash simulation:**
1. Start with current cash balance
2. Process actions in priority order:
   - **SELL:** Add proceeds to available cash
   - **BUY:** Subtract cost from available cash
3. Skip buys if insufficient cash
4. Log all skips with reason

**Example:**
```
Initial cash: $5,000

1. SELL AAPL (emergency) → Cash: $10,000 ✓
2. SELL MSFT (rebalancing) → Cash: $13,000 ✓
3. BUY NVDA ($8,000, high conviction) → Cash: $5,000 ✓
4. BUY META ($7,000, medium conviction) → Cash: -$2,000 ❌ SKIP (insufficient)
```

### Collision Detection

**Collision types:**
1. **Buy + Sell same ticker** - VETO the buy, keep the sell
2. **Multiple buys same ticker** - Keep highest conviction, skip others
3. **Multiple sells same ticker** - Combine into single sell

**Resolution logic:**
- Sells always win over buys (exit has priority)
- Higher conviction wins for competing buys
- Combine partial sells into full position exit

**Example:**
```
Proposed:
- SELL AAPL (100 shares, emergency)
- BUY AAPL (50 shares, high conviction)

Resolution:
- Keep: SELL AAPL (emergency exit takes priority)
- Skip: BUY AAPL (collision with sell)
- Note: "Skipped BUY AAPL - collision with emergency sell"
```

---

## Implementation Plan

### Files to Create/Modify

1. **Create:** `scripts/execution_sequencer.py`
   - ExecutionSequencer class
   - Priority scoring logic
   - Collision detection
   - Cash tracking simulation
   - Sequenced execution plan generation

2. **Modify:** `scripts/enhanced_structures.py`
   - Add PrioritizedAction dataclass
   - Add ExecutionPlan dataclass (already exists, verify fields)

3. **Modify:** `scripts/unified_analysis.py`
   - Run Layer 4 after Layer 3
   - Replace proposed_actions list with sequenced ExecutionPlan
   - Display execution plan with priorities

4. **Test:** Manual testing with mixed buy/sell proposals

---

## Success Criteria

✅ **Priority scores assigned** - Each action gets 0-100 priority
✅ **Actions sorted** - Sequenced high priority → low priority
✅ **Collisions detected** - Buy+sell same ticker handled correctly
✅ **Cash tracked** - Buys skipped when insufficient cash
✅ **Integration working** - Layer 4 output becomes final execution plan

---

## Example Full Scenario

**Current Portfolio:**
- Cash: $10,000
- Positions: AAPL ($15k), MSFT ($12k), GOOGL ($8k)

**Proposed Actions from Layers 1-3:**

| Action | Ticker | Details | Source |
|--------|--------|---------|--------|
| SELL | AAPL | 100 shares, deteriorating (urgency 85) | Layer 1 |
| SELL | MSFT | 50 shares, rebalancing | Layer 3 |
| BUY | NVDA | $8k, conviction 90 (EXCEPTIONAL) | Layer 2 |
| BUY | META | $6k, conviction 75 (GOOD) | Layer 2 |
| BUY | AAPL | $5k, conviction 80 (STRONG) | Layer 2 |

**Layer 4 Processing:**

1. **Assign Priorities:**
   - SELL AAPL: 95 (deteriorating, urgency 85)
   - SELL MSFT: 50 (rebalancing)
   - BUY NVDA: 85 (high conviction)
   - BUY META: 70 (medium conviction)
   - BUY AAPL: 85 (high conviction)

2. **Detect Collisions:**
   - ⚠️ Collision: BUY AAPL + SELL AAPL
   - Resolution: Keep SELL (higher priority), skip BUY

3. **Sort by Priority:**
   1. SELL AAPL (95)
   2. BUY NVDA (85)
   3. BUY META (70)
   4. SELL MSFT (50)

4. **Cash Tracking:**
   - Start: $10,000
   - SELL AAPL (+$15,000) → $25,000 ✓
   - BUY NVDA (-$8,000) → $17,000 ✓
   - BUY META (-$6,000) → $11,000 ✓
   - SELL MSFT (+$6,000) → $17,000 ✓

**Final Execution Plan:**
```
Sequenced Actions (4):
1. [95] SELL AAPL - Deteriorating position (urgency 85)
2. [85] BUY NVDA - Exceptional conviction, breakout pattern
3. [70] BUY META - Good conviction
4. [50] SELL MSFT - Rebalancing (position at 18%)

Skipped Actions (1):
- BUY AAPL - Collision with SELL AAPL (sell takes priority)

Initial Cash: $10,000
Final Cash: $17,000 (estimated)
```

---

## Next Steps After Phase 5

**Phase 6: Learning System Integration**
- Track execution outcomes
- Learn which priorities lead to best results
- Auto-tune priority weights based on performance
- Pattern learning for conviction calibration

**Phase 7: Dashboard Integration**
- Show execution sequence in UI
- Priority badges for each action
- Cash flow visualization
- One-click approve/execute

**Phase 8: Testing & Validation**
- Parallel paper trading comparison (layers vs no layers)
- Performance metrics (Sharpe, max drawdown, win rate)
- Backtest on historical data
