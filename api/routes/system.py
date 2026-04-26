"""System health and logs endpoints."""
import csv
import logging
from datetime import date as _date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

from log_parser import build_day_summary

router = APIRouter(prefix="/api/system")

CRON_LOGS_DIR = Path(__file__).parent.parent.parent / "cron" / "logs"
PORTFOLIOS_DIR = Path(__file__).parent.parent.parent / "data" / "portfolios"

_MISSING_JOB = {"status": "missing", "ok": 0, "failed": 0, "ran_at": None}

def _empty_day(date_str: str) -> dict:
    return {
        "date": date_str,
        "pipeline": {
            "scan": dict(_MISSING_JOB),
            "execute": {**_MISSING_JOB, "trades": 0},
            "update_midday": dict(_MISSING_JOB),
            "update_close": dict(_MISSING_JOB),
        },
        "watchdog_restarts": 0,
        "events": [],
    }


@router.get("/pipeline-health")
def pipeline_health():
    """Return latest pipeline execution status for all portfolios."""
    import json
    status_dir = Path(__file__).parent.parent.parent / "data" / "pipeline_status"
    if not status_dir.exists():
        return {"portfolios": [], "anomalies": []}

    results = []
    anomalies = []
    for f in sorted(status_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            results.append(data)
            # Check for anomalies
            if data.get("ai_mode") == "mechanical_fallback":
                anomalies.append(f"{data['portfolio_id']}: Claude fallback activated")
            if data.get("executed", {}).get("buys", 0) == 0 and data.get("proposed", {}).get("buys", 0) > 0:
                anomalies.append(f"{data['portfolio_id']}: all buys dropped")
        except Exception:
            pass

    return {"portfolios": results, "anomalies": anomalies}


@router.get("/logs")
def get_system_logs():
    """Return last 30 days of pipeline activity, newest first."""
    if not CRON_LOGS_DIR.exists():
        return {"days": [_empty_day(str(_date.today() - timedelta(days=i))) for i in range(30)]}

    days = []
    today = _date.today()
    for i in range(30):
        date_str = str(today - timedelta(days=i))
        try:
            day = build_day_summary(CRON_LOGS_DIR, PORTFOLIOS_DIR, date_str)
        except Exception as e:
            logging.warning("Failed to build day summary for %s: %s", date_str, e)
            day = _empty_day(date_str)
        days.append(day)
    return {"days": days}


# In-memory narrative cache: {date_str: {"result": response_dict, "cached_at": datetime}}
_narrative_cache: dict[str, dict] = {}
_NARRATIVE_CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_trades_for_date(date_str: str) -> list[dict]:
    """Get trade details across all portfolios for a given date."""
    trades = []
    if not PORTFOLIOS_DIR.exists():
        return trades
    for portfolio_dir in sorted(PORTFOLIOS_DIR.iterdir()):
        if not portfolio_dir.is_dir():
            continue
        csv_path = portfolio_dir / "transactions.csv"
        if not csv_path.exists():
            continue
        try:
            with csv_path.open() as f:
                for row in csv.DictReader(f):
                    if row.get("date", "").startswith(date_str):
                        trades.append({
                            "portfolio": portfolio_dir.name,
                            "ticker": row.get("ticker", ""),
                            "action": row.get("action", ""),
                            "price": row.get("price", ""),
                            "reason": row.get("reason", ""),
                        })
        except Exception as e:
            logging.warning("Failed to read transactions for %s: %s", portfolio_dir.name, e)
            continue
    return trades


def _get_pnl_snapshots(date_str: str) -> list[dict]:
    """Get P&L snapshot for each portfolio on a given date."""
    snapshots = []
    if not PORTFOLIOS_DIR.exists():
        return snapshots
    for portfolio_dir in sorted(PORTFOLIOS_DIR.iterdir()):
        if not portfolio_dir.is_dir():
            continue
        csv_path = portfolio_dir / "daily_snapshots.csv"
        if not csv_path.exists():
            continue
        try:
            with csv_path.open() as f:
                for row in csv.DictReader(f):
                    if row.get("date", "") == date_str:
                        snapshots.append({
                            "portfolio": portfolio_dir.name,
                            "total_equity": row.get("total_equity", ""),
                            "day_pnl": row.get("day_pnl", ""),
                            "day_pnl_pct": row.get("day_pnl_pct", ""),
                        })
        except Exception as e:
            logging.warning("Failed to read snapshots for %s: %s", portfolio_dir.name, e)
            continue
    return snapshots


def _build_narrative_prompt(
    date_str: str,
    day_summary: dict,
    trades: list[dict],
    pnl_snapshots: list[dict],
) -> str:
    pipeline = day_summary.get("pipeline", {})

    def _job_line(job: dict, label: str) -> str:
        if job.get("status") == "missing":
            return f"  {label}: did not run"
        ok = job.get("ok", 0)
        failed = job.get("failed", 0)
        trades_note = f", {job.get('trades', 0)} trades" if "trades" in job else ""
        status = "✓" if job.get("status") == "ok" else "✗"
        return f"  {label}: {status} {ok}/{ok+failed} portfolios ok{trades_note}"

    pipeline_lines = "\n".join([
        _job_line(pipeline.get("scan", {}), "SCAN (6:30 AM)"),
        _job_line(pipeline.get("execute", {}), "EXECUTE (9:35 AM)"),
        _job_line(pipeline.get("update_midday", {}), "UPDATE MIDDAY (12:00 PM)"),
        _job_line(pipeline.get("update_close", {}), "UPDATE CLOSE (4:15 PM)"),
        f"  API watchdog restarts: {day_summary.get('watchdog_restarts', 0)}",
    ])

    trade_lines = ""
    if trades:
        trade_lines = "\n".join(
            f"  {t['action']} {t['ticker']} in [{t['portfolio']}] @ ${t['price']} — reason: {t['reason']}"
            for t in trades
        )
    else:
        trade_lines = "  No trades today."

    pnl_lines = ""
    if pnl_snapshots:
        pnl_lines = "\n".join(
            f"  {s['portfolio']}: equity=${s['total_equity']}, day P&L=${s['day_pnl']} ({s['day_pnl_pct']}%)"
            for s in pnl_snapshots
        )
    else:
        pnl_lines = "  No P&L data available."

    return f"""You are the GScott trading system's daily analyst. Write a concise daily briefing for {date_str}.

## Pipeline Status
{pipeline_lines}

## Today's Trades
{trade_lines}

## Portfolio P&L
{pnl_lines}

---

Write a daily briefing covering:
1. What happened operationally — did the pipeline run cleanly, any issues?
2. Why trades were made — synthesize from the ticker/reason data above
3. Patterns emerging across portfolios today
4. Anything notable — failures, unusual activity, watchdog restarts

Be concise — 3–5 short paragraphs. Use plain text (no markdown headers). Write in second person ("your portfolios").
""".strip()


@router.get("/narrative")
def get_system_narrative(date: Optional[str] = None, regenerate: bool = False):
    """Generate (or return cached) Claude narrative for a given date.

    Query params:
      date: YYYY-MM-DD (defaults to today)
      regenerate: true to bypass 10-minute in-memory cache
    """
    from schema import CLAUDE_MODEL

    target_date = date or str(_date.today())

    if not regenerate and target_date in _narrative_cache:
        entry = _narrative_cache[target_date]
        age = (datetime.now() - entry["cached_at"]).total_seconds()
        if age < _NARRATIVE_CACHE_TTL_SECONDS:
            cached = dict(entry["result"])
            cached["cached"] = True
            return cached

    try:
        day_summary = build_day_summary(CRON_LOGS_DIR, PORTFOLIOS_DIR, target_date)
    except Exception as e:
        logging.warning("Failed to build day summary for narrative %s: %s", target_date, e)
        day_summary = _empty_day(target_date)

    trades = _get_trades_for_date(target_date)
    pnl_snapshots = _get_pnl_snapshots(target_date)
    prompt = _build_narrative_prompt(target_date, day_summary, trades, pnl_snapshots)

    try:
        import anthropic
        client = anthropic.Anthropic(timeout=60.0)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = message.content[0].text
    except Exception as e:
        logging.warning("Claude narrative call failed for %s: %s", target_date, e)
        return {
            "date": target_date,
            "narrative": None,
            "generated_at": datetime.now().isoformat(),
            "cached": False,
            "error": "narrative unavailable",
        }

    result = {
        "date": target_date,
        "narrative": narrative,
        "generated_at": datetime.now().isoformat(),
        "cached": False,
    }
    _narrative_cache[target_date] = {"result": result, "cached_at": datetime.now()}
    return result



@router.get("/model-comparison")
def model_comparison(attribution: str = "sell"):
    """Compare baseline (4.6) vs challenger (4.7) across active portfolios.

    attribution: "sell" (default) credits realized P&L to the SELL-cohort (the
        exit decision) and unrealized P&L to the BUY-cohort. "buy" credits all
        P&L to the BUY cohort."""
    import json
    from schema import MODEL_EXPERIMENT
    from portfolio_registry import list_portfolios

    if attribution not in ("sell", "buy"):
        attribution = "sell"

    baseline = MODEL_EXPERIMENT["baseline_model"]
    challenger = MODEL_EXPERIMENT["challenger_model"]
    switch_date = MODEL_EXPERIMENT["switch_date"]
    end_date = MODEL_EXPERIMENT["end_date"]

    # Exclude portfolios flagged as experiment replicas / side portfolios — they
    # have no counterpart in the other cohort and would skew the A/B.
    active_portfolios = [
        p.id for p in list_portfolios(active_only=True)
        if not p.exclude_from_aggregates
    ]

    # Load starting_capital for each portfolio for return% denominators
    starting_capital_by_pid: dict = {}
    for pid in active_portfolios:
        cfg_file = PORTFOLIOS_DIR / pid / "config.json"
        if cfg_file.exists():
            try:
                with open(cfg_file) as f:
                    starting_capital_by_pid[pid] = float(json.load(f).get("starting_capital", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                starting_capital_by_pid[pid] = 0.0
    total_starting_capital = sum(starting_capital_by_pid.values())

    def _cohort_for(row: dict) -> str:
        """Return 'baseline' or 'challenger' for a BUY or SELL row."""
        rationale_raw = row.get("trade_rationale", "") or ""
        if rationale_raw:
            try:
                tag = json.loads(rationale_raw).get("ai_model", "") or ""
                if tag == baseline:
                    return "baseline"
                if tag == challenger:
                    return "challenger"
            except (json.JSONDecodeError, AttributeError):
                pass
        # Fallback: date-based inference (pre-switch = baseline, post = challenger)
        date_str = str(row.get("date", ""))[:10]
        return "challenger" if date_str >= switch_date else "baseline"

    def _bucket():
        return {
            "buys": 0,
            "closed": 0,
            "open_lots": 0,          # lots with shares_remaining > 0
            "wins": 0,
            "losses": 0,
            "realized_pnl": 0.0,
            "total_pnl_pct_sum": 0.0,
            "holding_days_sum": 0,
            "capital_closed": 0.0,
            "unrealized_pnl": 0.0,
            "capital_open": 0.0,
        }

    cohorts = {"baseline": _bucket(), "challenger": _bucket()}
    # Per-portfolio, per-cohort buckets for breakdown view
    by_portfolio: dict = {
        pid: {"baseline": _bucket(), "challenger": _bucket()}
        for pid in active_portfolios
    }

    for pid in active_portfolios:
        tx_file = PORTFOLIOS_DIR / pid / "transactions.csv"
        if not tx_file.exists():
            continue
        with open(tx_file) as f:
            rows = list(csv.DictReader(f))

        # Build per-ticker BUY history (FIFO lot matching) to match SELL outcomes
        # to the BUY's model cohort
        lots_by_ticker: dict = {}
        for r in rows:
            ticker = r.get("ticker")
            action = r.get("action")
            try:
                shares = float(r.get("shares", 0) or 0)
                price = float(r.get("price", 0) or 0)
            except (TypeError, ValueError):
                continue

            if action == "BUY":
                buy_cohort = _cohort_for(r)
                cohorts[buy_cohort]["buys"] += 1
                by_portfolio[pid][buy_cohort]["buys"] += 1
                lots_by_ticker.setdefault(ticker, []).append({
                    "shares_initial": shares,
                    "shares_remaining": shares,
                    "price": price,
                    "date": str(r.get("date", ""))[:10],
                    "buy_cohort": buy_cohort,
                    "sell_matches": [],      # per-sell records: {cohort, pnl, cost_basis, closed_lot, date}
                })
            elif action == "SELL":
                lots = lots_by_ticker.get(ticker, [])
                remaining_sell = shares
                sell_date = str(r.get("date", ""))[:10]
                sell_cohort = _cohort_for(r)
                i = 0
                while remaining_sell > 0 and i < len(lots):
                    lot = lots[i]
                    if lot["shares_remaining"] <= 0:
                        i += 1
                        continue
                    matched = min(remaining_sell, lot["shares_remaining"])
                    pnl = (price - lot["price"]) * matched
                    matched_cost = lot["price"] * matched
                    lot["shares_remaining"] -= matched
                    lot_closed = (lot["shares_remaining"] == 0)
                    lot["sell_matches"].append({
                        "cohort": sell_cohort,
                        "pnl": pnl,
                        "cost_basis": matched_cost,
                        "closed_lot": lot_closed,
                        "date": sell_date,
                    })
                    remaining_sell -= matched
                    if not lot_closed:
                        break

        # Load current prices for unrealized P&L on open lots
        pos_file = PORTFOLIOS_DIR / pid / "positions.csv"
        current_prices: dict = {}
        if pos_file.exists():
            with open(pos_file) as f:
                for row in csv.DictReader(f):
                    t = row.get("ticker")
                    try:
                        cp = float(row.get("current_price", 0) or 0)
                    except (TypeError, ValueError):
                        cp = 0.0
                    if t and cp > 0:
                        current_prices[t] = cp

        # Aggregation pass — attribution mode determines who gets realized P&L:
        #   "buy":  all P&L (realized + unrealized) → lot's buy_cohort
        #   "sell": realized → whichever cohort executed the sell;
        #           unrealized → buy_cohort (only they've made a decision)
        for ticker, ticker_lots in lots_by_ticker.items():
            cp = current_prices.get(ticker, 0.0)
            for lot in ticker_lots:
                buy_cohort = lot["buy_cohort"]
                lot_realized = sum(m["pnl"] for m in lot["sell_matches"])
                sold_cost = sum(m["cost_basis"] for m in lot["sell_matches"])
                open_cost = lot["price"] * lot["shares_remaining"]
                lot_closed = (lot["shares_remaining"] == 0)

                # Unrealized always goes to buy_cohort (same in both modes)
                if lot["shares_remaining"] > 0 and cp > 0:
                    unrealized = (cp - lot["price"]) * lot["shares_remaining"]
                    for b in (cohorts[buy_cohort], by_portfolio[pid][buy_cohort]):
                        b["unrealized_pnl"] += unrealized
                        b["capital_open"] += open_cost

                # Open-lot count → buy_cohort (who originated it)
                if not lot_closed:
                    for b in (cohorts[buy_cohort], by_portfolio[pid][buy_cohort]):
                        b["open_lots"] += 1

                # Realized P&L attribution depends on mode
                if attribution == "buy":
                    # All realized P&L → buy_cohort; closed count → buy_cohort
                    if sold_cost > 0:
                        for b in (cohorts[buy_cohort], by_portfolio[pid][buy_cohort]):
                            b["realized_pnl"] += lot_realized
                            b["capital_closed"] += sold_cost
                    if lot_closed:
                        # Full lot close — lot-level win/loss, holding days, pnl_pct
                        lot_pnl_pct = (lot_realized / sold_cost * 100) if sold_cost > 0 else 0
                        last_sell_date = lot["sell_matches"][-1]["date"] if lot["sell_matches"] else None
                        try:
                            held = (datetime.fromisoformat(last_sell_date) -
                                    datetime.fromisoformat(lot["date"])).days if last_sell_date else 0
                        except (ValueError, TypeError):
                            held = 0
                        for b in (cohorts[buy_cohort], by_portfolio[pid][buy_cohort]):
                            b["closed"] += 1
                            b["total_pnl_pct_sum"] += lot_pnl_pct
                            b["holding_days_sum"] += held
                            if lot_realized > 0:
                                b["wins"] += 1
                            else:
                                b["losses"] += 1
                else:
                    # SELL mode: attribute each partial sell to its executing cohort
                    for match in lot["sell_matches"]:
                        sc = match["cohort"]
                        pnl = match["pnl"]
                        cb = match["cost_basis"]
                        for b in (cohorts[sc], by_portfolio[pid][sc]):
                            b["realized_pnl"] += pnl
                            b["capital_closed"] += cb
                    if lot_closed:
                        # Closer = cohort of the final sell match
                        closer = lot["sell_matches"][-1]["cohort"]
                        last_sell_date = lot["sell_matches"][-1]["date"]
                        # Lot-level pnl_pct uses aggregate lot realized over aggregate sold cost
                        lot_pnl_pct = (lot_realized / sold_cost * 100) if sold_cost > 0 else 0
                        try:
                            held = (datetime.fromisoformat(last_sell_date) -
                                    datetime.fromisoformat(lot["date"])).days
                        except (ValueError, TypeError):
                            held = 0
                        for b in (cohorts[closer], by_portfolio[pid][closer]):
                            b["closed"] += 1
                            b["total_pnl_pct_sum"] += lot_pnl_pct
                            b["holding_days_sum"] += held
                            if lot_realized > 0:
                                b["wins"] += 1
                            else:
                                b["losses"] += 1

    def _finalize(b: dict, starting_capital: float) -> dict:
        closed = b["closed"]
        total_pnl = b["realized_pnl"] + b["unrealized_pnl"]
        return {
            "buys": b["buys"],
            "closed": closed,
            "open": b["open_lots"],
            "wins": b["wins"],
            "losses": b["losses"],
            "win_rate_pct": round(b["wins"] / closed * 100, 1) if closed else 0.0,
            "realized_pnl": round(b["realized_pnl"], 2),
            "unrealized_pnl": round(b["unrealized_pnl"], 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / starting_capital * 100, 2) if starting_capital > 0 else 0.0,
            "avg_per_trade_return_pct": round(b["total_pnl_pct_sum"] / closed, 2) if closed else 0.0,
            "avg_holding_days": round(b["holding_days_sum"] / closed, 1) if closed else 0.0,
        }

    today = _date.today().isoformat()
    try:
        days_remaining = max(0, (datetime.fromisoformat(end_date) - datetime.fromisoformat(today)).days)
    except (ValueError, TypeError):
        days_remaining = 0

    per_portfolio = []
    for pid in active_portfolios:
        sc = starting_capital_by_pid.get(pid, 0.0)
        per_portfolio.append({
            "portfolio_id": pid,
            "starting_capital": sc,
            "baseline": _finalize(by_portfolio[pid]["baseline"], sc),
            "challenger": _finalize(by_portfolio[pid]["challenger"], sc),
        })

    return {
        "attribution": attribution,
        "baseline": {"model": baseline, **_finalize(cohorts["baseline"], total_starting_capital)},
        "challenger": {"model": challenger, **_finalize(cohorts["challenger"], total_starting_capital)},
        "switch_date": switch_date,
        "end_date": end_date,
        "days_remaining": days_remaining,
        "portfolios_included": active_portfolios,
        "total_starting_capital": total_starting_capital,
        "by_portfolio": per_portfolio,
    }
