#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import digest_service


def test_book_rollup_sums_provided_rows_and_counts_health():
    # `_roll_up_book` sums the rows it's given (live-filtering happens upstream
    # in build_digest — see Task 6). Two live, non-excluded portfolios.
    rows = [
        {"id": "max", "equity": 5_000_000.0, "day_pnl": 12_000.0, "total_return_pct": 18.4, "exclude": False},
        {"id": "gov-infra", "equity": 1_000_000.0, "day_pnl": 6_420.0, "total_return_pct": 9.3, "exclude": False},
    ]
    book = digest_service._roll_up_book(rows)
    assert book["equity"] == 6_000_000.0
    assert book["day_pnl"] == 18_420.0
    assert book["health"]["green"] == 2
    assert book["health"]["red"] == 0


def test_book_rollup_respects_exclude_from_aggregates():
    rows = [
        {"id": "max", "equity": 5_000_000.0, "day_pnl": 10.0, "total_return_pct": 1.0, "exclude": False},
        {"id": "max2", "equity": 4_960_000.0, "day_pnl": 5.0, "total_return_pct": 1.0, "exclude": True},
    ]
    book = digest_service._roll_up_book(rows)
    assert book["equity"] == 5_000_000.0  # max2 excluded
    assert book["day_pnl"] == 10.0          # max2's 5.0 excluded
    assert book["health"]["green"] == 1     # only max counted
    assert book["health"]["red"] == 0


def test_derive_trend_from_sparkline_and_alpha():
    rising = [100, 101, 103, 106, 110]
    falling = [110, 106, 103, 101, 98]
    flat = [100, 100.2, 99.9, 100.1, 100.0]
    assert digest_service.derive_trend(rising, vs_bench_pct=12.0) == "ahead"
    assert digest_service.derive_trend(falling, vs_bench_pct=-21.0) == "fading"
    assert digest_service.derive_trend(flat, vs_bench_pct=-0.5) == "flat"


def test_derive_trend_handles_short_series():
    assert digest_service.derive_trend([], vs_bench_pct=0.0) == "flat"
    assert digest_service.derive_trend([100.0], vs_bench_pct=0.0) == "flat"


import pandas as pd


def test_build_book_curve_aligns_and_normalizes(monkeypatch):
    # max:      equity [100→110], day_pnl [0→10]
    # gov-infra: equity [50→55],  day_pnl [0→5]
    # Day-2: prior = (110+55)-(10+5) = 150; pnl = 15; r = 0.10 → book[-1] = 110.0
    snaps = {
        "max":      pd.DataFrame({"date": ["2026-05-01", "2026-05-02"],
                                  "total_equity": [100.0, 110.0], "day_pnl": [0.0, 10.0]}),
        "gov-infra":pd.DataFrame({"date": ["2026-05-01", "2026-05-02"],
                                  "total_equity": [50.0, 55.0],   "day_pnl": [0.0, 5.0]}),
    }
    spy = pd.Series([400.0, 408.0], index=pd.to_datetime(["2026-05-01", "2026-05-02"]))
    monkeypatch.setattr(digest_service, "_fetch_spy_series", lambda start, end: spy)

    curve = digest_service.build_book_curve(snaps, range_key="ALL")
    assert curve["book"][0] == 100.0
    assert round(curve["book"][-1], 1) == 110.0
    assert curve["spy"][0] == 100.0
    assert round(curve["spy"][-1], 1) == 102.0
    assert curve["range"] == "ALL"


def test_build_book_curve_is_deposit_neutral(monkeypatch):
    # equity jumps 100 -> 200 but day_pnl is 0 (pure deposit) -> book stays flat at 100
    snaps = {"p": pd.DataFrame({"date": ["2026-05-01", "2026-05-02"],
                                "total_equity": [100.0, 200.0], "day_pnl": [0.0, 0.0]})}
    monkeypatch.setattr(digest_service, "_fetch_spy_series", lambda s, e: pd.Series(dtype=float))
    curve = digest_service.build_book_curve(snaps, range_key="ALL")
    assert curve["book"][0] == 100.0
    assert round(curve["book"][-1], 1) == 100.0


def test_build_book_curve_reflects_real_pnl(monkeypatch):
    # real +10 gain on a 100 base -> +10%
    snaps = {"p": pd.DataFrame({"date": ["2026-05-01", "2026-05-02"],
                                "total_equity": [100.0, 110.0], "day_pnl": [0.0, 10.0]})}
    monkeypatch.setattr(digest_service, "_fetch_spy_series", lambda s, e: pd.Series(dtype=float))
    curve = digest_service.build_book_curve(snaps, range_key="ALL")
    assert round(curve["book"][-1], 1) == 110.0


def test_vs_bench_uses_configured_symbol():
    cfg_micro = {"benchmark_symbol": "^RUT"}
    cfg_max = {}
    assert digest_service.bench_symbol(cfg_micro) == "^RUT"
    assert digest_service.bench_symbol(cfg_max) == "SPY"


def test_vs_bench_pct_is_total_return_minus_bench_return(monkeypatch):
    monkeypatch.setattr(digest_service, "_bench_return_pct", lambda sym, snaps: 7.0)
    snaps = pd.DataFrame({"date": ["2026-01-01", "2026-05-01"], "total_equity": [100, 131]})
    alpha = digest_service.vs_bench_pct(total_return_pct=31.0, bench="^RUT", snapshots=snaps)
    assert round(alpha, 1) == 24.0


def test_build_recap_classifies_buys_and_sells():
    txns = pd.DataFrame({
        "date": ["2026-05-29", "2026-05-29", "2026-05-28"],
        "ticker": ["NVDA", "INTC", "OLD"],
        "action": ["BUY", "SELL", "BUY"],
        "total_value": [50000.0, 30000.0, 9999.0],
        "reason": ["SIGNAL", "STOP_LOSS", "SIGNAL"],
    })
    recap = digest_service.build_recap(
        txns_by_pid={"max": txns}, since="2026-05-29",
        movers=[{"ticker": "CRDO", "pct": 9.1}, {"ticker": "HUT", "pct": -7.2}],
        regime={"label": "SIDEWAYS", "risk": 41, "risk_prev": 47},
    )
    assert recap["buys"]["count"] == 1     # only 2026-05-29 BUY counts
    assert recap["exits"]["count"] == 1
    assert recap["swings"][0]["ticker"] == "CRDO"
    assert recap["regime"]["label"] == "SIDEWAYS"


def test_compute_posture_maps_regime_and_exposure():
    p = digest_service.compute_posture(regime="BULL", deployed_pct=85.0, book_alpha=4.2)
    assert p["value"] > 0.6 and "risk-on" in p["label"].lower()
    d = digest_service.compute_posture(regime="BEAR", deployed_pct=20.0, book_alpha=-1.0)
    assert d["value"] < 0.4


def test_spy_today_move():
    assert digest_service._spy_today_move([100.0, 102.0]) == 2.0
    assert digest_service._spy_today_move([100.0]) == 0.0
    assert digest_service._spy_today_move([]) == 0.0


def test_fetch_bench_series_uses_period_not_start_end(monkeypatch):
    import pandas as pd
    calls = {}
    def fake_cached_download(symbol, period="1y", **kwargs):
        calls["period"] = period
        calls["kwargs"] = kwargs
        idx = pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-29"])
        return pd.DataFrame({"Close": [400.0, 405.0, 410.0]}, index=idx)
    import yf_session
    monkeypatch.setattr(yf_session, "cached_download", fake_cached_download)
    s = digest_service._fetch_bench_series("SPY", "2026-05-01", "2026-05-29")
    # cached_download must be called with a period and WITHOUT start/end (the bug)
    assert "start" not in calls["kwargs"] and "end" not in calls["kwargs"]
    assert calls["period"] in {"1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
    assert len(s) >= 1 and float(s.iloc[-1]) == 410.0
