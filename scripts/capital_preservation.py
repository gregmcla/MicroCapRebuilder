#!/usr/bin/env python3
"""
Capital Preservation Mode for GScott.

Auto-protects portfolio when risk thresholds are exceeded:
- Halts new buys
- Tightens stop losses
- Reduces position sizes

Triggers:
- Drawdown exceeds threshold (e.g., 10%)
- Risk score drops below threshold (e.g., 40)
- Bear market regime detected
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
from enum import Enum
import json

from market_regime import get_market_regime, MarketRegime
from risk_scoreboard import get_risk_scoreboard

# ─── Paths ───
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CONFIG_PATH = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration from config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


class PreservationTrigger(Enum):
    """Reasons for activating capital preservation."""
    DRAWDOWN = "drawdown_threshold"
    RISK_SCORE = "risk_score_threshold"
    BEAR_MARKET = "bear_market"
    MANUAL = "manual_override"


@dataclass
class PreservationAction:
    """Action taken during capital preservation."""
    name: str
    description: str
    value: Optional[float] = None


@dataclass
class PreservationStatus:
    """Current capital preservation status."""
    active: bool
    trigger_reasons: List[str] = field(default_factory=list)
    actions_taken: List[PreservationAction] = field(default_factory=list)
    exit_conditions: List[str] = field(default_factory=list)

    # Modifiers when active
    halt_new_buys: bool = False
    stop_loss_tightening_pct: float = 0.0  # e.g., 5.0 means tighten by 5%
    position_size_multiplier: float = 1.0  # e.g., 0.5 means half size


class CapitalPreservationManager:
    """Manages capital preservation mode."""

    # Default configuration if not in config.json
    DEFAULT_CONFIG = {
        "enabled": True,
        "triggers": {
            "drawdown_threshold_pct": 10.0,
            "risk_score_threshold": 40,
            "regime_bear_auto_enable": True
        },
        "actions": {
            "halt_new_buys": True,
            "tighten_stops_pct": 5.0,
            "reduce_position_size_multiplier": 0.5
        }
    }

    def __init__(self):
        self.config = load_config()
        self.preservation_config = self._get_preservation_config()

    def _get_preservation_config(self) -> dict:
        """Get preservation config from main config or use defaults."""
        risk_mgmt = self.config.get("risk_management", {})
        return risk_mgmt.get("capital_preservation", self.DEFAULT_CONFIG)

    def check_status(self) -> PreservationStatus:
        """Check if capital preservation mode should be active."""
        if not self.preservation_config.get("enabled", True):
            return PreservationStatus(active=False)

        triggers = self.preservation_config.get("triggers", {})
        actions_config = self.preservation_config.get("actions", {})

        trigger_reasons = []
        exit_conditions = []

        # Check drawdown trigger
        drawdown_threshold = triggers.get("drawdown_threshold_pct", 10.0)
        current_drawdown = self._get_current_drawdown()
        if current_drawdown >= drawdown_threshold:
            trigger_reasons.append(
                f"Drawdown ({current_drawdown:.1f}%) exceeds threshold ({drawdown_threshold:.1f}%)"
            )
            exit_conditions.append(
                f"Drawdown recovers below {drawdown_threshold:.1f}%"
            )

        # Check risk score trigger
        risk_threshold = triggers.get("risk_score_threshold", 40)
        current_risk_score = self._get_risk_score()
        if current_risk_score is not None and current_risk_score < risk_threshold:
            trigger_reasons.append(
                f"Risk score ({current_risk_score:.0f}) below threshold ({risk_threshold})"
            )
            exit_conditions.append(
                f"Risk score recovers above {risk_threshold}"
            )

        # Check bear market trigger
        if triggers.get("regime_bear_auto_enable", True):
            regime = get_market_regime()
            if regime == MarketRegime.BEAR:
                trigger_reasons.append(
                    "Bear market regime detected"
                )
                exit_conditions.append(
                    "Market regime changes to SIDEWAYS or BULL"
                )

        # Determine if active
        is_active = len(trigger_reasons) > 0

        if not is_active:
            return PreservationStatus(active=False)

        # Build actions
        actions_taken = []

        halt_buys = actions_config.get("halt_new_buys", True)
        if halt_buys:
            actions_taken.append(PreservationAction(
                name="Halt New Buys",
                description="No new positions will be opened"
            ))

        tighten_pct = actions_config.get("tighten_stops_pct", 5.0)
        if tighten_pct > 0:
            actions_taken.append(PreservationAction(
                name="Tighten Stops",
                description=f"Stop losses tightened by {tighten_pct:.1f}%",
                value=tighten_pct
            ))

        size_multiplier = actions_config.get("reduce_position_size_multiplier", 0.5)
        if size_multiplier < 1.0:
            actions_taken.append(PreservationAction(
                name="Reduce Position Size",
                description=f"New positions sized at {size_multiplier*100:.0f}% of normal",
                value=size_multiplier
            ))

        return PreservationStatus(
            active=True,
            trigger_reasons=trigger_reasons,
            actions_taken=actions_taken,
            exit_conditions=exit_conditions,
            halt_new_buys=halt_buys,
            stop_loss_tightening_pct=tighten_pct,
            position_size_multiplier=size_multiplier
        )

    def _get_current_drawdown(self) -> float:
        """Get current drawdown percentage."""
        try:
            scoreboard = get_risk_scoreboard()
            for c in scoreboard.components:
                if c.name == "Drawdown":
                    return c.value  # This is the drawdown percentage
            return 0.0
        except Exception:
            return 0.0

    def _get_risk_score(self) -> Optional[float]:
        """Get current overall risk score."""
        try:
            scoreboard = get_risk_scoreboard()
            return scoreboard.overall_score
        except Exception:
            return None

    def get_adjusted_stop_loss(self, current_price: float, original_stop: float) -> float:
        """
        Get tightened stop loss when preservation mode is active.

        Args:
            current_price: Current stock price
            original_stop: Original stop loss price

        Returns:
            Adjusted stop loss (higher = tighter)
        """
        status = self.check_status()

        if not status.active or status.stop_loss_tightening_pct <= 0:
            return original_stop

        # Calculate tightened stop
        # If price is $100, original stop is $92 (8% below)
        # Tightening by 5% means new stop is $95 (5% below)
        tighten_pct = status.stop_loss_tightening_pct
        tightened_stop = current_price * (1 - tighten_pct / 100)

        # Only tighten if it raises the stop (more protective)
        return max(original_stop, tightened_stop)

    def get_position_size_multiplier(self) -> float:
        """Get position size multiplier (1.0 = normal, 0.5 = half)."""
        status = self.check_status()

        if not status.active:
            return 1.0

        return status.position_size_multiplier

    def should_halt_buys(self) -> bool:
        """Check if new buys should be halted."""
        status = self.check_status()
        return status.active and status.halt_new_buys


def get_preservation_status() -> PreservationStatus:
    """Get current capital preservation status."""
    manager = CapitalPreservationManager()
    return manager.check_status()


def should_halt_buys() -> bool:
    """Quick check if buys should be halted."""
    manager = CapitalPreservationManager()
    return manager.should_halt_buys()


def get_position_size_multiplier() -> float:
    """Get current position size multiplier."""
    manager = CapitalPreservationManager()
    return manager.get_position_size_multiplier()


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n─── Capital Preservation Status ───\n")

    status = get_preservation_status()

    if status.active:
        print("⚠️  CAPITAL PRESERVATION MODE: ACTIVE")
        print()
        print("Trigger Reasons:")
        for reason in status.trigger_reasons:
            print(f"  - {reason}")
        print()
        print("Actions Taken:")
        for action in status.actions_taken:
            print(f"  - {action.name}: {action.description}")
        print()
        print("Exit Conditions:")
        for condition in status.exit_conditions:
            print(f"  - {condition}")
        print()
        print(f"Halt New Buys: {status.halt_new_buys}")
        print(f"Stop Tightening: {status.stop_loss_tightening_pct}%")
        print(f"Position Size Multiplier: {status.position_size_multiplier}x")
    else:
        print("✅ Capital Preservation Mode: INACTIVE")
        print("   Portfolio operating normally")
