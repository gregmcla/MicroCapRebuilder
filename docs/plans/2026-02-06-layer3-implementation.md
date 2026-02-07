# Layer 3: Portfolio Composition - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add portfolio composition intelligence that enforces diversification limits, detects correlation, and triggers rebalancing.

**Architecture:** Layer 3 processes after Layer 2 (Opportunity Management), analyzes sector concentration, correlation, and position sizing, then filters buys that violate limits and generates rebalancing sells.

**Tech Stack:** Python 3, pandas, yfinance for correlation data, existing PortfolioState architecture

---

## Task 1: Create Sector Mapping

**Files:**
- Create: `data/sector_mapping.json`
- Create: `scripts/sector_mapper.py`

**Step 1: Create sector mapping JSON**

Create `data/sector_mapping.json` with current portfolio tickers:

```json
{
  "AEIS": "Technology",
  "HLX": "Energy",
  "TEX": "Consumer Cyclical",
  "CRC": "Energy",
  "BELFB": "Technology",
  "GOLF": "Consumer Cyclical",
  "LBRT": "Energy",
  "CRUS": "Technology",
  "LPX": "Industrials",
  "MGY": "Energy",
  "WDFC": "Consumer Defensive",
  "GPRK": "Energy"
}
```

**Step 2: Create sector_mapper.py helper**

Create `scripts/sector_mapper.py`:

```python
#!/usr/bin/env python3
"""
Sector Mapper - Maps tickers to sectors for composition analysis.

Uses static JSON file with yfinance fallback for missing tickers.
"""

import json
from pathlib import Path
from typing import Optional, Dict
import yfinance as yf

DATA_DIR = Path(__file__).parent.parent / "data"
SECTOR_FILE = DATA_DIR / "sector_mapping.json"


def load_sector_mapping() -> Dict[str, str]:
    """Load sector mapping from JSON file."""
    if SECTOR_FILE.exists():
        with open(SECTOR_FILE) as f:
            return json.load(f)
    return {}


def save_sector_mapping(mapping: Dict[str, str]) -> None:
    """Save sector mapping to JSON file."""
    with open(SECTOR_FILE, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


def get_sector(ticker: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Get sector for ticker.

    Args:
        ticker: Stock ticker
        mapping: Optional pre-loaded mapping (for performance)

    Returns:
        Sector name or "Unknown" if not found
    """
    if mapping is None:
        mapping = load_sector_mapping()

    # Check static mapping first
    if ticker in mapping:
        return mapping[ticker]

    # Fallback to yfinance
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "Unknown")

        # Cache for next time
        mapping[ticker] = sector
        save_sector_mapping(mapping)

        return sector
    except Exception:
        return "Unknown"


def update_sector_mapping(tickers: list) -> Dict[str, str]:
    """
    Update sector mapping for list of tickers.

    Fetches missing sectors from yfinance and updates JSON file.

    Args:
        tickers: List of ticker symbols

    Returns:
        Updated mapping dict
    """
    mapping = load_sector_mapping()

    for ticker in tickers:
        if ticker not in mapping:
            sector = get_sector(ticker, mapping)
            print(f"  {ticker}: {sector}")

    return mapping
```

**Step 3: Test sector mapper**

Run:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from sector_mapper import get_sector, load_sector_mapping

mapping = load_sector_mapping()
print(f"Loaded {len(mapping)} sectors")
print(f"WDFC: {get_sector('WDFC', mapping)}")
print(f"LBRT: {get_sector('LBRT', mapping)}")
print("OK")
EOF
```

Expected: Prints sector mappings and "OK"

**Step 4: Commit**

```bash
git add data/sector_mapping.json scripts/sector_mapper.py
git commit -m "feat(layer3): add sector mapping for composition analysis

- Static JSON mapping for current portfolio tickers
- SectorMapper helper with yfinance fallback
- Caches new sectors to JSON for performance"
```

---

## Task 2: Add Composition Data Structures

**Files:**
- Modify: `scripts/enhanced_structures.py`

**Step 1: Add CompositionViolation dataclass**

Add after BuyProposal:

```python
@dataclass
class CompositionViolation:
    """Portfolio composition limit violation."""
    ticker: str
    violation_type: str  # "SECTOR", "CORRELATION", "TOP3"
    current_value: float
    limit_value: float
    description: str
```

**Step 2: Add RebalanceTrigger dataclass**

Add after CompositionViolation:

```python
@dataclass
class RebalanceTrigger:
    """Rebalancing action trigger."""
    ticker: str
    current_pct: float  # % of portfolio
    target_pct: float
    trim_amount: float  # Dollar amount to trim
    reason: str
```

**Step 3: Test imports**

Run:
```bash
python3 -c "from scripts.enhanced_structures import CompositionViolation, RebalanceTrigger; print('OK')"
```

**Step 4: Commit**

```bash
git add scripts/enhanced_structures.py
git commit -m "feat(layer3): add composition data structures

- CompositionViolation for tracking limit violations
- RebalanceTrigger for rebalancing actions"
```

---

## Task 3: Create CompositionLayer

**Files:**
- Create: `scripts/composition_layer.py`

**Step 1: Create composition_layer.py skeleton**

Create `scripts/composition_layer.py`:

```python
#!/usr/bin/env python3
"""
Layer 3: Portfolio Composition

Enforces diversification limits, detects correlation, triggers rebalancing.
"""

import json
from pathlib import Path
from typing import List, Dict, Set, Optional
from collections import defaultdict

import pandas as pd
import yfinance as yf

from enhanced_structures import (
    BuyProposal, SellProposal, CompositionViolation,
    RebalanceTrigger, UrgencyLevel
)
from portfolio_state import PortfolioState
from sector_mapper import get_sector, load_sector_mapping


DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


class CompositionLayer:
    """Layer 3: Portfolio Composition - Diversification and correlation limits."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize composition layer with configuration."""
        self.config = config or load_config()
        self.layer3_config = self.config.get("enhanced_trading", {}).get("layer3", {})
        self.enabled = self.layer3_config.get("enable_composition", True)

        # Load limits
        self.sector_limit_pct = self.layer3_config.get("sector_limit_pct", 40.0)
        self.correlation_threshold = self.layer3_config.get("correlation_threshold", 0.7)
        self.max_correlated = self.layer3_config.get("max_correlated_positions", 3)
        self.top3_limit_pct = self.layer3_config.get("top3_limit_pct", 45.0)

        # Load sector mapping
        self.sector_mapping = load_sector_mapping()

    def process(
        self,
        state: PortfolioState,
        layer1_output: Dict,
        layer2_output: Dict
    ) -> Dict:
        """
        Process Layer 3: Filter buys by composition limits, generate rebalancing.

        Args:
            state: Current portfolio state
            layer1_output: Output from Layer 1 (sells)
            layer2_output: Output from Layer 2 (buy proposals)

        Returns:
            dict with:
                - filtered_buys: List[BuyProposal] (approved buys)
                - blocked_buys: List[BuyProposal] (blocked by limits)
                - rebalance_sells: List[SellProposal] (rebalancing actions)
                - violations: List[CompositionViolation]
                - warnings: List[str]
        """
        if not self.enabled:
            return {
                "filtered_buys": layer2_output.get("buy_proposals", []),
                "blocked_buys": [],
                "rebalance_sells": [],
                "violations": [],
                "warnings": []
            }

        buy_proposals = layer2_output.get("buy_proposals", [])

        # Analyze current composition
        current_sectors = self._analyze_sectors(state)
        current_top3_pct = self._calculate_top3_pct(state)

        # Filter buy proposals
        filtered_buys = []
        blocked_buys = []
        violations = []
        warnings = []

        for proposal in buy_proposals:
            # Check sector limit
            sector_ok, sector_violation = self._check_sector_limit(
                proposal, state, current_sectors
            )
            if not sector_ok:
                blocked_buys.append(proposal)
                violations.append(sector_violation)
                continue

            # Check correlation (skip for now - implement in later iteration)
            # correlation_ok, corr_violation = self._check_correlation(proposal, state)

            # Check top-3 limit
            top3_ok, top3_violation = self._check_top3_limit(
                proposal, state, current_top3_pct
            )
            if not top3_ok:
                blocked_buys.append(proposal)
                violations.append(top3_violation)
                continue

            # Approved
            filtered_buys.append(proposal)

        # Generate warnings for current composition issues
        for sector, pct in current_sectors.items():
            if pct > self.sector_limit_pct:
                warnings.append(f"{sector} sector at {pct:.1f}% (limit {self.sector_limit_pct:.0f}%)")

        if current_top3_pct > self.top3_limit_pct:
            warnings.append(f"Top-3 concentration at {current_top3_pct:.1f}% (limit {self.top3_limit_pct:.0f}%)")

        # Check for rebalancing needs
        rebalance_sells = self._generate_rebalancing_sells(state, current_sectors, current_top3_pct)

        print(f"\n  🏗️  Layer 3: Approved {len(filtered_buys)}/{len(buy_proposals)} buys")
        if blocked_buys:
            print(f"  ⚠️  Blocked {len(blocked_buys)} buys due to composition limits")
        if rebalance_sells:
            print(f"  ⚖️  Generated {len(rebalance_sells)} rebalancing sell(s)")

        return {
            "filtered_buys": filtered_buys,
            "blocked_buys": blocked_buys,
            "rebalance_sells": rebalance_sells,
            "violations": violations,
            "warnings": warnings
        }

    def _analyze_sectors(self, state: PortfolioState) -> Dict[str, float]:
        """
        Analyze sector concentration in current portfolio.

        Returns:
            Dict[sector, percentage_of_portfolio]
        """
        if state.positions.empty:
            return {}

        sector_values = defaultdict(float)

        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            market_value = pos["market_value"]
            sector = get_sector(ticker, self.sector_mapping)
            sector_values[sector] += market_value

        # Convert to percentages
        return {
            sector: (value / state.total_equity * 100)
            for sector, value in sector_values.items()
        }

    def _calculate_top3_pct(self, state: PortfolioState) -> float:
        """Calculate percentage of portfolio in top 3 positions."""
        if state.positions.empty or len(state.positions) < 3:
            return 0.0

        sorted_positions = state.positions.sort_values("market_value", ascending=False)
        top3_value = sorted_positions.head(3)["market_value"].sum()

        return (top3_value / state.total_equity * 100) if state.total_equity > 0 else 0.0

    def _check_sector_limit(
        self,
        proposal: BuyProposal,
        state: PortfolioState,
        current_sectors: Dict[str, float]
    ) -> tuple[bool, Optional[CompositionViolation]]:
        """
        Check if buy would violate sector concentration limit.

        Returns:
            (is_ok, violation_or_none)
        """
        sector = get_sector(proposal.ticker, self.sector_mapping)
        current_sector_pct = current_sectors.get(sector, 0.0)

        # Calculate new sector percentage after buy
        new_sector_value = (current_sector_pct / 100 * state.total_equity) + proposal.total_value
        new_total_equity = state.total_equity  # Approximation (ignores cash decrease)
        new_sector_pct = (new_sector_value / new_total_equity * 100)

        if new_sector_pct > self.sector_limit_pct:
            violation = CompositionViolation(
                ticker=proposal.ticker,
                violation_type="SECTOR",
                current_value=new_sector_pct,
                limit_value=self.sector_limit_pct,
                description=f"{sector} sector would be {new_sector_pct:.1f}% (limit {self.sector_limit_pct:.0f}%)"
            )
            return False, violation

        return True, None

    def _check_top3_limit(
        self,
        proposal: BuyProposal,
        state: PortfolioState,
        current_top3_pct: float
    ) -> tuple[bool, Optional[CompositionViolation]]:
        """
        Check if buy would violate top-3 concentration limit.

        Returns:
            (is_ok, violation_or_none)
        """
        # Simulate portfolio with new position
        simulated_positions = state.positions.copy()

        # Add new position
        new_row = pd.DataFrame([{
            "ticker": proposal.ticker,
            "market_value": proposal.total_value,
            "shares": proposal.shares,
            "current_price": proposal.price,
        }])
        simulated_positions = pd.concat([simulated_positions, new_row], ignore_index=True)

        # Calculate new top-3
        sorted_positions = simulated_positions.sort_values("market_value", ascending=False)
        new_top3_value = sorted_positions.head(3)["market_value"].sum()
        new_total_equity = state.total_equity  # Approximation
        new_top3_pct = (new_top3_value / new_total_equity * 100)

        if new_top3_pct > self.top3_limit_pct:
            violation = CompositionViolation(
                ticker=proposal.ticker,
                violation_type="TOP3",
                current_value=new_top3_pct,
                limit_value=self.top3_limit_pct,
                description=f"Top-3 would be {new_top3_pct:.1f}% (limit {self.top3_limit_pct:.0f}%)"
            )
            return False, violation

        return True, None

    def _generate_rebalancing_sells(
        self,
        state: PortfolioState,
        current_sectors: Dict[str, float],
        current_top3_pct: float
    ) -> List[SellProposal]:
        """
        Generate rebalancing sells for oversized positions.

        Only triggers if:
        - Rebalancing enabled in config
        - Top-3 > limit OR any sector > limit
        - Position is >18% (15% target + 20% drift threshold)
        """
        rebalance_config = self.layer3_config.get("enable_rebalancing", True)
        if not rebalance_config:
            return []

        # Only rebalance if limits violated
        limits_violated = (
            current_top3_pct > self.top3_limit_pct or
            any(pct > self.sector_limit_pct for pct in current_sectors.values())
        )

        if not limits_violated:
            return []

        rebalance_sells = []
        target_pct = self.layer3_config.get("rebalance_target_pct", 15.0)
        trigger_pct = target_pct * (1 + self.layer3_config.get("rebalance_trigger_pct", 20.0) / 100)

        for _, pos in state.positions.iterrows():
            position_pct = (pos["market_value"] / state.total_equity * 100)

            if position_pct > trigger_pct:
                # Calculate trim amount
                target_value = state.total_equity * (target_pct / 100)
                trim_value = pos["market_value"] - target_value
                trim_shares = int(trim_value / pos["current_price"])

                if trim_shares > 0:
                    rebalance_sells.append(SellProposal(
                        ticker=pos["ticker"],
                        shares=trim_shares,
                        current_price=pos["current_price"],
                        reason=f"REBALANCING (position at {position_pct:.1f}%, target {target_pct:.0f}%)",
                        urgency_level=UrgencyLevel.LOW,
                        urgency_score=50
                    ))

        return rebalance_sells
```

**Step 2: Test CompositionLayer**

Run:
```python
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from composition_layer import CompositionLayer
from portfolio_state import load_portfolio_state

state = load_portfolio_state(fetch_prices=False)
layer = CompositionLayer()

# Mock layer2 output
layer2_output = {"buy_proposals": []}

result = layer.process(state, {}, layer2_output)
print(f"Warnings: {len(result['warnings'])}")
print(f"Rebalancing sells: {len(result['rebalance_sells'])}")
for warning in result['warnings']:
    print(f"  - {warning}")
print("OK")
EOF
```

Expected: Prints composition warnings and "OK"

**Step 3: Commit**

```bash
git add scripts/composition_layer.py
git commit -m "feat(layer3): add CompositionLayer with diversification limits

- Sector concentration limits (max 40% per sector)
- Top-3 concentration limits (max 45%)
- Filters buy proposals that violate limits
- Generates rebalancing sells for oversized positions
- Correlation analysis placeholder (to be implemented)"
```

---

## Task 4: Integrate Layer 3 into unified_analysis.py

**Files:**
- Modify: `scripts/unified_analysis.py`

**Step 1: Add import**

Add to imports:

```python
from composition_layer import CompositionLayer
```

**Step 2: Integrate Layer 3 after Layer 2**

Find the Layer 2 section and add Layer 3 after it:

```python
# Run Layer 3: Portfolio Composition (if layers enabled)
if config.get("enhanced_trading", {}).get("enable_layers", False):
    print("\nRunning Layer 3: Portfolio Composition...")
    layer3 = CompositionLayer(config)
    layer3_output = layer3.process(state, layer1_output, layer2_output)

    # Use filtered buys instead of all layer2 buys
    layer2_output["buy_proposals"] = layer3_output["filtered_buys"]

    # Add rebalancing sells to proposed actions
    for rebalance_sell in layer3_output["rebalance_sells"]:
        proposed_actions.append(ProposedAction(
            action_type="SELL",
            ticker=rebalance_sell.ticker,
            shares=rebalance_sell.shares,
            price=rebalance_sell.current_price,
            reason=rebalance_sell.reason,
            stop_loss=0.0,
            take_profit=0.0,
        ))

    # Display composition warnings
    for warning in layer3_output["warnings"]:
        print(f"  ⚠️  {warning}")

    # Display blocked buys
    for blocked in layer3_output["blocked_buys"]:
        violation = next((v for v in layer3_output["violations"] if v.ticker == blocked.ticker), None)
        if violation:
            print(f"  🚫 Blocked {blocked.ticker}: {violation.description}")
```

**Step 3: Test integration**

Run:
```bash
cd scripts && python3 unified_analysis.py
```

Expected: Shows "Running Layer 3: Portfolio Composition..." and composition warnings

**Step 4: Commit**

```bash
git add scripts/unified_analysis.py
git commit -m "feat(layer3): integrate CompositionLayer into unified analysis

- Run Layer 3 after Layer 2
- Filter buy proposals through composition limits
- Add rebalancing sells to proposed actions
- Display composition warnings and blocked buys"
```

---

## Success Criteria

✅ Task 1: Sector mapping created and sector_mapper.py working
✅ Task 2: Composition data structures compile
✅ Task 3: CompositionLayer enforces sector and top-3 limits
✅ Task 4: Layer 3 integrated into unified_analysis.py

**Test:** Run `python3 scripts/unified_analysis.py` and verify:
- "Running Layer 3: Portfolio Composition..." appears
- Composition warnings displayed if limits exceeded
- Blocked buys shown with violation reasons
- Rebalancing sells generated if needed
