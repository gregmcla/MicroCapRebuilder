# Layer 2: Opportunity Management - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add intelligent opportunity management with conviction scoring, pattern detection, and dynamic position sizing.

**Architecture:** Layer 2 processes after Layer 1 (Risk Management), scores candidates with conviction multipliers, detects entry patterns, and sizes positions by conviction + volatility.

**Tech Stack:** Python 3, existing PortfolioState/StockScorer architecture, config-driven

---

## Task 1: Add Conviction Data Structures

**Files:**
- Modify: `scripts/enhanced_structures.py`

**Step 1: Add conviction and pattern enums**

Add to `enhanced_structures.py` after existing enums:

```python
class ConvictionLevel(str, Enum):
    """Conviction level categories."""
    EXCEPTIONAL = "EXCEPTIONAL"  # 90+
    STRONG = "STRONG"  # 80-89
    GOOD = "GOOD"  # 70-79
    ACCEPTABLE = "ACCEPTABLE"  # 60-69


class PatternType(str, Enum):
    """Entry pattern types."""
    BREAKOUT = "BREAKOUT"
    MOMENTUM_SURGE = "MOMENTUM_SURGE"
    MEAN_REVERSION = "MEAN_REVERSION"
    VOLUME_SPIKE = "VOLUME_SPIKE"
```

**Step 2: Add ConvictionScore dataclass**

Add after SellProposal:

```python
@dataclass
class ConvictionScore:
    """Conviction scoring result for a candidate."""
    ticker: str
    composite_score: float  # Base 6-factor score
    conviction_multiplier: float  # 0.75 - 2.0
    final_conviction: float  # composite * multiplier (capped at 100)
    conviction_level: ConvictionLevel
    patterns_detected: List['PatternSignal']
    factors: Dict[str, float]  # Individual factor scores
    atr_pct: float = 0.0
```

**Step 3: Add PatternSignal dataclass**

Add after ConvictionScore:

```python
@dataclass
class PatternSignal:
    """Detected entry pattern."""
    pattern_type: PatternType
    confidence: int  # 0-100
    description: str
    detected_at_price: float
```

**Step 4: Add BuyProposal dataclass**

Add after PatternSignal:

```python
@dataclass
class BuyProposal:
    """Buy proposal from Layer 2."""
    ticker: str
    shares: int
    price: float
    total_value: float
    conviction_score: ConvictionScore
    position_size_pct: float  # % of portfolio
    rationale: str  # Human-readable explanation
```

**Step 5: Run test to verify imports**

Run:
```bash
python3 -c "from scripts.enhanced_structures import ConvictionLevel, PatternType, ConvictionScore, PatternSignal, BuyProposal; print('OK')"
```

Expected: Prints "OK"

**Step 6: Commit**

```bash
git add scripts/enhanced_structures.py
git commit -m "feat(layer2): add conviction and pattern data structures

- ConvictionLevel enum (EXCEPTIONAL/STRONG/GOOD/ACCEPTABLE)
- PatternType enum (BREAKOUT/MOMENTUM_SURGE/MEAN_REVERSION/VOLUME_SPIKE)
- ConvictionScore dataclass with multiplier and patterns
- PatternSignal dataclass for detected patterns
- BuyProposal dataclass for Layer 2 output"
```

---

## Task 2: Create OpportunityLayer with Conviction Scoring

**Files:**
- Create: `scripts/opportunity_layer.py`

**Step 1: Create opportunity_layer.py skeleton**

Create `scripts/opportunity_layer.py`:

```python
#!/usr/bin/env python3
"""
Layer 2: Opportunity Management

Scores candidates with conviction levels, detects entry patterns,
sizes positions by conviction and volatility.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

from enhanced_structures import (
    BuyProposal, ConvictionScore, ConvictionLevel,
    PatternSignal, PatternType
)
from stock_scorer import StockScorer, StockScore
from portfolio_state import PortfolioState, load_watchlist
from market_regime import MarketRegime, get_position_size_multiplier


DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


class OpportunityLayer:
    """Layer 2: Opportunity Management - Conviction scoring and pattern detection."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize opportunity layer with configuration."""
        self.config = config or load_config()
        self.layer2_config = self.config.get("enhanced_trading", {}).get("layer2", {})
        self.enabled = self.layer2_config.get("enable_conviction", True)
        self.min_conviction = self.layer2_config.get("min_conviction", 60)

    def process(self, state: PortfolioState, risk_layer_output: Dict) -> Dict:
        """
        Process Layer 2: Score candidates with conviction, detect patterns.

        Args:
            state: Current portfolio state
            risk_layer_output: Output from Layer 1 (for context)

        Returns:
            dict with:
                - buy_proposals: List[BuyProposal]
                - conviction_scores: Dict[ticker, ConvictionScore]
        """
        if not self.enabled:
            return {
                "buy_proposals": [],
                "conviction_scores": {}
            }

        # Check if we can buy
        if state.regime == MarketRegime.BEAR:
            print("  ⚠️  Bear market - Layer 2 skipping new buys")
            return {"buy_proposals": [], "conviction_scores": {}}

        if state.num_positions >= self.config.get("max_positions", 15):
            print(f"  ⚠️  At max positions ({state.num_positions}) - Layer 2 skipping")
            return {"buy_proposals": [], "conviction_scores": {}}

        # Load and score watchlist
        watchlist = load_watchlist()
        current_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()
        candidates = [t for t in watchlist if t not in current_tickers]

        if not candidates:
            return {"buy_proposals": [], "conviction_scores": {}}

        scorer = StockScorer(regime=state.regime)
        scored_results = scorer.score_watchlist(candidates)

        # Calculate conviction for each candidate
        conviction_scores = {}
        for stock_score in scored_results:
            if not stock_score:
                continue

            conviction = self.calculate_conviction(stock_score, state.regime)
            if conviction.final_conviction >= self.min_conviction:
                conviction_scores[stock_score.ticker] = conviction

        # Generate buy proposals
        buy_proposals = self._generate_buy_proposals(
            conviction_scores, state
        )

        print(f"\n  💡 Layer 2: {len(conviction_scores)} candidates meet conviction threshold")
        print(f"  💰 Generated {len(buy_proposals)} buy proposal(s)")

        return {
            "buy_proposals": buy_proposals,
            "conviction_scores": conviction_scores
        }

    def calculate_conviction(
        self, stock_score: StockScore, regime: MarketRegime
    ) -> ConvictionScore:
        """
        Calculate conviction score with multipliers.

        Args:
            stock_score: Base stock score from 6-factor model
            regime: Current market regime

        Returns:
            ConvictionScore with multiplier applied
        """
        composite = stock_score.composite_score

        # Base multiplier from score
        thresholds = self.layer2_config.get("conviction_thresholds", {})
        multipliers = self.layer2_config.get("conviction_multipliers", {})

        if composite >= thresholds.get("exceptional", 90):
            base_multiplier = multipliers.get("exceptional", 2.0)
            level = ConvictionLevel.EXCEPTIONAL
        elif composite >= thresholds.get("strong", 80):
            base_multiplier = multipliers.get("strong", 1.5)
            level = ConvictionLevel.STRONG
        elif composite >= thresholds.get("good", 70):
            base_multiplier = multipliers.get("good", 1.0)
            level = ConvictionLevel.GOOD
        else:
            base_multiplier = multipliers.get("acceptable", 0.75)
            level = ConvictionLevel.ACCEPTABLE

        # Adjustments
        adjustments = self.layer2_config.get("conviction_adjustments", {})
        multiplier = base_multiplier

        # Multiple confirmations (momentum + volume + RS all strong)
        if self._check_multiple_confirmations(stock_score):
            multiplier += adjustments.get("multiple_confirmations", 0.3)

        # Pattern detection
        patterns = self._detect_entry_patterns(stock_score)
        if patterns:
            for pattern in patterns:
                if pattern.pattern_type == PatternType.BREAKOUT:
                    multiplier += adjustments.get("breakout_pattern", 0.2)
                elif pattern.pattern_type == PatternType.MOMENTUM_SURGE:
                    multiplier += adjustments.get("fresh_high", 0.2)

        # Regime alignment
        if self._check_regime_alignment(stock_score, regime):
            multiplier += adjustments.get("regime_alignment", 0.2)

        # Low volatility
        if stock_score.atr_pct < 2.0:
            multiplier += adjustments.get("low_volatility", 0.1)

        # Cap multiplier
        max_multiplier = self.layer2_config.get("conviction_multiplier_max", 2.0)
        multiplier = min(multiplier, max_multiplier)

        # Calculate final conviction
        final_conviction = min(100, composite * multiplier)

        return ConvictionScore(
            ticker=stock_score.ticker,
            composite_score=composite,
            conviction_multiplier=round(multiplier, 2),
            final_conviction=round(final_conviction, 1),
            conviction_level=level,
            patterns_detected=patterns,
            factors={
                "momentum": stock_score.momentum_score,
                "volatility": stock_score.volatility_score,
                "volume": stock_score.volume_score,
                "relative_strength": stock_score.relative_strength_score,
                "mean_reversion": stock_score.mean_reversion_score,
                "rsi": stock_score.rsi_score,
            },
            atr_pct=stock_score.atr_pct
        )

    def _check_multiple_confirmations(self, stock_score: StockScore) -> bool:
        """Check if momentum + volume + RS all strong."""
        return (
            stock_score.momentum_score >= 70 and
            stock_score.volume_score >= 70 and
            stock_score.relative_strength_score >= 70
        )

    def _detect_entry_patterns(self, stock_score: StockScore) -> List[PatternSignal]:
        """Detect entry patterns (breakout, momentum surge, etc.)."""
        patterns = []

        # Breakout: Strong momentum + high volume
        if stock_score.momentum_20d > 10 and stock_score.volume_score > 75:
            patterns.append(PatternSignal(
                pattern_type=PatternType.BREAKOUT,
                confidence=80,
                description=f"20-day momentum {stock_score.momentum_20d:.1f}% with high volume",
                detected_at_price=stock_score.current_price
            ))

        # Momentum surge: Multi-timeframe alignment
        if stock_score.momentum_alignment == "ALIGNED":
            patterns.append(PatternSignal(
                pattern_type=PatternType.MOMENTUM_SURGE,
                confidence=75,
                description="Multi-timeframe momentum alignment",
                detected_at_price=stock_score.current_price
            ))

        # Mean reversion: Oversold bounce
        if stock_score.rsi_value and stock_score.rsi_value < 35:
            patterns.append(PatternSignal(
                pattern_type=PatternType.MEAN_REVERSION,
                confidence=70,
                description=f"Oversold bounce from RSI {stock_score.rsi_value:.1f}",
                detected_at_price=stock_score.current_price
            ))

        return patterns

    def _check_regime_alignment(self, stock_score: StockScore, regime: MarketRegime) -> bool:
        """Check if stock aligns with market regime."""
        if regime == MarketRegime.BULL:
            # Bull market: Want high momentum stocks
            return stock_score.momentum_score >= 70
        elif regime == MarketRegime.SIDEWAYS:
            # Sideways: Want mean reversion plays
            return stock_score.mean_reversion_score >= 70
        else:
            # Bear: Want defensive (low vol, high quality)
            return stock_score.volatility_score >= 70

    def _generate_buy_proposals(
        self, conviction_scores: Dict[str, ConvictionScore], state: PortfolioState
    ) -> List[BuyProposal]:
        """Generate buy proposals with conviction-based position sizing."""
        proposals = []

        # Sort by final conviction
        sorted_convictions = sorted(
            conviction_scores.values(),
            key=lambda x: x.final_conviction,
            reverse=True
        )

        # Position sizing config
        sizing = self.layer2_config.get("position_sizing", {})
        high_conviction_pct = sizing.get("high_conviction_pct", 12.0) / 100
        medium_conviction_pct = sizing.get("medium_conviction_pct", 8.0) / 100
        low_conviction_pct = sizing.get("low_conviction_pct", 5.0) / 100

        # Regime multiplier
        position_multiplier = get_position_size_multiplier(state.regime)

        # Calculate position sizes
        slots_available = self.config.get("max_positions", 15) - state.num_positions
        remaining_cash = state.cash

        for conviction in sorted_convictions[:slots_available]:
            # Determine base position size by conviction
            if conviction.final_conviction >= 80:
                size_pct = high_conviction_pct
                conviction_label = "high"
            elif conviction.final_conviction >= 70:
                size_pct = medium_conviction_pct
                conviction_label = "medium"
            else:
                size_pct = low_conviction_pct
                conviction_label = "low"

            # Volatility adjustment - reduce size for high ATR
            if conviction.atr_pct > 6.0:
                size_pct *= 0.5  # 50% reduction for very high vol
            elif conviction.atr_pct > 4.0:
                size_pct *= 0.75  # 25% reduction for high vol

            # Apply regime multiplier and cap at max
            size_pct = min(size_pct * position_multiplier, self.config.get("max_position_pct", 15.0) / 100)
            position_value = min(state.total_equity * size_pct, remaining_cash)

            # Skip if position too small
            if position_value < 100:
                continue

            # Get price from conviction score (stock_score has current_price)
            # We need to fetch price here - for now use a placeholder
            # TODO: Get actual price from price_cache or fresh fetch
            price = conviction.factors.get("current_price", 0)
            if price == 0:
                # Skip if no price available
                continue

            shares = int(position_value / price)
            if shares == 0:
                continue

            total_value = shares * price

            # Build rationale
            patterns_str = ", ".join([p.pattern_type.value for p in conviction.patterns_detected]) if conviction.patterns_detected else "none"
            rationale = f"{conviction_label.title()} conviction ({conviction.final_conviction:.1f}) - {conviction.conviction_level.value} with {patterns_str} patterns"

            proposals.append(BuyProposal(
                ticker=conviction.ticker,
                shares=shares,
                price=round(price, 2),
                total_value=round(total_value, 2),
                conviction_score=conviction,
                position_size_pct=round(size_pct * 100, 1),
                rationale=rationale
            ))

            remaining_cash -= total_value

        return proposals
```

**Step 2: Test conviction scoring**

Run:
```python
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from opportunity_layer import OpportunityLayer
from portfolio_state import load_portfolio_state

state = load_portfolio_state(fetch_prices=False)
layer = OpportunityLayer()
result = layer.process(state, {})
print(f"Buy proposals: {len(result['buy_proposals'])}")
print(f"Conviction scores: {len(result['conviction_scores'])}")
if result['conviction_scores']:
    sample = list(result['conviction_scores'].values())[0]
    print(f"Sample conviction: {sample.ticker} = {sample.final_conviction:.1f} ({sample.conviction_level.value})")
print("OK")
EOF
```

Expected: Prints counts and sample conviction

**Step 3: Commit**

```bash
git add scripts/opportunity_layer.py
git commit -m "feat(layer2): add OpportunityLayer with conviction scoring

- Conviction multipliers based on composite score (0.75x-2.0x)
- Pattern detection (breakout, momentum surge, mean reversion)
- Adjustments for confirmations, regime alignment, low volatility
- Conviction-based position sizing (5-15% of portfolio)
- Volatility adjustment (reduce size for high ATR stocks)
- Generate BuyProposal objects with rationale"
```

---

## Task 3: Integrate Layer 2 into unified_analysis.py

**Files:**
- Modify: `scripts/unified_analysis.py`

**Step 1: Import OpportunityLayer**

Add to imports at top:

```python
from opportunity_layer import OpportunityLayer
```

**Step 2: Replace buy candidate loop with Layer 2**

Find the section that scores watchlist candidates (around line 150-200) and replace with:

```python
# Run Layer 2: Opportunity Management
if config.get("enhanced_trading", {}).get("enable_layers", False):
    print("\nRunning Layer 2: Opportunity Management...")
    layer2 = OpportunityLayer(config)
    layer2_output = layer2.process(state, layer1_output)

    # Convert BuyProposal to ProposedAction for AI review
    for buy_proposal in layer2_output["buy_proposals"]:
        proposed_actions.append(ProposedAction(
            action_type="BUY",
            ticker=buy_proposal.ticker,
            shares=buy_proposal.shares,
            price=buy_proposal.price,
            reason=buy_proposal.rationale,
            stop_loss=state.config.get("default_stop_loss_pct", 8.0),
            take_profit=state.config.get("default_take_profit_pct", 20.0),
        ))

        conviction = buy_proposal.conviction_score
        print(f"  💡 {buy_proposal.ticker}: Conviction {conviction.final_conviction:.1f} ({conviction.conviction_level.value}), {buy_proposal.shares} shares @ ${buy_proposal.price:.2f} = ${buy_proposal.total_value:.2f} ({buy_proposal.position_size_pct:.1f}% of portfolio)")
else:
    # Fallback to old logic if layers disabled
    # [Keep existing candidate scoring code]
```

**Step 3: Test integration**

Run:
```bash
cd scripts && python3 unified_analysis.py
```

Expected: Shows "Running Layer 2: Opportunity Management..." and conviction-based proposals

**Step 4: Commit**

```bash
git add scripts/unified_analysis.py
git commit -m "feat(layer2): integrate OpportunityLayer into unified analysis

- Replace basic buy candidate loop with Layer 2
- Convert BuyProposal to ProposedAction for AI review
- Display conviction scores and position sizing
- Fallback to old logic if enhanced_trading.enable_layers is false"
```

---

## Success Criteria

✅ Task 1: Conviction data structures compile and import successfully
✅ Task 2: OpportunityLayer calculates conviction scores with multipliers
✅ Task 3: Layer 2 integrated into unified_analysis.py, generates buy proposals

**Test:** Run `python3 scripts/unified_analysis.py` and verify:
- "Running Layer 2: Opportunity Management..." appears
- Conviction scores displayed with levels (EXCEPTIONAL/STRONG/GOOD/ACCEPTABLE)
- Position sizing varies by conviction (5-15% of portfolio)
- Patterns detected and shown in output
