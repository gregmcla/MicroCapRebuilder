"""Control endpoints for mode toggling and emergency actions."""

from fastapi import APIRouter, HTTPException
from datetime import date

from data_files import is_paper_mode, set_paper_mode
from portfolio_state import (
    load_portfolio_state,
    save_transactions_batch,
    remove_position,
    save_positions,
)
from post_mortem import save_post_mortem

router = APIRouter(prefix="/api/{portfolio_id}")


@router.get("/mode")
def get_mode(portfolio_id: str):
    """Get current mode (paper/live)."""
    return {"paper_mode": is_paper_mode(portfolio_id)}


@router.post("/mode/toggle")
def toggle_mode(portfolio_id: str):
    """Toggle between paper and live mode."""
    current = is_paper_mode(portfolio_id)
    new_mode = not current
    set_paper_mode(new_mode, portfolio_id)

    return {
        "paper_mode": new_mode,
        "message": f"Switched to {'PAPER' if new_mode else 'LIVE'} mode"
    }


@router.post("/sell/{ticker}")
def sell_position(portfolio_id: str, ticker: str):
    """Manually sell a single position at market price."""
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)

    if state.positions.empty:
        raise HTTPException(status_code=400, detail="No positions")

    pos_row = state.positions[state.positions["ticker"] == ticker]
    if pos_row.empty:
        raise HTTPException(status_code=404, detail=f"No position found for {ticker}")

    pos = pos_row.iloc[0]
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
        "reason": "MANUAL",
        "factor_scores": "{}",
        "regime_at_entry": "",
    }

    state = save_transactions_batch(state, [transaction])
    state = remove_position(state, ticker)
    save_positions(state)

    # Post-mortem (non-fatal)
    try:
        save_post_mortem(ticker)
    except Exception as e:
        print(f"Failed to generate post-mortem for {ticker}: {e}")

    return {
        "ticker": ticker,
        "shares": shares,
        "price": round(price, 2),
        "total_value": round(total_value, 2),
        "unrealized_pnl": round(float(pos["unrealized_pnl"]), 2),
        "unrealized_pnl_pct": round(float(pos["unrealized_pnl_pct"]), 2),
        "message": f"Sold {shares} shares of {ticker} @ ${price:.2f} for ${total_value:,.2f}",
    }


@router.post("/close-all")
def close_all(portfolio_id: str):
    """Emergency close all positions at market price."""
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)

    if state.positions.empty:
        raise HTTPException(status_code=400, detail="No positions to close")

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

    state = save_transactions_batch(state, transactions)

    for pos_info in closed_positions:
        state = remove_position(state, pos_info["ticker"])

    save_positions(state)

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
