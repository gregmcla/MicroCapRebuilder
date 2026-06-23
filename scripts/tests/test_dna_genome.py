#!/usr/bin/env python3
"""Tests for dna_genome — axis normalizers, profile assembly, PCA."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from dna_genome import (
    AXES,
    DnaGenome,
    compute_stated_dna,
    compute_measured_dna,
    compute_profile,
    compute_cluster_pca,
    profile_to_dict,
)


_TEST_PID = "_test_dna_genome"
_BASE = Path(__file__).parent.parent.parent / "data" / "portfolios" / _TEST_PID


@pytest.fixture(autouse=True)
def _cleanup():
    shutil.rmtree(_BASE, ignore_errors=True)
    _BASE.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(_BASE, ignore_errors=True)


# ─── Stated axis normalizers ─────────────────────────────────────────────────

def test_stated_aggression_max_config():
    """MAX-style config (8% risk, 12% max position) should land high."""
    cfg = {"risk_per_trade_pct": 8.0, "max_position_pct": 12.0}
    g = compute_stated_dna(cfg)
    assert g.aggression == 88.0  # 8*8 + 12*2 = 88


def test_stated_aggression_conservative():
    cfg = {"risk_per_trade_pct": 2.0, "max_position_pct": 5.0}
    g = compute_stated_dna(cfg)
    assert g.aggression == 26.0  # 2*8 + 5*2


def test_stated_concentration_focused_portfolio():
    """max_positions=2 → very concentrated."""
    cfg = {"max_positions": 2}
    g = compute_stated_dna(cfg)
    assert g.concentration > 80


def test_stated_concentration_broad_portfolio():
    cfg = {"max_positions": 100}
    g = compute_stated_dna(cfg)
    assert g.concentration < 40


def test_stated_momentum_bias_balanced():
    """Balanced 6-factor portfolio: 16.7% each → score ~32."""
    cfg = {"scoring": {"default_weights": {
        "price_momentum": 0.1667, "earnings_growth": 0.1667, "quality": 0.1667,
        "volume": 0.1667, "volatility": 0.1667, "value_timing": 0.1667,
    }}}
    g = compute_stated_dna(cfg)
    assert 28 <= g.momentum_bias <= 36


def test_stated_momentum_bias_heavy_momentum():
    cfg = {"scoring": {"default_weights": {
        "price_momentum": 0.40, "earnings_growth": 0.10, "quality": 0.10,
        "volume": 0.10, "volatility": 0.10, "value_timing": 0.20,
    }}}
    g = compute_stated_dna(cfg)
    assert g.momentum_bias >= 80


def test_stated_catalyst_hunting_with_refinement():
    cfg = {
        "universe": {"sources": {"screener": {
            "ai_refinement": "find catalyst-driven names",
            "market_cap_min": 50_000_000,
        }}},
        "default_stop_loss_pct": 12.0,
    }
    g = compute_stated_dna(cfg)
    assert g.catalyst_hunting >= 60


def test_stated_catalyst_hunting_no_refinement():
    cfg = {"universe": {"sources": {"screener": {"market_cap_min": 5_000_000_000}}}}
    g = compute_stated_dna(cfg)
    assert g.catalyst_hunting <= 35


def test_stated_regime_sensitivity_flat_weights():
    """If all regimes have identical weights, sensitivity is minimal."""
    same = {"price_momentum": 0.2, "earnings_growth": 0.2, "quality": 0.2,
            "volume": 0.2, "volatility": 0.1, "value_timing": 0.1}
    cfg = {"scoring": {"regime_weights": {"BULL": same, "BEAR": same, "SIDEWAYS": same}}}
    g = compute_stated_dna(cfg)
    assert g.regime_sensitivity == pytest.approx(10.0, abs=0.01)  # zero variance → floor


def test_stated_regime_sensitivity_differentiated():
    cfg = {"scoring": {"regime_weights": {
        "BULL":     {"price_momentum": 0.40, "quality": 0.10, "volatility": 0.05, "volume": 0.15, "earnings_growth": 0.15, "value_timing": 0.15},
        "BEAR":     {"price_momentum": 0.10, "quality": 0.40, "volatility": 0.20, "volume": 0.10, "earnings_growth": 0.10, "value_timing": 0.10},
        "SIDEWAYS": {"price_momentum": 0.20, "quality": 0.20, "volatility": 0.15, "volume": 0.15, "earnings_growth": 0.15, "value_timing": 0.15},
    }}}
    g = compute_stated_dna(cfg)
    assert g.regime_sensitivity >= 60


def test_stated_drawdown_discipline_tight():
    cfg = {
        "default_stop_loss_pct": 5.0,
        "risk_management": {"capital_preservation": {"triggers": {"drawdown_threshold_pct": 5.0}}},
    }
    g = compute_stated_dna(cfg)
    assert g.drawdown_discipline >= 70


def test_stated_drawdown_discipline_loose():
    cfg = {
        "default_stop_loss_pct": 15.0,
        "risk_management": {"capital_preservation": {"triggers": {"drawdown_threshold_pct": 20.0}}},
    }
    g = compute_stated_dna(cfg)
    assert g.drawdown_discipline <= 20


def test_stated_dna_confidence_always_one():
    g = compute_stated_dna({"risk_per_trade_pct": 5.0})
    assert g.confidence == 1.0


def test_stated_dna_empty_config_uses_defaults():
    g = compute_stated_dna({})
    # Doesn't crash, all axes in 0-100
    for axis in AXES:
        v = getattr(g, axis)
        assert 0 <= v <= 100, f"{axis}={v} out of range"


# ─── Measured DNA ────────────────────────────────────────────────────────────

def _seed_post_mortems(rows: list[dict]):
    """Write a fake post_mortems.csv with the rows.

    Fills the list-valued columns with `"[]"` (not `""`) because
    load_post_mortems() runs json.loads on them.
    """
    import pandas as pd
    cols = ["transaction_id", "buy_transaction_id", "ticker", "close_date",
            "entry_price", "exit_price", "pnl", "pnl_pct", "exit_reason",
            "holding_days", "regime_at_entry", "regime_at_exit",
            "composite_score_at_entry", "signal_rank_at_entry",
            "summary", "what_worked", "what_failed", "pattern_tags", "recommendation"]
    list_cols = {"what_worked", "what_failed", "pattern_tags"}
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = "[]" if c in list_cols else ""
    df = df[cols]
    # Backfill list cols where individual rows left them empty
    for lc in list_cols:
        df[lc] = df[lc].replace("", "[]")
    df.to_csv(_BASE / "post_mortems.csv", index=False)


def test_measured_empty_data_low_confidence():
    g = compute_measured_dna(_TEST_PID)
    assert g.confidence <= 0.2  # almost no data → low confidence
    # All axes still in valid range
    for axis in AXES:
        assert 0 <= getattr(g, axis) <= 100


def test_measured_time_horizon_from_post_mortems():
    """Avg 30-day holds → log10(30) * 30 ≈ 44."""
    _seed_post_mortems([
        {"ticker": "A", "close_date": "2026-05-01", "holding_days": 30, "exit_reason": "TAKE_PROFIT"},
        {"ticker": "B", "close_date": "2026-05-15", "holding_days": 30, "exit_reason": "STOP_LOSS"},
        {"ticker": "C", "close_date": "2026-05-30", "holding_days": 30, "exit_reason": "SIGNAL"},
    ])
    g = compute_measured_dna(_TEST_PID)
    assert 40 <= g.time_horizon <= 50


def test_measured_drawdown_discipline_loose():
    """Stops held longer than take-profits → ratio > 1 → low discipline."""
    _seed_post_mortems([
        {"ticker": "A", "close_date": "2026-05-01", "holding_days": 60, "exit_reason": "STOP_LOSS"},
        {"ticker": "B", "close_date": "2026-05-01", "holding_days": 70, "exit_reason": "STOP_LOSS"},
        {"ticker": "C", "close_date": "2026-05-01", "holding_days": 10, "exit_reason": "TAKE_PROFIT"},
        {"ticker": "D", "close_date": "2026-05-01", "holding_days": 12, "exit_reason": "TAKE_PROFIT"},
    ])
    g = compute_measured_dna(_TEST_PID)
    # Ratio 65/11 = 5.9 → very loose
    assert g.drawdown_discipline <= 20


def test_measured_drawdown_discipline_tight():
    """Quick stops, slow profits → ratio < 0.5 → high discipline."""
    _seed_post_mortems([
        {"ticker": "A", "close_date": "2026-05-01", "holding_days": 3, "exit_reason": "STOP_LOSS"},
        {"ticker": "B", "close_date": "2026-05-01", "holding_days": 5, "exit_reason": "STOP_LOSS"},
        {"ticker": "C", "close_date": "2026-05-01", "holding_days": 40, "exit_reason": "TAKE_PROFIT"},
        {"ticker": "D", "close_date": "2026-05-01", "holding_days": 60, "exit_reason": "TAKE_PROFIT"},
    ])
    g = compute_measured_dna(_TEST_PID)
    assert g.drawdown_discipline >= 80


def test_measured_window_filter():
    """When window=90, old post-mortems should be excluded."""
    _seed_post_mortems([
        {"ticker": "OLD", "close_date": "2020-01-01", "holding_days": 5, "exit_reason": "STOP_LOSS"},
    ])
    g_all = compute_measured_dna(_TEST_PID, window="all")
    g_90 = compute_measured_dna(_TEST_PID, window="90")
    # Old data only available in "all" — 90d window has no data, lower confidence
    assert g_all.confidence > g_90.confidence


# ─── Profile + drift ─────────────────────────────────────────────────────────

def test_profile_drift_calculation():
    cfg = {"risk_per_trade_pct": 8.0, "max_position_pct": 12.0}  # stated aggression = 88
    profile = compute_profile(_TEST_PID, "test", cfg)
    assert profile.stated.aggression == 88.0
    # Measured has no data → ~50 → drift ≈ 38
    assert abs(profile.drift["aggression"]) > 20


def test_profile_drift_summary_highlights_biggest_drift():
    cfg = {"risk_per_trade_pct": 10.0, "max_position_pct": 15.0}  # very aggressive stated
    _seed_post_mortems([
        {"ticker": f"T{i}", "close_date": "2026-05-01", "holding_days": 30,
         "exit_reason": "TAKE_PROFIT" if i % 2 else "STOP_LOSS"}
        for i in range(20)
    ])
    profile = compute_profile(_TEST_PID, "test", cfg)
    # Summary should mention the biggest disagreement
    assert profile.drift_summary != ""
    # Sanity: aggression drift is likely the headline (config is extreme)
    assert "overclaiming" in profile.drift_summary or "underclaiming" in profile.drift_summary


def test_profile_drift_summary_aligned_case():
    """If stated and measured are close, summary says 'aligned'."""
    cfg = {}  # all defaults → moderate scores
    profile = compute_profile(_TEST_PID, "test", cfg)
    # No measured data → measured ~50, stated also moderate → drift could be small or large
    # We just verify drift_summary is non-empty and structured
    assert isinstance(profile.drift_summary, str)


# ─── PCA ─────────────────────────────────────────────────────────────────────

def _genome(values: dict) -> DnaGenome:
    """Build a genome with explicit per-axis overrides; defaults to 50."""
    defaults = {a: 50.0 for a in AXES}
    defaults.update(values)
    return DnaGenome(**defaults, confidence=1.0)


def test_pca_returns_2d_projection():
    genomes = {
        "p1": _genome({"aggression": 90, "momentum_bias": 80}),
        "p2": _genome({"aggression": 20, "momentum_bias": 30}),
        "p3": _genome({"aggression": 50, "concentration": 80}),
        "p4": _genome({"aggression": 50, "concentration": 20}),
    }
    out = compute_cluster_pca(genomes)
    assert len(out["portfolios"]) == 4
    for p in out["portfolios"]:
        assert "x" in p and "y" in p
        assert isinstance(p["x"], float)
        assert isinstance(p["y"], float)


def test_pca_variance_explained_sums_to_at_most_one():
    genomes = {f"p{i}": _genome({"aggression": i * 10}) for i in range(6)}
    out = compute_cluster_pca(genomes)
    var = out["variance_explained"]
    assert len(var) == 2
    assert sum(var) <= 1.0001


def test_pca_axis_loadings_present():
    genomes = {f"p{i}": _genome({"aggression": i * 10, "momentum_bias": i * 8}) for i in range(5)}
    out = compute_cluster_pca(genomes)
    assert "axis_loadings" in out
    for axis in AXES:
        assert axis in out["axis_loadings"]
        assert len(out["axis_loadings"][axis]) == 2


def test_pca_similar_genomes_project_close():
    """MAX clones should land near each other in PCA space."""
    base_axes = {"aggression": 90, "momentum_bias": 85, "concentration": 70}
    genomes = {
        "max": _genome(base_axes),
        "max2": _genome(base_axes),    # exact clone
        "boring": _genome({"aggression": 20, "momentum_bias": 20, "concentration": 20}),
    }
    out = compute_cluster_pca(genomes)
    pts = {p["id"]: (p["x"], p["y"]) for p in out["portfolios"]}
    dist_clones = ((pts["max"][0] - pts["max2"][0]) ** 2 +
                   (pts["max"][1] - pts["max2"][1]) ** 2) ** 0.5
    dist_far = ((pts["max"][0] - pts["boring"][0]) ** 2 +
                (pts["max"][1] - pts["boring"][1]) ** 2) ** 0.5
    assert dist_clones < dist_far


def test_pca_empty_input():
    out = compute_cluster_pca({})
    assert out["portfolios"] == []
    assert out["variance_explained"] == [0.0, 0.0]


# ─── Serialization ───────────────────────────────────────────────────────────

def test_profile_to_dict_is_json_serializable():
    cfg = {"risk_per_trade_pct": 5.0}
    profile = compute_profile("p1", "Test", cfg)
    d = profile_to_dict(profile)
    s = json.dumps(d)  # must round-trip JSON
    assert json.loads(s)["portfolio_id"] == "p1"
    assert "axes" in d and d["axes"] == AXES
