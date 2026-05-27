"""Regime-conditional Bayesian weight learner.

Replaces factor_learning._apply_weight_adjustments. Tracks per-(factor, regime)
Beta posteriors over win rate in the top-30% vs bottom-30% score bucket. The
posterior-mean difference becomes a predictive-power signal, converted to
normalized [0.05, 0.40] weights. Sparse regimes (<15 trades) fall back to the
global posterior.

Per-portfolio caps read from config.json under learning.weight_cap / learning.weight_floor.
Defaults: cap=0.40, floor=0.05. Strategy-concentrated portfolios (MAX, MAX2) override
cap=0.55 so the learner can express momentum concentration without being flattened.

Audit trail at data/portfolios/{id}/weight_history.jsonl (one JSON line per update).
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

FACTORS = ["price_momentum", "earnings_growth", "quality", "volume", "volatility", "value_timing"]
REGIMES = ["BULL", "BEAR", "SIDEWAYS"]
PRIOR_ALPHA = 10.0
PRIOR_BETA = 10.0
SPARSE_THRESHOLD = 15
DEFAULT_WEIGHT_FLOOR = 0.05
DEFAULT_WEIGHT_CAP = 0.40
TOP_QUANTILE = 0.30
BOT_QUANTILE = 0.30


def _data_dir() -> Path:
    return Path(os.environ.get("MCR_DATA_DIR") or (Path(__file__).parent.parent / "data"))


def beta_posterior_mean(wins: int, losses: int,
                        alpha: float = PRIOR_ALPHA, beta: float = PRIOR_BETA) -> float:
    """Posterior mean of Beta(wins+alpha, losses+beta)."""
    return (wins + alpha) / (wins + losses + alpha + beta)


def compute_factor_power(trades: List[dict]) -> float:
    """Predictive power = posterior_mean(top-bucket win rate) - posterior_mean(bottom-bucket).

    `trades` is a list of {"score": int, "won": bool} for ONE factor across some
    set of trades (already filtered to the relevant regime).
    """
    if not trades:
        return 0.0
    scores = sorted(t["score"] for t in trades)
    n = len(scores)
    if n < 3:
        return 0.0
    top_cut = scores[int(n * (1 - TOP_QUANTILE))]
    bot_cut = scores[int(n * BOT_QUANTILE)]
    top = [t for t in trades if t["score"] >= top_cut]
    bot = [t for t in trades if t["score"] <= bot_cut]
    top_wins = sum(1 for t in top if t["won"])
    bot_wins = sum(1 for t in bot if t["won"])
    return (beta_posterior_mean(top_wins, len(top) - top_wins) -
            beta_posterior_mean(bot_wins, len(bot) - bot_wins))


def powers_to_weights(powers: Dict[str, float],
                       cap: float = DEFAULT_WEIGHT_CAP,
                       floor: float = DEFAULT_WEIGHT_FLOOR) -> Dict[str, float]:
    """Convert per-factor predictive powers into normalized weights in [floor, cap].

    Algorithm: shift powers to be non-negative (add 0.1 offset), normalize, then
    iteratively clamp+renormalize until both the floor and cap are satisfied.
    """
    if cap * len(FACTORS) < 1.0:
        raise ValueError(f"weight_cap {cap} too low: cap × {len(FACTORS)} factors must be ≥ 1.0")
    if floor * len(FACTORS) > 1.0:
        raise ValueError(f"weight_floor {floor} too high: floor × {len(FACTORS)} factors must be ≤ 1.0")
    shifted = {f: max(0.0, powers.get(f, 0.0)) + 0.1 for f in FACTORS}
    total = sum(shifted.values()) or 1.0
    weights = {f: shifted[f] / total for f in FACTORS}

    for _ in range(20):
        clamped = {f: max(floor, min(cap, w)) for f, w in weights.items()}
        excess = sum(weights[f] - clamped[f] for f in FACTORS)
        free = [f for f in FACTORS if floor < clamped[f] < cap]
        if abs(excess) < 1e-6 or not free:
            weights = clamped
            break
        share = excess / len(free)
        weights = {f: (clamped[f] + share if f in free else clamped[f]) for f in FACTORS}

    total = sum(weights.values())
    return {f: round(weights[f] / total, 4) for f in FACTORS}


def _read_portfolio_caps(portfolio_id: str) -> tuple:
    """Return (cap, floor) for this portfolio, falling back to defaults."""
    pdir = _data_dir() / "portfolios" / portfolio_id
    cfg_file = pdir / "config.json"
    if not cfg_file.exists():
        return DEFAULT_WEIGHT_CAP, DEFAULT_WEIGHT_FLOOR
    try:
        cfg = json.loads(cfg_file.read_text())
    except (json.JSONDecodeError, OSError):
        return DEFAULT_WEIGHT_CAP, DEFAULT_WEIGHT_FLOOR
    learning = cfg.get("learning", {}) or {}
    cap = float(learning.get("weight_cap", DEFAULT_WEIGHT_CAP))
    floor = float(learning.get("weight_floor", DEFAULT_WEIGHT_FLOOR))
    return cap, floor


def _load_closed_trades(portfolio_id: str) -> List[dict]:
    """Return [{buy_id, ticker, regime, factor_scores: {...}, won: bool, pnl_pct: float}]."""
    pdir = _data_dir() / "portfolios" / portfolio_id
    tx_file, pm_file = pdir / "transactions.csv", pdir / "post_mortems.csv"
    if not tx_file.exists() or not pm_file.exists():
        return []
    try:
        tx = pd.read_csv(tx_file, dtype=str)
        pm = pd.read_csv(pm_file, dtype=str)
    except Exception:
        return []
    if tx.empty or pm.empty:
        return []

    buys = tx[tx["action"] == "BUY"].set_index("transaction_id", drop=False)
    out: List[dict] = []
    for _, row in pm.iterrows():
        buy_id = row.get("buy_transaction_id", "")
        if buy_id not in buys.index:
            continue
        buy = buys.loc[buy_id]
        try:
            scores_raw = buy["factor_scores"]
            scores = json.loads(scores_raw) if scores_raw and str(scores_raw).strip() not in ("{}", "") else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if not scores:
            continue
        out.append({
            "buy_id": buy_id, "ticker": row["ticker"],
            "regime": row.get("regime_at_entry") or buy.get("regime_at_entry") or "UNKNOWN",
            "factor_scores": {k: int(float(v)) for k, v in scores.items() if v not in (None, "")},
            "won": float(row.get("pnl_pct") or 0) >= 0,
            "pnl_pct": float(row.get("pnl_pct") or 0),
        })
    return out


def learn_weights_for_regime(portfolio_id: str, regime: str,
                              closed_trades: Optional[List[dict]] = None,
                              cap: Optional[float] = None,
                              floor: Optional[float] = None) -> Dict[str, float]:
    """Compute weights for one regime. Falls back to global posterior if sparse."""
    if closed_trades is None:
        closed_trades = _load_closed_trades(portfolio_id)
    if cap is None or floor is None:
        _cap, _floor = _read_portfolio_caps(portfolio_id)
        cap = cap if cap is not None else _cap
        floor = floor if floor is not None else _floor
    in_regime = [t for t in closed_trades if t["regime"] == regime]
    pool = in_regime if len(in_regime) >= SPARSE_THRESHOLD else closed_trades

    powers: Dict[str, float] = {}
    for f in FACTORS:
        f_trades = []
        for t in pool:
            scores = t["factor_scores"]
            if isinstance(scores, str):
                try:
                    scores = json.loads(scores)
                except (json.JSONDecodeError, TypeError):
                    continue
            if f in scores:
                f_trades.append({"score": scores[f], "won": t["won"]})
        powers[f] = compute_factor_power(f_trades)
    return powers_to_weights(powers, cap=cap, floor=floor)


def update_weights_for_portfolio(portfolio_id: str) -> bool:
    """Recompute regime-conditional weights and persist to config.json. Append audit.

    Returns False if too few closed trades (per config.learning.min_trades_for_adjustment).
    Returns True on successful update.
    """
    pdir = _data_dir() / "portfolios" / portfolio_id
    cfg_file = pdir / "config.json"
    if not cfg_file.exists():
        return False
    cfg = json.loads(cfg_file.read_text())
    learning = cfg.get("learning", {}) or {}
    min_trades = learning.get("min_trades_for_adjustment", 10)
    cap = float(learning.get("weight_cap", DEFAULT_WEIGHT_CAP))
    floor = float(learning.get("weight_floor", DEFAULT_WEIGHT_FLOOR))
    closed = _load_closed_trades(portfolio_id)
    if len(closed) < min_trades:
        return False

    regime_weights = {r: learn_weights_for_regime(portfolio_id, r, closed, cap=cap, floor=floor)
                      for r in REGIMES}
    default_weights = learn_weights_for_regime(portfolio_id, "GLOBAL_FORCED_FALLBACK", closed, cap=cap, floor=floor)

    scoring = cfg.setdefault("scoring", {})
    scoring["default_weights"] = default_weights
    scoring["regime_weights"] = regime_weights
    cfg_file.write_text(json.dumps(cfg, indent=2))

    audit_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "portfolio_id": portfolio_id,
        "n_closed_trades": len(closed),
        "weight_cap": cap,
        "weight_floor": floor,
        "default_weights": default_weights,
        "regime_weights": regime_weights,
        "regime_counts": {r: sum(1 for t in closed if t["regime"] == r) for r in REGIMES},
    }
    audit_file = pdir / "weight_history.jsonl"
    with audit_file.open("a") as f:
        f.write(json.dumps(audit_entry) + "\n")
    return True
