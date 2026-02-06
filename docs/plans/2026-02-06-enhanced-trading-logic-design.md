# Enhanced Trading Logic Design

**Date:** 2026-02-06
**Status:** Design approved, ready for implementation

## Overview

Transform MicroCapRebuilder from a basic mechanical trading system into an intelligent, adaptive portfolio manager. The current system makes reasonable individual trade decisions but lacks strategic thinking about execution order, position re-evaluation, portfolio composition, and fast adaptation. This design introduces a 4-layer architecture that addresses all these gaps.

## Current System Weaknesses

### Buy Decisions
- Scores stocks in isolation (no awareness of existing portfolio composition)
- All positions same size (10% risk regardless of conviction or volatility)
- No pattern recognition (misses breakouts, reversals, momentum shifts)
- Only considers candidates not currently held

### Sell Decisions
- ONLY sells when stop loss (8%) or take profit (20%) triggers
- Never re-evaluates positions between entry and exit
- Example: Stock score drops 85 → 45, momentum reverses, but system holds indefinitely until stop hits
- Fixed stop percentages don't adapt to volatility or regime

### Hold Decisions
- Essentially non-existent - system just waits passively for stop/target triggers
- No trailing stops, no dynamic adjustments
- Winners and losers treated identically after entry

### Execution
- No strategic sequencing (buys might execute before sells, wasting available cash)
- No priority ranking (treats urgent risk reduction same as opportunistic buys)
- Simply executes `approved + modified` actions in arbitrary order

### Learning
- Requires 20+ completed trades before adjusting factor weights
- No pattern memory (doesn't learn "high conviction + breakout = 75% win rate")
- No conviction calibration (doesn't track if conviction scores are accurate)
- Slow to adapt to changing market conditions

## Proposed Solution: 4-Layer Architecture

Transform the unified analysis pipeline into a sophisticated decision system with four sequential layers:

```
Portfolio State + Market Data
         ↓
    Layer 1: Risk Management
    - Re-evaluates ALL positions
    - Detects deterioration (score drops, pattern breaks)
    - Manages dynamic stops (trailing, volatility-adjusted)
    - Outputs: Emergency sells, stop adjustments
         ↓
    Layer 2: Opportunity Management
    - Scores candidates with conviction levels
    - Pattern detection (breakouts, momentum)
    - Conviction-based position sizing (5-15%)
    - Outputs: Buy proposals with conviction scores
         ↓
    Layer 3: Portfolio Composition
    - Analyzes correlations, sector concentration
    - Enforces diversification limits
    - Modifies/vetoes trades for balance
    - Outputs: Portfolio-aware action adjustments
         ↓
    Layer 4: Execution Sequencer
    - Prioritizes actions by urgency/opportunity
    - Sequences: Emergency sells → Rebalancing → High-conviction buys
    - Validates constraints (cash, position limits)
    - Outputs: Optimally ordered trade list
         ↓
    AI Review (existing) → Execution (existing)
```

Each layer is independent and toggle-able. You can tune aggressiveness per layer (e.g., conservative risk management + aggressive opportunity seeking).

## Layer 1: Risk Management

**Purpose:** Continuously monitor positions for problems and manage downside protection dynamically.

### Position Re-Evaluation
Every analysis run, re-score ALL current positions using the same 6-factor model:
- Score dropped 20+ points → Flag as "DETERIORATING"
- Score dropped 30+ points → Propose "QUALITY_DEGRADATION" sell
- Still above 60 → Keep but monitor closer
- Compare current score to entry score for trend analysis

### Dynamic Stop Loss Management
Replace fixed 8% stops with adaptive logic:
- **Volatility-adjusted stops:** High volatility stocks get wider stops (e.g., 10% vs 6%)
  - Calculate ATR% (Average True Range / Price)
  - If ATR% > 5%, use 10% stop; if ATR% < 2%, use 6% stop
- **Trailing stops:** Once position up 10%+, raise stop to entry + 5%, then trail at -8% from peak
- **Regime-aware stops:** Bear market = tighter stops (6%), Bull = normal (8%), Sideways = 7%

### Pattern-Based Exit Signals
Detect technical deterioration:
- **Momentum reversal:** 20-day momentum flips negative while holding
- **Volume distribution:** Volume spike on down days (institutional selling)
- **Support break:** Breaking below 20-day moving average with high volume
- **RSI divergence:** Price making new highs but RSI declining

### Urgency Scoring
Each sell proposal gets urgency score (0-100):
- **90-100:** Stop loss hit, immediate exit required
- **70-89:** Pattern break + score deterioration (multiple signals)
- **50-69:** Score dropped significantly but not critical
- **Below 50:** Monitoring only, no action yet

**Output:** List of proposed sells with urgency scores, updated stop/target levels for all positions.

## Layer 2: Opportunity Management

**Purpose:** Identify best buying opportunities and size positions by conviction level.

### Enhanced Conviction Scoring
Beyond basic 6-factor composite score (0-100), calculate **conviction multiplier** (0.5x to 2.0x):

**Base multiplier from score:**
- 90+ score → 2.0x (exceptional opportunity)
- 80-89 → 1.5x (strong opportunity)
- 70-79 → 1.0x (good opportunity)
- 60-69 → 0.75x (acceptable opportunity)

**Adjustment factors:**
- **Multiple confirmations:** Momentum + volume + relative strength all strong → +0.3x
- **Pattern detection:** Breakout above resistance → +0.2x, Fresh 20-day high → +0.2x
- **Regime alignment:** Bull market + high momentum stock → +0.2x
- **Low volatility:** ATR% < 2% (less risky) → +0.1x

**Final conviction = composite_score × conviction_multiplier** (capped at 100)

### Conviction-Based Position Sizing
Replace fixed 10% risk per trade with dynamic sizing:
- **High conviction (80+):** 12-15% of portfolio
- **Medium conviction (70-79):** 8-10% of portfolio
- **Low conviction (60-69):** 5-7% of portfolio
- Still respects max 15% per position limit and regime multipliers

### Entry Pattern Detection
Flag special entry opportunities:
- **Breakout:** Price breaks above 20-day high on volume > 1.5x average
- **Pullback entry:** Strong stock (score 75+) dips to 20-day MA, bounces on volume
- **Momentum surge:** RSI crosses above 50 + volume spike + price acceleration
- **Regime catalyst:** Bull regime begins + stock has high momentum factor

### Opportunity Scoring
Each buy proposal gets opportunity score (0-100):
- **90-100:** High conviction + pattern + regime aligned
- **70-89:** High conviction, no special pattern
- **50-69:** Medium conviction
- **Below 50:** Low conviction, only if slots available

**Output:** Buy proposals with conviction scores, position sizes, opportunity scores, pattern flags.

## Layer 3: Portfolio Composition

**Purpose:** Ensure portfolio stays balanced and diversified, preventing dangerous concentrations.

### Correlation Analysis
Calculate pairwise correlations between all positions (60-day price history):
- **High correlation (>0.7):** Flag as "clustered risk"
- **Sector grouping:** Auto-detect industry (energy, tech, finance, healthcare, etc.)
- **Warning threshold:** If 3+ positions all correlated >0.7 → risk cluster alert

### Concentration Limits
Enforce diversification rules:
- **Single sector max:** 40% of portfolio (prevents "all energy" or "all tech" disasters)
- **Correlation cluster max:** No more than 3 highly-correlated positions
- **Top 3 positions max:** 45% of portfolio (prevents over-concentration in winners)
- **Single position max:** 15% (existing limit, enforced here too)

### Trade Modification Logic
When Layer 2 proposes a trade that violates limits:
- **Veto:** If sector already at 40%, reject the buy entirely
- **Reduce size:** If adding would push sector to 38%, reduce position size to keep at 35%
- **Suggest swap:** "Sector at limit - consider selling [weakest position in sector] first"

### Rebalancing Proposals
Detect imbalances in current portfolio:
- **Position overgrowth:** Position grew to 20% due to gains → propose partial trim to 15%
- **Sector drift:** Sector drifted to 45% → propose trimming weakest position in sector
- **Correlation cluster:** Positions became highly correlated → flag for monitoring
- **Winner concentration:** Top 3 positions > 50% → consider taking some profits

**Output:** Modified action list (vetoes, size adjustments, rebalancing sells), portfolio health metrics.

## Layer 4: Execution Sequencer

**Purpose:** Strategically order all trades to optimize cash usage, risk reduction, and opportunity capture.

### Strategic Prioritization
All approved actions receive priority score (0-100):

**Sells (higher priority = execute first):**
- **Priority 100:** Emergency exits (stop loss hit)
- **Priority 70-90:** Deteriorating positions (based on Layer 1 urgency score)
- **Priority 60-70:** Quality degradation (score dropped 30+)
- **Priority 50-60:** Rebalancing trims (portfolio optimization)

**Buys (higher priority = more important opportunity):**
- **Priority 80-90:** High conviction + pattern detected
- **Priority 70-80:** High conviction (80+), no special pattern
- **Priority 60-70:** Medium conviction (70-79)
- **Priority 40-50:** Low conviction (60-69)

### Execution Sequence
Sort all actions by priority (highest first):

1. **Emergency sells** (Priority 100) - Reduce risk immediately, free up cash
2. **Deteriorating position exits** (Priority 70-90) - Risk reduction
3. **High-conviction buys** (Priority 80-90) - Capture best opportunities while cash available
4. **Rebalancing sells** (Priority 50-60) - Portfolio optimization
5. **Medium/low conviction buys** (Priority 40-70) - Fill remaining slots if cash available

### Dynamic Cash Tracking
As each trade executes in sequence:
- **Track remaining cash** after each sell (add proceeds)
- **Check available cash** before each buy
- **Skip if insufficient cash** for a buy, try next lower-priority buy
- **Real-time position count** - stop at max 15 positions
- **Log skipped trades** with reasons for transparency

### Execution Report
Output shows:
- Proposed sequence with reasoning ("Selling TICKER first to free $X for high-conviction buy")
- Cash flow at each step (Running cash: $X after each trade)
- Skipped trades with reasons ("Skipped TICKER buy - insufficient cash after higher-priority trades")
- Final portfolio snapshot after sequence completes

**Output:** Optimally sequenced trade list ready for AI review and execution.

## Integration with Existing System

### Current Flow
```python
unified_analysis.py:
  1. Check stop/target triggers → proposed_sells
  2. Score watchlist → proposed_buys
  3. AI review → approved actions
  4. Execute in arbitrary order
```

### Enhanced Flow
```python
unified_analysis.py (refactored):
  1. Load portfolio state
  2. Layer 1 (risk_layer.py) → risk_actions, updated_stops
  3. Layer 2 (opportunity_layer.py) → opportunity_actions
  4. Layer 3 (portfolio_layer.py) → modified_actions, vetoes
  5. Layer 4 (execution_sequencer.py) → sequenced_actions
  6. AI review (EXISTING ai_review.py) → approved actions
  7. Execute in optimal order (EXISTING execute_approved_actions)
```

### New Modules

**`scripts/risk_layer.py`**
- `re_evaluate_positions(state)` → List[SellProposal]
- `calculate_dynamic_stops(state)` → Dict[ticker, StopLevels]
- `detect_deterioration(position, current_score)` → DeteriorationSignal

**`scripts/opportunity_layer.py`**
- `calculate_conviction(stock_score, patterns, regime)` → ConvictionScore
- `detect_entry_patterns(ticker)` → List[PatternSignal]
- `size_position_by_conviction(conviction, volatility, regime)` → PositionSize

**`scripts/portfolio_layer.py`**
- `analyze_correlations(positions)` → CorrelationMatrix
- `check_concentration_limits(positions, proposed_actions)` → LimitViolations
- `apply_portfolio_constraints(actions)` → ModifiedActions

**`scripts/execution_sequencer.py`**
- `prioritize_actions(actions)` → PrioritizedActions
- `sequence_trades(actions, cash, constraints)` → SequencedTrades
- `generate_execution_plan(sequenced_trades)` → ExecutionPlan

### Enhanced Existing Modules

**`scripts/stock_scorer.py`**
- Add `detect_breakout(ticker)` → bool
- Add `detect_momentum_surge(ticker)` → bool
- Add `calculate_pattern_score(ticker)` → float

**`scripts/unified_analysis.py`**
- Orchestrate layer calls
- Keep existing AI review integration
- Pass sequenced actions to AI review

**`scripts/ai_review.py`**
- Unchanged - still reviews final action list
- Now sees additional context (conviction scores, patterns, portfolio health)

### Configuration

Add to `data/config.json`:

```json
{
  "enhanced_trading": {
    "enable_layers": true,
    "layer1": {
      "enable_reeval": true,
      "aggressiveness": "moderate",
      "min_score_drop_for_alert": 20,
      "min_score_drop_for_sell": 30,
      "enable_trailing_stops": true,
      "enable_volatility_stops": true
    },
    "layer2": {
      "enable_conviction": true,
      "min_conviction": 60,
      "enable_pattern_detection": true,
      "conviction_multiplier_max": 2.0
    },
    "layer3": {
      "enable_composition": true,
      "sector_limit_pct": 40,
      "correlation_threshold": 0.7,
      "max_correlated_positions": 3,
      "top3_limit_pct": 45
    },
    "layer4": {
      "enable_sequencing": true,
      "emergency_sell_priority": 100,
      "high_conviction_buy_priority": 85
    }
  }
}
```

## Learning and Adaptation

### Fast Pattern Learning
Track patterns that precede wins/losses:
- Store: `{pattern: "high_conviction_breakout", outcomes: [+18%, +22%, -5%, +15%]}`
- Calculate: Win rate, avg return, sample size
- Update pattern confidence scores after every 5 trades (vs current 20+ threshold)
- Store in `data/pattern_learning.json`

Example patterns tracked:
- "high_conviction_breakout" → 75% win rate, +18% avg return
- "score_drop_25_plus" → 80% led to losses when held
- "trailing_stop_saved" → Saved +$X vs fixed stops

### Conviction Calibration
Compare conviction scores to actual outcomes:
- If high-conviction (85+) trades only winning 50% → reduce conviction multipliers by 10%
- If medium-conviction (70-75) outperforming → increase their position sizes by 10%
- Track conviction vs outcome in post-mortems
- Recalibrate every 10 trades

### Dynamic Stop Optimization
Track which stop strategies work best:
- "Trailing stops saved +$X vs fixed stops over last 20 trades"
- "Volatility-adjusted stops reduced whipsaws by Y%"
- "Regime-aware stops caught Z more bear market losses"
- Auto-tune stop percentages based on recent performance

### Layer Aggressiveness Auto-Tuning
If portfolio underperforming (Sharpe < 0.5, drawdown > 15%):
- **Layer 1 (Risk):** Increase aggressiveness (exit deteriorating positions faster)
  - Lower score drop threshold from 30 → 25
  - Tighten stops by 1%
- **Layer 3 (Portfolio):** Relax limits slightly (allow higher conviction bets)
  - Increase sector limit from 40% → 45%

If portfolio overperforming but volatile (Sharpe > 1.0, but daily volatility > 3%):
- **Layer 1 (Risk):** Decrease aggressiveness (let winners run longer)
  - Raise score drop threshold from 30 → 35
  - Widen trailing stops by 1%
- **Layer 3 (Portfolio):** Tighten limits (enforce more diversification)
  - Decrease sector limit from 40% → 35%

### Enhanced Post-Mortems
After each trade, record in `data/enhanced_post_mortems.csv`:
- All layer decisions (conviction score, correlation at entry, sector weight, etc.)
- Pattern flags at entry/exit
- Whether execution sequence was optimal (did we sell before buying?)
- Layer 1 signals during hold period (was deterioration detected?)
- Actual vs expected return based on conviction

Schema:
```
ticker, entry_date, exit_date, return_pct,
conviction_score, patterns_at_entry, sector_weight_at_entry,
correlation_cluster, execution_priority, urgency_score,
layer1_signals_during_hold, layer3_constraints_applied,
conviction_accuracy (actual_return vs expected_return)
```

### Learning Cadence
- **Every 5 trades:** Update pattern learning, conviction calibration
- **Every 10 trades:** Review stop optimization
- **Every 20 trades:** Comprehensive layer aggressiveness review
- **Monthly:** Deep analysis of all learning metrics, manual review

## Success Metrics

Track these metrics to validate the enhancement is working:

### Performance Metrics
- **Sharpe Ratio:** Should improve from current baseline
- **Max Drawdown:** Should decrease (better risk management)
- **Win Rate:** Should improve (better entry/exit decisions)
- **Average Win / Average Loss:** Should increase (let winners run, cut losers faster)

### System Intelligence Metrics
- **Execution efficiency:** % of times sells executed before buys when cash was needed
- **Conviction accuracy:** Correlation between conviction score and actual returns
- **Deterioration detection:** % of losses caught by Layer 1 before hitting stop loss
- **Portfolio balance:** Average sector concentration, correlation cluster frequency

### Adaptation Metrics
- **Learning velocity:** Time to detect and adjust to pattern changes (target: 5-10 trades)
- **Stop effectiveness:** Trailing stops vs fixed stops performance comparison
- **Rebalancing value:** Profit/loss from Layer 3 rebalancing proposals

### Comparison to Current System
Run parallel paper trading for 30 days:
- Current system (control)
- Enhanced system (test)
- Compare all metrics above

## Implementation Phases

### Phase 1: Layer 1 (Risk Management)
- Position re-evaluation
- Dynamic stops (trailing, volatility-adjusted, regime-aware)
- Deterioration detection
- Urgency scoring

### Phase 2: Layer 2 (Opportunity Management)
- Conviction scoring
- Pattern detection
- Conviction-based position sizing
- Opportunity scoring

### Phase 3: Layer 3 (Portfolio Composition)
- Correlation analysis
- Concentration limits
- Trade modification logic
- Rebalancing proposals

### Phase 4: Layer 4 (Execution Sequencer)
- Priority scoring
- Strategic sequencing
- Dynamic cash tracking
- Execution reporting

### Phase 5: Learning System
- Pattern learning
- Conviction calibration
- Stop optimization
- Auto-tuning

### Phase 6: Testing & Validation
- Parallel paper trading
- Metrics comparison
- Dashboard integration
- Documentation

## Risk Considerations

### Potential Issues
- **Over-optimization:** Too many rules could lead to analysis paralysis
- **Computational cost:** Re-scoring all positions + correlation analysis on every run
- **Configuration complexity:** Many knobs to tune
- **Testing difficulty:** Hard to validate without live trading or long backtests

### Mitigations
- Start with layers disabled, enable one at a time
- Add performance monitoring and caching for expensive operations
- Provide sensible defaults, document tuning guidelines
- Paper trade for 30 days before enabling in live mode
- Keep kill switch: `"enable_layers": false` reverts to current system

## Conclusion

This 4-layer architecture transforms MicroCapRebuilder from a mechanical rule-follower into an intelligent portfolio manager that:
- ✅ Continuously re-evaluates positions (not just at entry/exit)
- ✅ Thinks strategically about execution order
- ✅ Manages portfolio composition and balance
- ✅ Adapts quickly to changing patterns and conditions
- ✅ Sizes positions by conviction and risk
- ✅ Uses dynamic, adaptive risk management

Each layer is independent, toggle-able, and tunable. The system can be incrementally enhanced (one layer at a time) and validated through parallel paper trading before going live.
