#!/usr/bin/env python3
"""
Risk Manager Module for MicroCapRebuilder.

Provides:
- Stop loss checking
- Take profit checking
- Volatility-adjusted position sizing
- Portfolio limit enforcement
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from schema import Action, Reason

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"
POSITIONS_FILE = DATA_DIR / "positions.csv"


@dataclass
class SellSignal:
    """Represents a signal to sell a position."""
    ticker: str
    shares: int
    reason: str  # STOP_LOSS, TAKE_PROFIT, MANUAL
    trigger_price: float
    current_price: float


def load_config() -> dict:
    """Load configuration from config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "starting_capital": 5000.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "max_positions": 15,
        "default_stop_loss_pct": 8.0,
        "default_take_profit_pct": 20.0,
        "volatility_lookback_days": 20,
    }


class RiskManager:
    """Manages risk for the portfolio."""

    def __init__(self):
        self.config = load_config()

    def check_stop_losses(
        self, positions_df: pd.DataFrame, current_prices: dict
    ) -> List[SellSignal]:
        """
        Check all positions for stop loss triggers.

        Args:
            positions_df: DataFrame with position data
            current_prices: Dict mapping ticker -> current price

        Returns:
            List of SellSignal objects for positions that hit stop loss
        """
        signals = []

        for _, row in positions_df.iterrows():
            ticker = row["ticker"]
            shares = int(row["shares"])
            stop_loss = row.get("stop_loss")

            # Skip if no stop loss set
            if pd.isna(stop_loss) or stop_loss == "" or stop_loss == 0:
                continue

            stop_loss = float(stop_loss)
            current_price = current_prices.get(ticker)

            if current_price is None:
                continue

            # Trigger if current price falls below stop loss
            if current_price <= stop_loss:
                signals.append(SellSignal(
                    ticker=ticker,
                    shares=shares,
                    reason=Reason.STOP_LOSS,
                    trigger_price=stop_loss,
                    current_price=current_price,
                ))

        return signals

    def check_take_profits(
        self, positions_df: pd.DataFrame, current_prices: dict
    ) -> List[SellSignal]:
        """
        Check all positions for take profit triggers.

        Args:
            positions_df: DataFrame with position data
            current_prices: Dict mapping ticker -> current price

        Returns:
            List of SellSignal objects for positions that hit take profit
        """
        signals = []

        for _, row in positions_df.iterrows():
            ticker = row["ticker"]
            shares = int(row["shares"])
            take_profit = row.get("take_profit")

            # Skip if no take profit set
            if pd.isna(take_profit) or take_profit == "" or take_profit == 0:
                continue

            take_profit = float(take_profit)
            current_price = current_prices.get(ticker)

            if current_price is None:
                continue

            # Trigger if current price rises above take profit
            if current_price >= take_profit:
                signals.append(SellSignal(
                    ticker=ticker,
                    shares=shares,
                    reason=Reason.TAKE_PROFIT,
                    trigger_price=take_profit,
                    current_price=current_price,
                ))

        return signals

    def calculate_stop_loss_price(self, entry_price: float) -> float:
        """
        Calculate stop loss price based on config percentage.

        Args:
            entry_price: The entry price of the position

        Returns:
            Stop loss price
        """
        stop_pct = self.config.get("default_stop_loss_pct", 8.0) / 100
        return round(entry_price * (1 - stop_pct), 2)

    def calculate_take_profit_price(self, entry_price: float) -> float:
        """
        Calculate take profit price based on config percentage.

        Args:
            entry_price: The entry price of the position

        Returns:
            Take profit price
        """
        take_pct = self.config.get("default_take_profit_pct", 20.0) / 100
        return round(entry_price * (1 + take_pct), 2)

    def calculate_position_size(
        self,
        price: float,
        cash: float,
        volatility: Optional[float] = None,
    ) -> int:
        """
        Calculate position size based on risk parameters.

        Args:
            price: Current price per share
            cash: Available cash
            volatility: Optional volatility measure (ATR as % of price)

        Returns:
            Number of shares to buy
        """
        risk_pct = self.config.get("risk_per_trade_pct", 10.0) / 100
        risk_capital = cash * risk_pct

        # Adjust for volatility if provided (higher volatility = smaller position)
        if volatility is not None and volatility > 0:
            # Scale down position for volatile stocks
            # If volatility is 5%, use normal size
            # If volatility is 10%, use half size
            volatility_adjustment = min(1.0, 0.05 / volatility)
            risk_capital *= volatility_adjustment

        shares = int(risk_capital // price)
        return max(0, shares)

    def check_portfolio_limits(
        self,
        positions_df: pd.DataFrame,
        new_ticker: str,
        new_value: float,
        total_equity: float,
    ) -> tuple[bool, str]:
        """
        Check if adding a new position would violate portfolio limits.

        Args:
            positions_df: Current positions DataFrame
            new_ticker: Ticker of new position
            new_value: Value of new position
            total_equity: Total portfolio equity

        Returns:
            Tuple of (is_allowed, reason)
        """
        max_positions = self.config.get("max_positions", 15)
        max_position_pct = self.config.get("max_position_pct", 15.0) / 100

        # Check max positions
        current_positions = len(positions_df)
        if current_positions >= max_positions:
            return False, f"Max positions limit ({max_positions}) reached"

        # Check position concentration
        if total_equity > 0:
            position_pct = new_value / total_equity
            if position_pct > max_position_pct:
                return False, f"Position would exceed {max_position_pct*100:.0f}% concentration limit"

        # Check if already holding this ticker
        if new_ticker in positions_df["ticker"].values:
            existing_value = positions_df[
                positions_df["ticker"] == new_ticker
            ]["market_value"].sum()
            combined_pct = (existing_value + new_value) / total_equity
            if combined_pct > max_position_pct:
                return False, f"Combined position would exceed {max_position_pct*100:.0f}% limit"

        return True, "OK"

    def get_all_sell_signals(
        self, positions_df: pd.DataFrame, current_prices: dict
    ) -> List[SellSignal]:
        """
        Get all sell signals (stop loss and take profit combined).

        Args:
            positions_df: DataFrame with position data
            current_prices: Dict mapping ticker -> current price

        Returns:
            Combined list of all sell signals
        """
        stop_loss_signals = self.check_stop_losses(positions_df, current_prices)
        take_profit_signals = self.check_take_profits(positions_df, current_prices)

        return stop_loss_signals + take_profit_signals
