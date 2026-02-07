# Layer 4: Execution Sequencer - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add execution sequencing intelligence that prioritizes actions strategically, tracks cash, and prevents execution conflicts.

**Architecture:** Layer 4 processes last after all layers, assigns priorities, sorts actions, detects collisions, tracks cash, and creates final execution plan.

**Tech Stack:** Python 3, existing PortfolioState architecture, ProposedAction dataclass

---

## Task 1: Verify/Update Execution Data Structures

**Files:**
- Modify: `scripts/enhanced_structures.py`

**Step 1: Verify PrioritizedAction exists**

Check if PrioritizedAction dataclass exists. If not, add after ProposedAction:

```python
@dataclass
class PrioritizedAction:
    """Action with assigned priority for execution sequencing."""
    action: ProposedAction
    priority: int  # 0-100
    priority_reason: str
    execution_order: int  # Assigned during sequencing
```

**Step 2: Verify ExecutionPlan exists and has needed fields**

Check ExecutionPlan dataclass (should already exist). Ensure it has:

```python
@dataclass
class ExecutionPlan:
    """Final sequenced execution plan."""
    sequenced_actions: List[PrioritizedAction]
    initial_cash: float
    final_cash_estimate: float
    skipped_actions: List[Dict] = field(default_factory=list)
    execution_notes: List[str] = field(default_factory=list)
```

**Step 3: Test imports**

Run:
```bash
python3 -c "from scripts.enhanced_structures import PrioritizedAction, ExecutionPlan; print('OK')"
```

**Step 4: Commit (if changes made)**

```bash
git add scripts/enhanced_structures.py
git commit -m "feat(layer4): verify execution sequencer data structures

- PrioritizedAction for priority-scored actions
- ExecutionPlan for final sequenced output"
```

---

## Task 2: Create ExecutionSequencer

**Files:**
- Create: `scripts/execution_sequencer.py`

**Step 1: Create execution_sequencer.py**

Create `scripts/execution_sequencer.py`:

```python
#!/usr/bin/env python3
"""
Layer 4: Execution Sequencer

Prioritizes actions strategically, tracks cash, prevents execution conflicts.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

from enhanced_structures import (
    ProposedAction, PrioritizedAction, ExecutionPlan
)
from portfolio_state import PortfolioState


DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


class ExecutionSequencer:
    """Layer 4: Execution Sequencer - Strategic action prioritization."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize execution sequencer with configuration."""
        self.config = config or load_config()
        self.layer4_config = self.config.get("enhanced_trading", {}).get("layer4", {})
        self.enabled = self.layer4_config.get("enable_sequencing", True)

        # Load priority levels from config
        self.priorities = self.layer4_config.get("priorities", {
            "emergency_sell": 100,
            "deteriorating_sell_high": 90,
            "deteriorating_sell_medium": 70,
            "quality_degradation_sell": 60,
            "rebalancing_sell": 50,
            "high_conviction_buy": 85,
            "medium_conviction_buy": 65,
            "low_conviction_buy": 45,
        })

    def process(self, state: PortfolioState, proposed_actions: List[ProposedAction]) -> ExecutionPlan:
        """
        Process Layer 4: Sequence actions by priority, detect collisions, track cash.

        Args:
            state: Current portfolio state
            proposed_actions: All proposed actions from Layers 1-3

        Returns:
            ExecutionPlan with sequenced actions
        """
        if not self.enabled or not proposed_actions:
            return ExecutionPlan(
                sequenced_actions=[],
                initial_cash=state.cash,
                final_cash_estimate=state.cash,
                skipped_actions=[],
                execution_notes=["Layer 4 disabled or no actions to sequence"]
            )

        # Step 1: Assign priorities
        prioritized = self._assign_priorities(proposed_actions)

        # Step 2: Detect and resolve collisions
        resolved, skipped_collisions = self._resolve_collisions(prioritized)

        # Step 3: Sort by priority
        sorted_actions = sorted(resolved, key=lambda x: (-x.priority, x.action.ticker))

        # Step 4: Track cash and filter affordable actions
        final_sequence, skipped_cash = self._track_cash(sorted_actions, state.cash)

        # Assign execution order
        for i, action in enumerate(final_sequence):
            action.execution_order = i + 1

        # Calculate final cash estimate
        final_cash = state.cash
        for paction in final_sequence:
            if paction.action.action_type == "SELL":
                final_cash += paction.action.shares * paction.action.price
            else:  # BUY
                final_cash -= paction.action.shares * paction.action.price

        # Build execution notes
        notes = []
        if skipped_collisions:
            notes.append(f"Resolved {len(skipped_collisions)} collision(s)")
        if skipped_cash:
            notes.append(f"Skipped {len(skipped_cash)} action(s) due to insufficient cash")

        print(f"\n  🎯 Layer 4: Sequenced {len(final_sequence)} action(s)")
        if skipped_collisions or skipped_cash:
            print(f"  ⚠️  Skipped {len(skipped_collisions) + len(skipped_cash)} action(s)")

        return ExecutionPlan(
            sequenced_actions=final_sequence,
            initial_cash=state.cash,
            final_cash_estimate=round(final_cash, 2),
            skipped_actions=skipped_collisions + skipped_cash,
            execution_notes=notes
        )

    def _assign_priorities(self, actions: List[ProposedAction]) -> List[PrioritizedAction]:
        """Assign priority scores to all actions."""
        prioritized = []

        for action in actions:
            priority, reason = self._calculate_priority(action)
            prioritized.append(PrioritizedAction(
                action=action,
                priority=priority,
                priority_reason=reason,
                execution_order=0  # Assigned later
            ))

        return prioritized

    def _calculate_priority(self, action: ProposedAction) -> tuple[int, str]:
        """
        Calculate priority for a single action.

        Returns:
            (priority_score, reason_string)
        """
        if action.action_type == "SELL":
            # Determine sell priority from reason
            reason_lower = action.reason.lower()

            if "emergency" in reason_lower or "stop" in reason_lower:
                return self.priorities["emergency_sell"], "Emergency/stop loss sell"
            elif "deteriorat" in reason_lower:
                # Use urgency score if available (from Layer 1)
                # For now, use medium priority
                return self.priorities["deteriorating_sell_medium"], "Deteriorating position"
            elif "rebalanc" in reason_lower:
                return self.priorities["rebalancing_sell"], "Rebalancing sell"
            else:
                return self.priorities["quality_degradation_sell"], "Quality degradation"

        else:  # BUY
            # Determine buy priority from conviction (in reason or quant_score)
            quant_score = action.quant_score or 0

            if quant_score >= 80:
                return self.priorities["high_conviction_buy"], f"High conviction buy (score {quant_score:.0f})"
            elif quant_score >= 70:
                return self.priorities["medium_conviction_buy"], f"Medium conviction buy (score {quant_score:.0f})"
            else:
                return self.priorities["low_conviction_buy"], f"Low conviction buy (score {quant_score:.0f})"

    def _resolve_collisions(
        self, prioritized: List[PrioritizedAction]
    ) -> tuple[List[PrioritizedAction], List[Dict]]:
        """
        Detect and resolve collisions (same ticker in multiple actions).

        Returns:
            (resolved_actions, skipped_actions)
        """
        # Group by ticker
        ticker_groups = defaultdict(list)
        for paction in prioritized:
            ticker_groups[paction.action.ticker].append(paction)

        resolved = []
        skipped = []

        for ticker, actions in ticker_groups.items():
            if len(actions) == 1:
                # No collision
                resolved.append(actions[0])
                continue

            # Collision detected
            sells = [a for a in actions if a.action.action_type == "SELL"]
            buys = [a for a in actions if a.action.action_type == "BUY"]

            if sells and buys:
                # Sell + Buy collision: Keep sell, skip buy
                resolved.extend(sells)
                for buy in buys:
                    skipped.append({
                        "action": buy.action,
                        "reason": f"Collision with SELL {ticker} (sell takes priority)"
                    })
            elif len(sells) > 1:
                # Multiple sells: Combine into one (keep highest priority)
                best_sell = max(sells, key=lambda x: x.priority)
                resolved.append(best_sell)
                for sell in sells:
                    if sell != best_sell:
                        skipped.append({
                            "action": sell.action,
                            "reason": f"Duplicate SELL {ticker} (combined into single sell)"
                        })
            else:
                # Multiple buys: Keep highest priority
                best_buy = max(buys, key=lambda x: x.priority)
                resolved.append(best_buy)
                for buy in buys:
                    if buy != best_buy:
                        skipped.append({
                            "action": buy.action,
                            "reason": f"Duplicate BUY {ticker} (keeping highest priority)"
                        })

        return resolved, skipped

    def _track_cash(
        self, sorted_actions: List[PrioritizedAction], initial_cash: float
    ) -> tuple[List[PrioritizedAction], List[Dict]]:
        """
        Simulate cash flow sequentially, skip actions that overdraw.

        Returns:
            (affordable_actions, skipped_actions)
        """
        cash = initial_cash
        affordable = []
        skipped = []

        for paction in sorted_actions:
            action = paction.action

            if action.action_type == "SELL":
                # Sells add cash
                proceeds = action.shares * action.price
                cash += proceeds
                affordable.append(paction)
            else:  # BUY
                # Buys require cash
                cost = action.shares * action.price
                if cost <= cash:
                    cash -= cost
                    affordable.append(paction)
                else:
                    skipped.append({
                        "action": action,
                        "reason": f"Insufficient cash (need ${cost:.2f}, have ${cash:.2f})"
                    })

        return affordable, skipped
```

**Step 2: Test ExecutionSequencer**

Run:
```python
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from execution_sequencer import ExecutionSequencer
from portfolio_state import load_portfolio_state
from ai_review import ProposedAction

state = load_portfolio_state(fetch_prices=False)
sequencer = ExecutionSequencer()

# Mock some proposed actions
actions = [
    ProposedAction(
        action_type="SELL",
        ticker="TEST",
        shares=100,
        price=10.0,
        reason="EMERGENCY",
        stop_loss=0,
        take_profit=0
    ),
    ProposedAction(
        action_type="BUY",
        ticker="TEST2",
        shares=50,
        price=20.0,
        reason="High conviction",
        quant_score=85,
        stop_loss=0,
        take_profit=0
    )
]

plan = sequencer.process(state, actions)
print(f"Sequenced: {len(plan.sequenced_actions)} actions")
print(f"Skipped: {len(plan.skipped_actions)} actions")
print(f"Cash: ${plan.initial_cash:.2f} → ${plan.final_cash_estimate:.2f}")
print("OK")
EOF
```

Expected: Prints execution plan summary and "OK"

**Step 3: Commit**

```bash
git add scripts/execution_sequencer.py
git commit -m "feat(layer4): add ExecutionSequencer with strategic prioritization

- Priority scoring (0-100) for all actions
- Collision detection and resolution
- Sequential cash tracking
- Skips actions that overdraw cash
- Generates final ExecutionPlan"
```

---

## Task 3: Integrate Layer 4 into unified_analysis.py

**Files:**
- Modify: `scripts/unified_analysis.py`

**Step 1: Add import**

Add to imports:

```python
from execution_sequencer import ExecutionSequencer
```

**Step 2: Integrate Layer 4 after all other layers**

Find where proposed_actions list is complete (after Layer 3) and add:

```python
# Run Layer 4: Execution Sequencer (if layers enabled)
if config.get("enhanced_trading", {}).get("enable_layers", False):
    print("\nRunning Layer 4: Execution Sequencer...")
    sequencer = ExecutionSequencer(config)
    execution_plan = sequencer.process(state, proposed_actions)

    # Display execution plan
    if execution_plan.sequenced_actions:
        print(f"\n  📋 Execution Plan ({len(execution_plan.sequenced_actions)} actions):")
        for paction in execution_plan.sequenced_actions:
            action = paction.action
            priority_badge = f"[{paction.priority}]"
            action_str = f"{action.action_type} {action.ticker}"
            print(f"  {paction.execution_order}. {priority_badge} {action_str} - {paction.priority_reason}")

    # Display skipped actions
    if execution_plan.skipped_actions:
        print(f"\n  ⏭️  Skipped {len(execution_plan.skipped_actions)} action(s):")
        for skipped in execution_plan.skipped_actions:
            action = skipped["action"]
            print(f"  - {action.action_type} {action.ticker}: {skipped['reason']}")

    # Update proposed_actions to only include sequenced actions
    proposed_actions = [pa.action for pa in execution_plan.sequenced_actions]
```

**Step 3: Test integration**

Run:
```bash
cd scripts && python3 unified_analysis.py
```

Expected: Shows "Running Layer 4: Execution Sequencer..." with execution plan

**Step 4: Commit**

```bash
git add scripts/unified_analysis.py
git commit -m "feat(layer4): integrate ExecutionSequencer into unified analysis

- Run Layer 4 after Layers 1-3
- Display execution plan with priorities
- Show skipped actions with reasons
- All 4 layers now fully orchestrated"
```

---

## Success Criteria

✅ Task 1: Execution data structures verified/updated
✅ Task 2: ExecutionSequencer created with all logic
✅ Task 3: Layer 4 integrated into unified_analysis.py

**Test:** Run `python3 scripts/unified_analysis.py` and verify:
- "Running Layer 4: Execution Sequencer..." appears
- Execution plan displayed with priority scores
- Actions sorted by priority (high → low)
- Skipped actions shown with reasons
- Final cash estimate displayed
