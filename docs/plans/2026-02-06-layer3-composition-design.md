# Layer 3: Portfolio Composition - Design

## Context

**What we've built (Phases 1-3):**
- ✅ Layer 1 Risk Management - Dynamic stops, position re-evaluation, deterioration detection
- ✅ Layer 2 Opportunity Management - Conviction scoring, pattern detection, dynamic sizing
- ✅ Enhanced structures for all layers

**What's missing:**
- No sector diversification limits - could end up 80% in one sector
- No correlation analysis - could have 5 highly correlated tech stocks
- No concentration limits - top 3 positions could be 70% of portfolio
- No rebalancing logic - positions drift from targets over time

**Goal:** Add portfolio composition intelligence that enforces diversification limits, detects correlation, and triggers rebalancing when needed.

---

## Design

### Architecture

Layer 3 processes **after** Layer 2 and **before** execution sequencing:

```
Input: PortfolioState + Layer 1 output (sells) + Layer 2 output (buys)
  ↓
Layer 3: Portfolio Composition
  1. Check sector concentration (current + proposed)
  2. Analyze correlation between positions
  3. Check top-3 concentration
  4. Block buys that violate limits
  5. Generate rebalancing sells if needed
  ↓
Output: {
  filtered_buys: List[BuyProposal],  # Removed violating buys
  rebalance_sells: List[SellProposal],  # Rebalancing actions
  composition_warnings: List[str]  # Human-readable warnings
}
```

### Sector Concentration Limits

**Configuration:**
- `sector_limit_pct`: 40% (max portfolio value in one sector)

**Logic:**
1. Group current positions by sector
2. Calculate sector % for each
3. For each proposed buy:
   - Determine ticker's sector (need sector mapping)
   - Calculate new sector % if buy executes
   - Block if new sector % > limit

**Example:**
- Current: 35% Technology
- Proposed buy: $2k TECH stock
- After buy: 39% Technology ✅ Allow
- If it would be 42%: ❌ Block

### Correlation Analysis

**Configuration:**
- `correlation_threshold`: 0.7 (Pearson correlation)
- `max_correlated_positions`: 3 (max tickers with correlation >0.7)
- `correlation_lookback_days`: 60 (historical window)

**Logic:**
1. Fetch 60-day price history for all positions
2. Calculate pairwise correlations
3. Find clusters of correlated stocks (correlation >0.7)
4. For proposed buys:
   - Calculate correlation with existing positions
   - Block if it would create 4th correlated position in cluster

**Example:**
- Existing: AAPL, MSFT, GOOGL (all 0.8+ correlation)
- Proposed buy: META (0.85 correlation with cluster)
- Result: ❌ Block (would be 4th correlated tech stock)

### Top-3 Concentration Limit

**Configuration:**
- `top3_limit_pct`: 45% (max portfolio value in top 3 positions)

**Logic:**
1. Sort positions by market value
2. Calculate top-3 percentage
3. For proposed buys:
   - Simulate new portfolio with buy
   - Check if new top-3 > 45%
   - Block if exceeds limit

**Example:**
- Current top-3: $5k, $4k, $3k = $12k / $25k portfolio = 48%
- Already over limit
- Proposed buy: $3k position
- Result: ❌ Block (top-3 already violated)

### Rebalancing Logic

**Configuration:**
- `enable_rebalancing`: true
- `rebalance_trigger_pct`: 20% (trigger when position drifts 20% from target)
- `rebalance_target_pct`: 15% (target weight after rebalancing)

**Logic:**
1. Identify oversized positions (>18% of portfolio = 15% + 20% drift)
2. Calculate trim amount to bring back to 15%
3. Generate partial sell proposals
4. Only rebalance when top-3 > 45% or sector > 40%

**Example:**
- Position: $9k / $50k portfolio = 18%
- Target: 15% = $7.5k
- Over by: $1.5k
- Action: Sell $1.5k worth of shares (trim to target)

---

## Data Requirements

### Sector Mapping

Need ticker → sector mapping. Options:
1. **Static JSON file** - Manual curation
2. **yfinance metadata** - Fetch from yfinance `ticker.info['sector']`
3. **Hybrid** - Static file with yfinance fallback

Recommend: Static JSON for speed + yfinance fallback

```json
{
  "AAPL": "Technology",
  "WDFC": "Consumer Defensive",
  "LBRT": "Energy"
}
```

### Correlation Data

Need 60-day price history for correlation calculation:
- Use existing yfinance integration
- Cache correlation matrix (refresh daily)
- Store in `data/correlations.json`

---

## Implementation Plan

### Files to Create/Modify

1. **Create:** `scripts/composition_layer.py`
   - CompositionLayer class
   - Sector concentration checks
   - Correlation analysis
   - Top-3 concentration checks
   - Rebalancing logic

2. **Create:** `data/sector_mapping.json`
   - Static ticker → sector mapping

3. **Modify:** `scripts/enhanced_structures.py`
   - Add CompositionViolation dataclass
   - Add RebalanceTrigger dataclass

4. **Modify:** `scripts/unified_analysis.py`
   - Integrate Layer 3 after Layer 2
   - Filter buys based on composition limits
   - Add rebalancing sells to proposed actions

5. **Test:** Manual testing with current portfolio

---

## Success Criteria

✅ **Sector limits enforced** - Blocks buys that exceed 40% in one sector
✅ **Correlation detected** - Identifies correlated positions (>0.7)
✅ **Correlation limits enforced** - Blocks 4th correlated position
✅ **Top-3 concentration enforced** - Blocks when top-3 > 45%
✅ **Rebalancing triggered** - Generates trim sells for oversized positions
✅ **Integration working** - Layer 3 output feeds into execution sequencer

---

## Example Scenario

**Current Portfolio:**
- AAPL: $8k (16%, Technology)
- MSFT: $7k (14%, Technology)
- GOOGL: $6k (12%, Technology)
- WMT: $5k (10%, Consumer Defensive)
- Total: $50k, Top-3: 42%, Technology: 42%

**Proposed Buys from Layer 2:**
1. META: $4k (Technology, 0.85 correlation with AAPL/MSFT/GOOGL)
2. HD: $3k (Consumer Cyclical)
3. NVDA: $4k (Technology)

**Layer 3 Evaluation:**

1. **META:**
   - Sector check: Tech would be 50% ❌ BLOCKED (exceeds 40% limit)
   - Correlation check: Would be 4th correlated position ❌ BLOCKED

2. **HD:**
   - Sector check: Consumer Cyclical would be 6% ✅ OK
   - Correlation check: Low correlation ✅ OK
   - Top-3 check: New top-3 would be 42% ✅ OK (under 45%)
   - **Result:** ✅ APPROVED

3. **NVDA:**
   - Sector check: Tech would be 50% ❌ BLOCKED
   - **Result:** ❌ BLOCKED

**Rebalancing:**
- No positions >18% (rebalance trigger)
- No rebalancing needed

**Final Output:**
- Approved buys: [HD]
- Blocked buys: [META, NVDA]
- Warnings: ["Technology sector at 42% (limit 40%)", "3 correlated tech positions detected"]

---

## Next Steps After Phase 4

**Phase 5: Layer 4 - Execution Sequencer**
- Priority scoring for all actions
- Strategic ordering (emergency sells → rebalancing → high conviction buys)
- Cash tracking during execution
- Collision detection (don't buy and sell same ticker)

**Phase 6: Learning System Integration**
- Track which composition rules prevent losses
- Calibrate thresholds based on outcomes
- Learn sector rotation patterns
