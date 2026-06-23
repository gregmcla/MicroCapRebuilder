#!/usr/bin/env python3
"""
Strategy DNA Genome (Feature #16) — structured 8-axis representation of a
portfolio's strategy, computed two ways:

  STATED   — derived from config knobs the user/AI set at creation
  MEASURED — derived from observed behavior across the full transaction
             + post-mortem + weight-history history (configurable window)

Each axis is normalized to 0-100. Drift = stated - measured. The killer
features built on this:
  - Overlay radar: render stated as dashed outline, measured as filled polygon
  - Cluster map: 2D PCA scatter across all portfolios reveals duplicates and
    unexplored corners of strategy-space

Axis normalizers are heuristics. Each is documented inline with its formula
so the choices are auditable and tweakable. PCA uses numpy SVD (no
sklearn dependency).
"""

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


_DATA_DIR = Path(__file__).parent.parent / "data"


# ─── Typed schema ────────────────────────────────────────────────────────────

# Canonical axis ordering — used for serialization, PCA matrix layout, and
# render ordering on the radar. Changing this is a breaking change.
AXES = [
    "time_horizon",
    "aggression",
    "concentration",
    "regime_sensitivity",
    "momentum_bias",
    "quality_bias",
    "catalyst_hunting",
    "drawdown_discipline",
]


@dataclass
class DnaGenome:
    time_horizon: float
    aggression: float
    concentration: float
    regime_sensitivity: float
    momentum_bias: float
    quality_bias: float
    catalyst_hunting: float
    drawdown_discipline: float
    confidence: float = 0.0      # 0-1; how complete the underlying data is
    window: str = "all"          # "all" or "90"

    def as_vector(self) -> list[float]:
        return [getattr(self, a) for a in AXES]


@dataclass
class DnaProfile:
    portfolio_id: str
    portfolio_name: str
    stated: DnaGenome
    measured: DnaGenome
    drift: dict = field(default_factory=dict)      # axis -> stated - measured
    drift_summary: str = ""


# ─── STATED DNA ──────────────────────────────────────────────────────────────
# Each axis reads from config and maps to 0-100. Formulas are heuristics with
# explicit cutoffs documented per axis.

def compute_stated_dna(config: dict) -> DnaGenome:
    """Read config knobs and produce a stated genome.

    Stated genome is always confident=1.0 (config is fully present by definition).
    """
    return DnaGenome(
        time_horizon=_stated_time_horizon(config),
        aggression=_stated_aggression(config),
        concentration=_stated_concentration(config),
        regime_sensitivity=_stated_regime_sensitivity(config),
        momentum_bias=_stated_momentum_bias(config),
        quality_bias=_stated_quality_bias(config),
        catalyst_hunting=_stated_catalyst_hunting(config),
        drawdown_discipline=_stated_drawdown_discipline(config),
        confidence=1.0,
        window="config",
    )


def _stated_time_horizon(config: dict) -> float:
    """Wider stops + targets imply longer intended holds.

    Heuristic: avg(stop_pct, target_pct/2) — a 7% stop / 20% target → 8.5
    composite → 30 score. A 15% stop / 50% target → 20 composite → 70 score.
    Clamped 0-100 via piecewise-linear.
    """
    stop_pct = float(config.get("default_stop_loss_pct", 7.0))
    target_pct = float(config.get("default_take_profit_pct", 20.0))
    composite = (stop_pct + target_pct / 2.0)
    # Map composite 5 → 10, 10 → 40, 20 → 80, 30+ → 95
    if composite <= 5: return 10.0
    if composite <= 10: return 10 + (composite - 5) * 6.0      # 10 → 40
    if composite <= 20: return 40 + (composite - 10) * 4.0     # 40 → 80
    return min(95.0, 80 + (composite - 20) * 1.5)


def _stated_aggression(config: dict) -> float:
    """risk_per_trade_pct (1-10 typical) + max_position_pct (5-25 typical)
    blended. Higher = more aggressive.

    Heuristic: risk*8 + position*2, clipped to 0-100.
    """
    rpp = float(config.get("risk_per_trade_pct", 5.0))
    mpp = float(config.get("max_position_pct", 10.0))
    return min(100.0, max(0.0, rpp * 8.0 + mpp * 2.0))


def _stated_concentration(config: dict) -> float:
    """Fewer positions + tighter top-3 limits = more concentrated.

    Inverse of max_positions on a log scale (2 pos → 95, 10 → 50, 50 → 10).
    Boosted by top3_limit_pct (40% → +0, 60%+ → +20).
    """
    max_pos = max(1, int(config.get("max_positions", 20) or 20))
    # Log map: max_positions 1=100, 5=75, 20=55, 50=40, 100=30
    base = 100.0 - min(90.0, 35.0 * math.log10(max_pos))
    top3 = float(config.get("enhanced_trading", {}).get("layer3", {}).get("top3_limit_pct", 45.0))
    boost = max(0.0, (top3 - 45.0) * 1.0)  # each pct above 45 = +1 score
    return min(100.0, base + boost)


def _stated_regime_sensitivity(config: dict) -> float:
    """How much do per-regime factor weights differ from each other?

    Compute the std-dev of each factor's BULL/BEAR/SIDEWAYS values, average
    across factors, scale to 0-100. Higher variance = more sensitive.
    """
    rw = config.get("scoring", {}).get("regime_weights")
    if not isinstance(rw, dict) or not rw:
        return 50.0  # neutral when no regime weights defined
    factors = set()
    for _r, weights in rw.items():
        if isinstance(weights, dict):
            factors.update(weights.keys())
    if not factors:
        return 50.0
    spreads: list[float] = []
    for f in factors:
        vals = [float(rw[r].get(f, 0) or 0) for r in rw if isinstance(rw[r], dict) and f in rw[r]]
        if len(vals) >= 2:
            spreads.append(float(np.std(vals)))
    if not spreads:
        return 50.0
    avg_spread = sum(spreads) / len(spreads)
    # Empirically: avg_spread of 0 → no sensitivity (10), 0.02 → moderate (50), 0.06+ → high (90)
    return min(100.0, 10 + avg_spread * 1333.0)


def _stated_momentum_bias(config: dict) -> float:
    """Share of total scoring weight assigned to price_momentum.

    A balanced 6-factor portfolio would have ~16.7% each = score 17. Heavy
    momentum portfolios push to 30%+ = score 60+. We rescale 0.10..0.40 → 10..90.
    """
    weights = config.get("scoring", {}).get("default_weights", {})
    if not isinstance(weights, dict) or not weights:
        return 17.0
    total = sum(float(v or 0) for v in weights.values()) or 1.0
    share = float(weights.get("price_momentum", 0) or 0) / total
    # 0.10 → 10, 0.16 → 50, 0.25 → 80, 0.40 → 95
    return min(95.0, max(0.0, (share - 0.10) * 333.0 + 10))


def _stated_quality_bias(config: dict) -> float:
    """Mirror of _stated_momentum_bias but for the `quality` factor."""
    weights = config.get("scoring", {}).get("default_weights", {})
    if not isinstance(weights, dict) or not weights:
        return 17.0
    total = sum(float(v or 0) for v in weights.values()) or 1.0
    share = float(weights.get("quality", 0) or 0) / total
    return min(95.0, max(0.0, (share - 0.10) * 333.0 + 10))


def _stated_catalyst_hunting(config: dict) -> float:
    """Catalyst-hunting portfolios typically have:
      - An AI-refinement prompt on the screener (e.g. "asymmetric catalysts")
      - Low market_cap_min (allows micro/small caps where catalysts move price)
      - Wide stops (catalysts produce volatility)

    Composite of those three.
    """
    universe = config.get("universe", {})
    screener = universe.get("sources", {}).get("screener") or universe.get("screener") or {}
    has_refinement = bool(screener.get("ai_refinement"))
    refinement_score = 60.0 if has_refinement else 30.0

    mcap_min = float(screener.get("market_cap_min", 50_000_000) or 50_000_000)
    # Lower min → more catalyst-friendly. <50M → +25, 50M-500M → +10, 500M+ → 0
    if mcap_min < 50_000_000:
        mcap_bonus = 25.0
    elif mcap_min < 500_000_000:
        mcap_bonus = 10.0
    else:
        mcap_bonus = 0.0

    stop_pct = float(config.get("default_stop_loss_pct", 7.0))
    stop_bonus = max(0.0, (stop_pct - 7.0) * 1.5)  # each pt above 7 = +1.5

    return min(100.0, refinement_score + mcap_bonus + stop_bonus)


def _stated_drawdown_discipline(config: dict) -> float:
    """Tight stops + low drawdown threshold = highly disciplined.

    Heuristic:
      - stop_loss_pct: 5% → +50 score, 10% → +20, 15% → 0 (tighter = more disciplined)
      - capital_preservation drawdown_threshold_pct: 5% → +30, 15% → 0
    """
    stop = float(config.get("default_stop_loss_pct", 7.0))
    stop_score = max(0.0, 70.0 - stop * 5.0)  # 5% → 45, 10% → 20, 15% → 0

    cp = config.get("risk_management", {}).get("capital_preservation", {})
    triggers = cp.get("triggers") if isinstance(cp, dict) else {}
    dd_threshold = float(triggers.get("drawdown_threshold_pct", 10.0) or 10.0) if isinstance(triggers, dict) else 10.0
    dd_score = max(0.0, 40.0 - dd_threshold * 2.0)  # 5% → 30, 15% → 10, 20%+ → 0

    return min(100.0, stop_score + dd_score)


# ─── MEASURED DNA ────────────────────────────────────────────────────────────
# Read observed behavior from post-mortems, daily snapshots, weight history,
# and transactions. Each axis has its own loader so a single missing source
# only degrades the affected axis, not the whole genome.

def compute_measured_dna(portfolio_id: str, window: str = "all") -> DnaGenome:
    """Derive a genome from observed behavior.

    Args:
        portfolio_id: portfolio to analyze
        window: "all" (default — uses every available row) or "90" (last 90d)

    Returns:
        DnaGenome with `confidence` set proportional to the data depth.
    """
    days = None if window == "all" else 90

    time_h, conf_th = _measured_time_horizon(portfolio_id, days)
    agg, conf_agg = _measured_aggression(portfolio_id, days)
    conc, conf_conc = _measured_concentration(portfolio_id)
    regime, conf_reg = _measured_regime_sensitivity(portfolio_id, days)
    mom, conf_mom = _measured_momentum_bias(portfolio_id)
    qual, conf_qual = _measured_quality_bias(portfolio_id)
    cat, conf_cat = _measured_catalyst_hunting(portfolio_id, days)
    disc, conf_disc = _measured_drawdown_discipline(portfolio_id, days)

    confs = [conf_th, conf_agg, conf_conc, conf_reg, conf_mom, conf_qual, conf_cat, conf_disc]
    overall_conf = sum(confs) / len(confs)

    return DnaGenome(
        time_horizon=time_h,
        aggression=agg,
        concentration=conc,
        regime_sensitivity=regime,
        momentum_bias=mom,
        quality_bias=qual,
        catalyst_hunting=cat,
        drawdown_discipline=disc,
        confidence=round(overall_conf, 2),
        window=window,
    )


def _measured_time_horizon(pid: str, days: Optional[int]) -> tuple[float, float]:
    """Avg holding_days across closed trades, log-normalized to 0-100.

    1 day → 0, 7 days → 30, 30 days → 60, 90 days → 80, 365+ days → 95.
    Confidence = min(1.0, n_trades / 10).
    """
    try:
        from post_mortem import load_post_mortems
        pms = load_post_mortems(portfolio_id=pid)
    except Exception:
        return 50.0, 0.0
    if not pms:
        return 50.0, 0.0
    if days is not None:
        from datetime import date as _date, timedelta as _td
        cutoff = (_date.today() - _td(days=days)).isoformat()
        pms = [p for p in pms if (p.close_date or "") >= cutoff]
    if not pms:
        return 50.0, 0.0
    holds = [int(p.holding_days) for p in pms if (p.holding_days or 0) > 0]
    if not holds:
        return 50.0, 0.0
    avg = sum(holds) / len(holds)
    score = min(95.0, 30.0 * math.log10(max(1.0, avg)))
    conf = min(1.0, len(holds) / 10.0)
    return score, conf


def _measured_aggression(pid: str, days: Optional[int]) -> tuple[float, float]:
    """Annualized volatility from daily_snapshots → score.

    10% vol → 20 score, 30% → 60, 60%+ → 95. Confidence scales with the
    number of snapshot rows.
    """
    try:
        from analytics import PortfolioAnalytics
        analyzer = PortfolioAnalytics(portfolio_id=pid)
        metrics = analyzer.calculate_all_metrics()
    except Exception:
        return 50.0, 0.0
    if metrics is None:
        return 50.0, 0.0
    vol = float(getattr(metrics, "volatility_annual", 0) or 0)  # decimal e.g. 0.30
    # 0.10 → 20, 0.30 → 60, 0.60+ → 95
    score = min(95.0, max(0.0, vol * 200.0))
    conf = min(1.0, int(getattr(metrics, "days_tracked", 0) or 0) / 30.0)
    return score, conf


def _measured_concentration(pid: str) -> tuple[float, float]:
    """Current top-3 concentration as % of equity → score.

    30% → 30, 60% → 65, 90%+ → 95. Confidence = 1.0 if any positions, else 0.
    """
    try:
        from data_files import get_positions_file
        import pandas as pd
        pos_file = get_positions_file(pid)
        if not pos_file.exists():
            return 50.0, 0.0
        df = pd.read_csv(pos_file)
        if df.empty or "market_value" not in df.columns:
            return 50.0, 0.0
        total = float(df["market_value"].sum())
        if total <= 0:
            return 50.0, 0.0
        top3 = float(df.nlargest(3, "market_value")["market_value"].sum())
        top3_pct = top3 / total * 100
    except Exception:
        return 50.0, 0.0
    score = min(95.0, max(10.0, top3_pct - 10.0))
    return score, 1.0


def _measured_regime_sensitivity(pid: str, days: Optional[int]) -> tuple[float, float]:
    """Variance of per-regime weight vectors across weight_history.jsonl.

    Reads each row's regime_weights, computes the same std-dev metric as
    the stated version. Higher = the system has *learned* to differentiate
    regimes over time.
    """
    path = _DATA_DIR / "portfolios" / pid / "weight_history.jsonl"
    if not path.exists():
        return 50.0, 0.0
    rows: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return 50.0, 0.0
    if days is not None and rows:
        from datetime import datetime as _dt, timedelta as _td
        cutoff = (_dt.now() - _td(days=days)).isoformat()
        rows = [r for r in rows if r.get("timestamp", "") >= cutoff]
    if not rows:
        return 50.0, 0.0
    # Use the most recent row's regime_weights — Bayesian learner converged state
    rw = rows[-1].get("regime_weights")
    if not isinstance(rw, dict):
        return 50.0, 0.2
    factors = set()
    for r, weights in rw.items():
        if isinstance(weights, dict):
            factors.update(weights.keys())
    if not factors:
        return 50.0, 0.2
    spreads: list[float] = []
    for f in factors:
        vals = [float(rw[r].get(f, 0) or 0) for r in rw if isinstance(rw[r], dict) and f in rw[r]]
        if len(vals) >= 2:
            spreads.append(float(np.std(vals)))
    if not spreads:
        return 50.0, 0.2
    avg_spread = sum(spreads) / len(spreads)
    score = min(100.0, 10 + avg_spread * 1333.0)
    conf = min(1.0, len(rows) / 5.0)
    return score, conf


def _measured_momentum_bias(pid: str) -> tuple[float, float]:
    """Latest Bayesian-learned weight on price_momentum, scaled like stated."""
    return _measured_factor_bias_share(pid, "price_momentum")


def _measured_quality_bias(pid: str) -> tuple[float, float]:
    return _measured_factor_bias_share(pid, "quality")


def _measured_factor_bias_share(pid: str, factor: str) -> tuple[float, float]:
    path = _DATA_DIR / "portfolios" / pid / "weight_history.jsonl"
    if not path.exists():
        return 17.0, 0.0
    try:
        last_row = None
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                last_row = json.loads(line)
            except Exception:
                continue
        if last_row is None:
            return 17.0, 0.0
        weights = last_row.get("default_weights") or {}
        total = sum(float(v or 0) for v in weights.values()) or 1.0
        share = float(weights.get(factor, 0) or 0) / total
        # 0.10 → 10, 0.16 → 50, 0.25 → 80, 0.40 → 95
        score = min(95.0, max(0.0, (share - 0.10) * 333.0 + 10))
        conf = 1.0
        return score, conf
    except Exception:
        return 17.0, 0.0


def _measured_catalyst_hunting(pid: str, days: Optional[int]) -> tuple[float, float]:
    """Two-component score:
      1. Avg market_cap_at_entry_m of BUYs (smaller = catalyst-hunting). <500M → +40, 500-5000M → +20, >5000M → +0
      2. Share of BUYs with heat_at_entry in {HOT, SPIKING}. 0% → +5, 50%+ → +50

    Both columns are populated by Phase 2 (write hook + backfill). Rows with
    empty values contribute 0 to their component (graceful degradation).
    """
    try:
        from data_files import get_transactions_file
        import pandas as pd
        tx_file = get_transactions_file(pid)
        if not tx_file.exists():
            return 30.0, 0.0
        df = pd.read_csv(tx_file)
    except Exception:
        return 30.0, 0.0
    if df.empty or "action" not in df.columns:
        return 30.0, 0.0
    buys = df[df["action"].astype(str).str.upper() == "BUY"].copy()
    if buys.empty:
        return 30.0, 0.0
    if days is not None:
        from datetime import date as _date, timedelta as _td
        cutoff = (_date.today() - _td(days=days)).isoformat()
        buys = buys[buys["date"].astype(str) >= cutoff]
    if buys.empty:
        return 30.0, 0.0

    # Component 1: avg market_cap_at_entry_m
    mcap_col = "market_cap_at_entry_m"
    cap_score = 0.0
    cap_conf = 0.0
    if mcap_col in buys.columns:
        caps = buys[mcap_col].dropna()
        caps = caps[caps.astype(str) != ""]
        if not caps.empty:
            try:
                caps = caps.astype(float)
                caps = caps[caps > 0]
            except Exception:
                caps = caps[:0]
            if not caps.empty:
                avg_cap = float(caps.mean())
                if avg_cap < 500:
                    cap_score = 40.0
                elif avg_cap < 5000:
                    cap_score = 20.0
                else:
                    cap_score = 5.0
                cap_conf = min(1.0, len(caps) / max(1, len(buys)))

    # Component 2: heat_at_entry HOT/SPIKING share
    heat_col = "heat_at_entry"
    heat_score = 5.0
    heat_conf = 0.0
    if heat_col in buys.columns:
        heats = buys[heat_col].astype(str).str.upper()
        heats = heats[heats.isin(["COLD", "WARM", "HOT", "SPIKING"])]
        if not heats.empty:
            hot_share = (heats.isin(["HOT", "SPIKING"])).mean()
            heat_score = min(50.0, 5.0 + hot_share * 90.0)
            heat_conf = min(1.0, len(heats) / max(1, len(buys)))

    score = min(100.0, cap_score + heat_score)
    conf = (cap_conf + heat_conf) / 2.0
    return score, conf


def _measured_drawdown_discipline(pid: str, days: Optional[int]) -> tuple[float, float]:
    """Lower avg(holding_days where exit=STOP_LOSS) / avg(where exit=TAKE_PROFIT) = more disciplined.

    A perfectly disciplined book cuts losers fast (low STOP holds) and lets
    winners run (higher TP holds). Ratio < 0.5 → 90 score; 1.0 → 50; >2.0 → 15.
    """
    try:
        from post_mortem import load_post_mortems
        pms = load_post_mortems(portfolio_id=pid)
    except Exception:
        return 50.0, 0.0
    if not pms:
        return 50.0, 0.0
    if days is not None:
        from datetime import date as _date, timedelta as _td
        cutoff = (_date.today() - _td(days=days)).isoformat()
        pms = [p for p in pms if (p.close_date or "") >= cutoff]
    stop_holds = [int(p.holding_days) for p in pms if (p.exit_reason or "").upper() == "STOP_LOSS" and (p.holding_days or 0) > 0]
    tp_holds = [int(p.holding_days) for p in pms if (p.exit_reason or "").upper() == "TAKE_PROFIT" and (p.holding_days or 0) > 0]
    if not stop_holds or not tp_holds:
        # Can't compute ratio — fall back to stop-loss rate alone
        if not pms:
            return 50.0, 0.0
        stop_rate = sum(1 for p in pms if (p.exit_reason or "").upper() == "STOP_LOSS") / len(pms)
        # Higher stop_rate = more disciplined in cutting losers
        score = 30.0 + stop_rate * 40.0
        return min(85.0, score), min(0.5, len(pms) / 20.0)

    ratio = (sum(stop_holds) / len(stop_holds)) / max(1.0, (sum(tp_holds) / len(tp_holds)))
    if ratio < 0.3:
        score = 95.0
    elif ratio < 0.5:
        score = 80.0
    elif ratio < 1.0:
        score = 60.0
    elif ratio < 2.0:
        score = 35.0
    else:
        score = 15.0
    conf = min(1.0, (len(stop_holds) + len(tp_holds)) / 10.0)
    return score, conf


# ─── Profile assembly + drift ────────────────────────────────────────────────

def compute_profile(portfolio_id: str, portfolio_name: str, config: dict, window: str = "all") -> DnaProfile:
    stated = compute_stated_dna(config)
    measured = compute_measured_dna(portfolio_id, window=window)
    drift = {a: round(getattr(stated, a) - getattr(measured, a), 1) for a in AXES}
    return DnaProfile(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        stated=stated,
        measured=measured,
        drift=drift,
        drift_summary=_build_drift_summary(stated, measured, drift),
    )


def _build_drift_summary(stated: DnaGenome, measured: DnaGenome, drift: dict) -> str:
    """Human-readable headline highlighting the 1-2 biggest disagreements."""
    sorted_drift = sorted(drift.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top = [kv for kv in sorted_drift if abs(kv[1]) >= 15.0][:2]
    if not top:
        return "Stated and measured DNA closely aligned"
    parts = []
    for axis, delta in top:
        stated_v = getattr(stated, axis)
        measured_v = getattr(measured, axis)
        direction = "overclaiming" if delta > 0 else "underclaiming"
        nice = axis.replace("_", " ")
        parts.append(f"{nice}: stated {stated_v:.0f}, measured {measured_v:.0f} — {direction}")
    return "; ".join(parts)


# ─── PCA ─────────────────────────────────────────────────────────────────────

def compute_cluster_pca(genomes: dict[str, DnaGenome]) -> dict:
    """Project N portfolios' 8-axis genomes into 2D via SVD-based PCA.

    Returns:
        {
          "portfolios": [{"id": ..., "x": ..., "y": ...}, ...],
          "variance_explained": [pc1, pc2],   # ratios summing to <= 1
          "axis_loadings": {axis: [pc1_load, pc2_load], ...}  # for axis-arrow overlays
        }

    With only N≈7 portfolios in 8 dimensions, PCA is qualitative not statistical.
    Used for the cluster-map UI; do NOT use as a statistical claim.
    """
    if not genomes:
        return {"portfolios": [], "variance_explained": [0.0, 0.0], "axis_loadings": {}}

    ids = list(genomes.keys())
    X = np.array([genomes[i].as_vector() for i in ids], dtype=float)  # N×8
    if X.shape[0] == 0:
        return {"portfolios": [], "variance_explained": [0.0, 0.0], "axis_loadings": {}}

    # Center each axis
    mu = X.mean(axis=0)
    Xc = X - mu

    # SVD: Xc = U @ diag(s) @ Vt
    try:
        U, s, Vt = np.linalg.svd(Xc, full_matrices=False)
    except np.linalg.LinAlgError:
        return {"portfolios": [{"id": i, "x": 0.0, "y": 0.0} for i in ids],
                "variance_explained": [0.0, 0.0], "axis_loadings": {}}

    # Project onto top 2 components: scores = U @ diag(s) limited to 2 cols
    k = min(2, len(s))
    scores = U[:, :k] * s[:k]
    if scores.shape[1] == 1:
        # Degenerate case with only 1 effective component
        scores = np.column_stack([scores, np.zeros(scores.shape[0])])

    total_var = float((s ** 2).sum()) or 1.0
    var_explained = [float((s[i] ** 2) / total_var) if i < len(s) else 0.0 for i in range(2)]

    # Axis loadings: rows of Vt are principal axes in the 8-dim feature space.
    # Map each AXES[i] to (pc1_loading, pc2_loading) for the optional axis overlay.
    loadings: dict = {}
    for i, axis in enumerate(AXES):
        try:
            loadings[axis] = [float(Vt[0, i]) if 0 < len(s) else 0.0,
                              float(Vt[1, i]) if 1 < len(s) else 0.0]
        except Exception:
            loadings[axis] = [0.0, 0.0]

    return {
        "portfolios": [
            {"id": ids[i], "x": float(scores[i, 0]), "y": float(scores[i, 1])}
            for i in range(len(ids))
        ],
        "variance_explained": var_explained,
        "axis_loadings": loadings,
    }


# ─── Serialization helpers ───────────────────────────────────────────────────

def profile_to_dict(profile: DnaProfile) -> dict:
    return {
        "portfolio_id": profile.portfolio_id,
        "portfolio_name": profile.portfolio_name,
        "stated": asdict(profile.stated),
        "measured": asdict(profile.measured),
        "drift": profile.drift,
        "drift_summary": profile.drift_summary,
        "axes": AXES,
    }
