"""Control endpoints for mode toggling and emergency actions."""

from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path
from datetime import date

# Add scripts dir to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from data_files import is_paper_mode, set_paper_mode
from portfolio_state import (
    load_portfolio_state,
    save_transactions_batch,
    remove_position,
    save_positions,
)
from post_mortem import save_post_mortem

router = APIRouter(prefix="/api")


@router.get("/mode")
def get_mode():
    """Get current mode (paper/live)."""
    return {"paper_mode": is_paper_mode()}


@router.post("/mode/toggle")
def toggle_mode():
    """Toggle between paper and live mode."""
    current = is_paper_mode()
    new_mode = not current
    set_paper_mode(new_mode)

    return {
        "paper_mode": new_mode,
        "message": f"Switched to {'PAPER' if new_mode else 'LIVE'} mode"
    }


@router.post("/close-all")
def close_all():
    """Emergency close all positions at market price."""
    # Load state with fresh prices
    state = load_portfolio_state(fetch_prices=True)

    if state.positions.empty:
        raise HTTPException(status_code=400, detail="No positions to close")

    # Build SELL transactions for all positions
    transactions = []
    closed_positions = []

    for _, pos in state.positions.iterrows():
        ticker = pos["ticker"]
        shares = int(pos["shares"])
        price = float(pos["current_price"])
        total_value = shares * price

        transaction = {
            "transaction_id": f"SELL_{ticker}_{date.today().isoformat()}",
            "date": date.today().isoformat(),
            "ticker": ticker,
            "action": "SELL",
            "shares": shares,
            "price": round(price, 2),
            "total_value": round(total_value, 2),
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "reason": "EMERGENCY_CLOSE",
            "factor_scores": "{}",
            "regime_at_entry": "",
        }
        transactions.append(transaction)

        closed_positions.append({
            "ticker": ticker,
            "shares": shares,
            "price": round(price, 2),
            "total_value": round(total_value, 2),
            "unrealized_pnl": round(float(pos["unrealized_pnl"]), 2),
            "unrealized_pnl_pct": round(float(pos["unrealized_pnl_pct"]), 2),
        })

    # Save transactions (this updates cash)
    state = save_transactions_batch(state, transactions)

    # Remove all positions
    for pos_info in closed_positions:
        state = remove_position(state, pos_info["ticker"])

    # Persist positions
    save_positions(state)

    # Generate post-mortems (non-fatal if it fails)
    for pos_info in closed_positions:
        try:
            save_post_mortem(pos_info["ticker"])
        except Exception as e:
            print(f"Failed to generate post-mortem for {pos_info['ticker']}: {e}")

    total_value = sum(p["total_value"] for p in closed_positions)
    total_pnl = sum(p["unrealized_pnl"] for p in closed_positions)

    return {
        "closed": len(closed_positions),
        "positions": closed_positions,
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "message": f"Emergency close: sold {len(closed_positions)} positions for ${total_value:,.2f}"
    }
