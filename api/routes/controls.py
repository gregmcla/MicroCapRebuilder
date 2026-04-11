"""Control endpoints for mode toggling and emergency actions."""

import math
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

from data_files import is_paper_mode, set_paper_mode, load_config
from portfolio_state import (
    load_portfolio_state,
    save_transactions_batch,
    remove_position,
    reduce_position,
    save_positions,
    update_position,
)
from post_mortem import save_post_mortem, PostMortemAnalyzer


class SellRequest(BaseModel):
    shares: Optional[int] = None  # None = sell all


class BuyRequest(BaseModel):
    ticker: str
    shares: int
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

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
def sell_position(portfolio_id: str, ticker: str, body: SellRequest = SellRequest()):
    """Manually sell a position (full or partial) at market price."""
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)

    if state.positions.empty:
        raise HTTPException(status_code=400, detail="No positions")

    pos_row = state.positions[state.positions["ticker"] == ticker]
    if pos_row.empty:
        raise HTTPException(status_code=404, detail=f"No position found for {ticker}")

    pos = pos_row.iloc[0]
    total_shares = int(pos["shares"])
    sell_shares = body.shares if body.shares is not None else total_shares
    is_partial = sell_shares < total_shares

    if sell_shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be positive")
    if sell_shares > total_shares:
        raise HTTPException(status_code=400, detail=f"Cannot sell {sell_shares} shares, only hold {total_shares}")

    price = float(pos["current_price"])
    total_value = sell_shares * price
    avg_cost = float(pos["avg_cost_basis"])
    pnl = sell_shares * (price - avg_cost)
    pnl_pct = (price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0

    transaction = {
        "transaction_id": f"SELL_{ticker}_{date.today().isoformat()}",
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "ticker": ticker,
        "action": "SELL",
        "shares": sell_shares,
        "price": round(price, 2),
        "total_value": round(total_value, 2),
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "reason": "MANUAL",
        "factor_scores": "{}",
        "regime_at_entry": "",
    }

    state = save_transactions_batch(state, [transaction])

    if is_partial:
        state = reduce_position(state, ticker, sell_shares)
    else:
        state = remove_position(state, ticker)

    save_positions(state)

    # Post-mortem (non-fatal, only on full exit)
    if not is_partial:
        try:
            buy_txns = state.transactions[
                (state.transactions["ticker"] == ticker) &
                (state.transactions["action"] == "BUY")
            ]
            if not buy_txns.empty:
                analyzer = PostMortemAnalyzer()
                pm = analyzer.analyze_trade(transaction, buy_txns.iloc[-1].to_dict(), "UNKNOWN")
                save_post_mortem(pm, portfolio_id=portfolio_id)
        except Exception as e:
            print(f"Failed to generate post-mortem for {ticker}: {e}")

    label = f"Sold {sell_shares} of {total_shares} shares" if is_partial else f"Sold {sell_shares} shares"
    return {
        "ticker": ticker,
        "shares": sell_shares,
        "total_shares": total_shares,
        "remaining_shares": total_shares - sell_shares if is_partial else 0,
        "price": round(price, 2),
        "total_value": round(total_value, 2),
        "unrealized_pnl": round(pnl, 2),
        "unrealized_pnl_pct": round(pnl_pct, 2),
        "partial": is_partial,
        "message": f"{label} of {ticker} @ ${price:.2f} for ${total_value:,.2f}",
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

    analyzer = PostMortemAnalyzer()
    for pos_info, tx in zip(closed_positions, transactions):
        try:
            buy_txns = state.transactions[
                (state.transactions["ticker"] == pos_info["ticker"]) &
                (state.transactions["action"] == "BUY")
            ]
            if not buy_txns.empty:
                pm = analyzer.analyze_trade(tx, buy_txns.iloc[-1].to_dict(), "UNKNOWN")
                save_post_mortem(pm, portfolio_id=portfolio_id)
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


@router.get("/quote/{ticker}")
def get_quote(portfolio_id: str, ticker: str):
    """Get live price + portfolio risk defaults for a ticker."""
    from portfolio_state import fetch_prices_batch
    import yfinance as yf
    from threading import Thread

    prices, failures, prev_closes = fetch_prices_batch([ticker])
    if ticker in failures or ticker not in prices:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {ticker}")

    price = prices[ticker]
    prev_close = prev_closes.get(ticker)

    info_result = {}
    def fetch_info():
        try:
            data = yf.Ticker(ticker).info
            info_result["name"] = data.get("shortName", data.get("longName", ticker))
            info_result["sector"] = data.get("sector", "")
        except Exception:
            pass

    t = Thread(target=fetch_info)
    t.start()
    t.join(timeout=5)

    config = load_config(portfolio_id)
    risk_pct = config.get("risk_per_trade_pct", 8.0)
    stop_pct = config.get("default_stop_loss_pct", 7.0)
    take_pct = config.get("default_take_profit_pct", 20.0)

    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    cash = state.cash
    suggested = math.floor(cash * risk_pct / 100 / price) if price > 0 else 0

    return {
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "name": info_result.get("name", ticker),
        "sector": info_result.get("sector", ""),
        "prev_close": round(prev_close, 2) if prev_close else None,
        "available_cash": round(cash, 2),
        "risk_per_trade_pct": risk_pct,
        "default_stop_loss_pct": stop_pct,
        "default_take_profit_pct": take_pct,
        "suggested_shares": suggested,
    }


@router.post("/buy")
def buy_position(portfolio_id: str, body: BuyRequest):
    """Manually buy a position at market price."""
    from portfolio_state import fetch_prices_batch

    if body.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be positive")

    prices, failures, _ = fetch_prices_batch([body.ticker])
    if body.ticker in failures or body.ticker not in prices:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {body.ticker}")

    price = prices[body.ticker]
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    total_cost = body.shares * price

    if total_cost > state.cash + 0.01:
        raise HTTPException(status_code=400, detail=f"Insufficient cash: need ${total_cost:,.2f}, have ${state.cash:,.2f}")

    config = load_config(portfolio_id)
    stop_pct = body.stop_loss_pct if body.stop_loss_pct is not None else config.get("default_stop_loss_pct", 7.0)
    take_pct = body.take_profit_pct if body.take_profit_pct is not None else config.get("default_take_profit_pct", 20.0)
    stop_loss = round(price * (1 - stop_pct / 100), 2)
    take_profit = round(price * (1 + take_pct / 100), 2)

    transaction = {
        "transaction_id": f"BUY_{body.ticker}_{date.today().isoformat()}",
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "ticker": body.ticker,
        "action": "BUY",
        "shares": body.shares,
        "price": round(price, 2),
        "total_value": round(total_cost, 2),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reason": "MANUAL",
        "factor_scores": "{}",
        "regime_at_entry": "",
    }

    state = save_transactions_batch(state, [transaction])
    state = update_position(state, body.ticker, body.shares, price, stop_loss, take_profit)
    save_positions(state)

    return {
        "ticker": body.ticker,
        "shares": body.shares,
        "price": round(price, 2),
        "total_value": round(total_cost, 2),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "remaining_cash": round(state.cash, 2),
        "message": f"Bought {body.shares} shares of {body.ticker} @ ${price:.2f} for ${total_cost:,.2f}",
    }
