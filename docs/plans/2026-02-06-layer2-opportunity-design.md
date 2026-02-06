# Layer 2: Opportunity Management - Design

## Context

**What we've built (Phase 1-2):**
- ✅ Layer 1 Risk Management working - dynamic stops, position re-evaluation, deterioration detection
- ✅ Enhanced structures (SellProposal, StopLevels, DeteriorationSignal)
- ✅ Configuration system in place (enhanced_trading.layer1)

**What's missing:**
- Basic buy candidates still use fixed 10% position sizing
- No conviction scoring - treats all candidates equally
- No pattern detection - misses breakouts, momentum surges
- No volatility-adjusted sizing - treats volatile stocks same as stable ones

**Goal:** Add intelligent opportunity management that sizes positions by conviction and detects high-probability entry patterns.

---

## Design

### Architecture

Layer 2 processes **after** Layer 1 and **before** portfolio composition:

```
Input: PortfolioState + Layer 1 output (sells)
  ↓
Layer 2: Opportunity Management
  1. Score watchlist candidates (existing 6-factor model)
  2. Calculate conviction (base score + multipliers)
  3. Detect entry patterns (breakout, momentum surge, mean reversion)
  4. Size positions by conviction + volatility
  5. Generate BuyProposal objects
  ↓
Output: {buy_proposals: List[BuyProposal], conviction_scores: Dict}
```

### Conviction Scoring System

**Base Conviction = Composite Score × Multiplier**

**Multipliers (0.75x - 2.0x):**
- **Exceptional (90+):** 2.0x → final conviction up to 100
- **Strong (80-89):** 1.5x → final conviction ~120-135
- **Good (70-79):** 1.0x → final conviction 70-79
- **Acceptable (60-69):** 0.75x → final conviction ~45-52

**Conviction Adjustments** (additive):
- Multiple confirmations (momentum + volume + RS all >70): +0.3
- Breakout pattern detected: +0.2
- Fresh high / momentum surge: +0.2
- Regime alignment (stock style matches market): +0.2
- Low volatility (ATR <2%): +0.1

**Example:**
- Stock scores 75 (GOOD) → base 1.0x
- Has breakout pattern (+0.2) + regime aligned (+0.2) → 1.4x multiplier
- Final conviction: 75 × 1.4 = 105 (capped at 100)

### Pattern Detection

**Patterns to detect:**
1. **Breakout** - 20-day high + volume surge (>75 volume score)
2. **Momentum Surge** - Multi-timeframe alignment (5/20/60 day all positive)
3. **Mean Reversion** - Oversold bounce (RSI <35 → >45)

**Pattern confidence:** 70-90 based on signal strength

### Position Sizing

**Conviction-based sizing:**
- High conviction (80+): 12% of portfolio
- Medium conviction (70-79): 8% of portfolio
- Low conviction (60-69): 5% of portfolio

**Volatility adjustment:**
- High ATR (>4%): Reduce size by 25%
- Very high ATR (>6%): Reduce size by 50%

**Regime multiplier** (existing):
- BULL: 100% of base size
- SIDEWAYS: 80%
- BEAR: 0% (no new buys)

**Example calculation:**
- Conviction 85 (high) → 12% base size
- ATR 3.2% (moderate) → no adjustment
- BULL market → 100% multiplier
- Final size: 12% of $50k portfolio = $6,000 position

---

## Implementation Plan

### Files to Create/Modify

1. **Create:** `scripts/opportunity_layer.py`
   - OpportunityLayer class
   - Conviction scoring logic
   - Pattern detection
   - Position sizing

2. **Modify:** `scripts/enhanced_structures.py`
   - Add BuyProposal dataclass
   - Add ConvictionScore dataclass
   - Add PatternSignal dataclass

3. **Modify:** `scripts/unified_analysis.py`
   - Integrate Layer 2 after Layer 1
   - Replace basic buy candidate loop with Layer 2 output
   - Pass conviction scores to AI review

4. **Test:** Manual testing with current portfolio

---

## Success Criteria

✅ **Conviction scores calculated** - Higher scores for multi-factor confirmation
✅ **Patterns detected** - Identifies breakouts and momentum surges
✅ **Dynamic position sizing** - High conviction gets 12%, low gets 5%
✅ **Volatility adjustment** - Reduces size for high-ATR stocks
✅ **Integration working** - Layer 2 output feeds into AI review and execution

---

## Next Steps After Phase 3

**Phase 4: Layer 3 - Portfolio Composition**
- Sector concentration limits (max 40% per sector)
- Correlation analysis (max 3 correlated positions)
- Top-3 concentration limit (max 45% in top 3 positions)
- Rebalancing triggers

**Phase 5: Layer 4 - Execution Sequencer**
- Priority scoring for all actions
- Strategic ordering (emergency sells → high conviction buys)
- Cash tracking during execution

**Phase 6: Learning System**
- Pattern success tracking
- Conviction calibration (adjust multipliers based on outcomes)
- Auto-tuning based on performance
