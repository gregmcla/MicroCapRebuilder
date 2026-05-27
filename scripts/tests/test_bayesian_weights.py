import json
from pathlib import Path
import pandas as pd
import pytest
from bayesian_weights import (
    beta_posterior_mean,
    compute_factor_power,
    powers_to_weights,
    learn_weights_for_regime,
    update_weights_for_portfolio,
    FACTORS,
)


def test_beta_posterior_mean_centers_at_prior():
    # No data: prior alpha=beta=10 → mean = 0.5
    assert beta_posterior_mean(0, 0) == pytest.approx(0.5)


def test_beta_posterior_mean_shifts_with_data():
    # 100 wins, 0 losses with weak prior alpha=beta=10 → mean ≈ 110/120
    assert beta_posterior_mean(100, 0) == pytest.approx(110 / 120, abs=1e-6)
    assert beta_posterior_mean(0, 100) == pytest.approx(10 / 120, abs=1e-6)


def test_compute_factor_power_positive_when_high_scores_win_more():
    # 10 high-score trades, 8 wins; 10 low-score trades, 2 wins
    # → posterior_top ≈ 18/30 = 0.60; posterior_bot ≈ 12/30 = 0.40 → power ≈ 0.20
    trades = (
        [{"score": 80, "won": True}] * 8 +
        [{"score": 80, "won": False}] * 2 +
        [{"score": 20, "won": True}] * 2 +
        [{"score": 20, "won": False}] * 8
    )
    power = compute_factor_power(trades)
    assert power > 0.15
    assert power < 0.25


def test_compute_factor_power_zero_when_no_data():
    assert compute_factor_power([]) == 0.0


def test_powers_to_weights_clamps_and_normalizes():
    # One factor dominates → would be 1.0 unclamped; must be clamped to default 0.40 cap
    powers = {"price_momentum": 1.0, "earnings_growth": 0.0, "quality": 0.0,
              "volume": 0.0, "volatility": 0.0, "value_timing": 0.0}
    w = powers_to_weights(powers)
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-4)
    assert max(w.values()) <= 0.40 + 1e-6
    assert min(w.values()) >= 0.05 - 1e-6
    assert w["price_momentum"] == pytest.approx(0.40, abs=1e-4)


def test_powers_to_weights_respects_custom_cap_and_floor():
    # MAX-style override: cap=0.55, floor=0.05
    powers = {"price_momentum": 1.0, "earnings_growth": 0.0, "quality": 0.0,
              "volume": 0.0, "volatility": 0.0, "value_timing": 0.0}
    w = powers_to_weights(powers, cap=0.55, floor=0.05)
    assert w["price_momentum"] == pytest.approx(0.55, abs=1e-4)
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-4)
    assert max(w.values()) <= 0.55 + 1e-6
    assert min(w.values()) >= 0.05 - 1e-6


def test_powers_to_weights_equal_when_no_signal():
    powers = {f: 0.0 for f in FACTORS}
    w = powers_to_weights(powers)
    for v in w.values():
        assert v == pytest.approx(1 / 6, abs=1e-4)


def test_learn_falls_back_to_global_when_regime_sparse(tmp_path, monkeypatch):
    """BEAR regime with <15 trades → uses global posterior, not BEAR-specific."""
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    pdir = tmp_path / "portfolios" / "p1"
    pdir.mkdir(parents=True)

    # 50 BULL trades where price_momentum is highly predictive
    # 5 BEAR trades (sparse) — should fall back to global
    rows = []
    for i in range(50):
        won = i < 35  # 70% win rate
        rows.append({
            "buy_id": f"B{i}", "ticker": f"T{i}", "regime": "BULL",
            "factor_scores": json.dumps({"price_momentum": 80 if won else 20, "earnings_growth": 50,
                                          "quality": 50, "volume": 50, "volatility": 50, "value_timing": 50}),
            "won": won,
        })
    for i in range(5):
        rows.append({
            "buy_id": f"BR{i}", "ticker": f"BT{i}", "regime": "BEAR",
            "factor_scores": json.dumps({"price_momentum": 50, "earnings_growth": 50,
                                          "quality": 50, "volume": 50, "volatility": 50, "value_timing": 50}),
            "won": i < 3,
        })

    bull_weights = learn_weights_for_regime("p1", "BULL", rows)
    bear_weights = learn_weights_for_regime("p1", "BEAR", rows)

    # BULL: price_momentum should be the dominant factor (highest weight)
    assert bull_weights["price_momentum"] == max(bull_weights.values())
    assert bull_weights["price_momentum"] > 0.28  # comfortably above equal-weight baseline (1/6 ≈ 0.167)
    # BEAR: sparse → falls back to global (55 trades) → pm elevated, similar to BULL
    assert bear_weights["price_momentum"] > 0.25


def test_update_weights_writes_config_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    pdir = tmp_path / "portfolios" / "p1"
    pdir.mkdir(parents=True)
    # Seed minimal config
    (pdir / "config.json").write_text(json.dumps({
        "id": "p1",
        "scoring": {"default_weights": {f: 1 / 6 for f in FACTORS}, "regime_weights": {}},
        "learning": {"min_trades_for_adjustment": 5},
    }))
    # Seed 20 closed trades in transactions+post_mortems
    txs, pms = [], []
    for i in range(20):
        won = i < 14
        txs.append({
            "transaction_id": f"BUY-{i}", "date": f"2026-04-{i+1:02d}", "ticker": f"T{i}",
            "action": "BUY", "shares": 1, "price": 10, "regime_at_entry": "BULL",
            "factor_scores": json.dumps({f: (85 if won and f == "price_momentum" else 50) for f in FACTORS}),
            "trade_rationale": "{}",
        })
        txs.append({
            "transaction_id": f"SELL-{i}", "date": f"2026-04-{i+10:02d}", "ticker": f"T{i}",
            "action": "SELL", "shares": 1, "price": 11 if won else 9,
            "factor_scores": "{}", "trade_rationale": "{}",
        })
        pms.append({
            "transaction_id": f"SELL-{i}", "buy_transaction_id": f"BUY-{i}", "ticker": f"T{i}",
            "close_date": f"2026-04-{i+10:02d}", "pnl_pct": 10 if won else -10,
            "regime_at_entry": "BULL", "exit_reason": "TAKE_PROFIT" if won else "STOP_LOSS",
            "holding_days": 5, "summary": "", "what_worked": "[]", "what_failed": "[]",
            "pattern_tags": "[]", "recommendation": "",
        })
    pd.DataFrame(txs).to_csv(pdir / "transactions.csv", index=False)
    pd.DataFrame(pms).to_csv(pdir / "post_mortems.csv", index=False)

    result = update_weights_for_portfolio("p1")
    assert result is True

    # Config updated
    cfg = json.loads((pdir / "config.json").read_text())
    weights = cfg["scoring"]["default_weights"]
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-3)
    assert all(0.05 - 1e-6 <= v <= 0.40 + 1e-6 for v in weights.values())
    # price_momentum should be the strongest signal in this synthetic data
    assert weights["price_momentum"] == max(weights.values())

    # Audit trail exists
    audit = pdir / "weight_history.jsonl"
    assert audit.exists()
    lines = audit.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["portfolio_id"] == "p1"
    assert "timestamp" in entry
    assert entry["regime_weights"]["BULL"]["price_momentum"] > 0.25


def test_update_returns_false_when_too_few_trades(tmp_path, monkeypatch):
    """min_trades_for_adjustment=10 with only 3 closed trades → no-op."""
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    pdir = tmp_path / "portfolios" / "p1"
    pdir.mkdir(parents=True)
    (pdir / "config.json").write_text(json.dumps({
        "id": "p1",
        "scoring": {"default_weights": {f: 1 / 6 for f in FACTORS}},
        "learning": {"min_trades_for_adjustment": 10},
    }))
    pd.DataFrame([]).to_csv(pdir / "transactions.csv", index=False)
    pd.DataFrame([]).to_csv(pdir / "post_mortems.csv", index=False)
    assert update_weights_for_portfolio("p1") is False


def test_update_respects_per_portfolio_cap_override(tmp_path, monkeypatch):
    """A portfolio with learning.weight_cap=0.55 lets a strong factor reach 0.55, not 0.40.

    Uses 100 trades with perfectly split scores (pm=90 for winners, pm=10 for losers,
    all others=50 neutral) so the Bayesian posterior creates a strong enough signal
    to push price_momentum above 0.40. With default cap=0.40 it would clamp there;
    with cap=0.55 it should clamp at 0.55 instead.
    """
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    pdir = tmp_path / "portfolios" / "max-like"
    pdir.mkdir(parents=True)
    (pdir / "config.json").write_text(json.dumps({
        "id": "max-like",
        "scoring": {"default_weights": {f: 1 / 6 for f in FACTORS}, "regime_weights": {}},
        "learning": {"min_trades_for_adjustment": 5, "weight_cap": 0.55, "weight_floor": 0.05},
    }))
    txs, pms = [], []
    # 100 trades: 60 winners (pm=90), 40 losers (pm=10), all other factors neutral at 50
    for i in range(100):
        won = i < 60
        txs.append({
            "transaction_id": f"BUY-{i}", "date": "2026-04-01", "ticker": f"T{i}",
            "action": "BUY", "shares": 1, "price": 10, "regime_at_entry": "BULL",
            "factor_scores": json.dumps({
                "price_momentum": 90 if won else 10,
                "earnings_growth": 50, "quality": 50,
                "volume": 50, "volatility": 50, "value_timing": 50,
            }),
            "trade_rationale": "{}",
        })
        txs.append({
            "transaction_id": f"SELL-{i}", "date": "2026-04-15", "ticker": f"T{i}",
            "action": "SELL", "shares": 1, "price": 11 if won else 9,
            "factor_scores": "{}", "trade_rationale": "{}",
        })
        pms.append({
            "transaction_id": f"SELL-{i}", "buy_transaction_id": f"BUY-{i}", "ticker": f"T{i}",
            "close_date": "2026-04-15", "pnl_pct": 10 if won else -10,
            "regime_at_entry": "BULL", "exit_reason": "TAKE_PROFIT" if won else "STOP_LOSS",
            "holding_days": 14, "summary": "", "what_worked": "[]", "what_failed": "[]",
            "pattern_tags": "[]", "recommendation": "",
        })
    pd.DataFrame(txs).to_csv(pdir / "transactions.csv", index=False)
    pd.DataFrame(pms).to_csv(pdir / "post_mortems.csv", index=False)

    assert update_weights_for_portfolio("max-like") is True
    cfg = json.loads((pdir / "config.json").read_text())
    weights = cfg["scoring"]["default_weights"]
    # With cap=0.55, dominant factor can exceed the default 0.40 ceiling
    assert weights["price_momentum"] == pytest.approx(0.55, abs=1e-4)
    assert max(weights.values()) <= 0.55 + 1e-6
