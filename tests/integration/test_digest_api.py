#!/usr/bin/env python3
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))
from main import app

client = TestClient(app)


def test_digest_endpoint_shape(monkeypatch):
    import pandas as pd
    import digest_service as ds
    import portfolio_registry, portfolio_state

    class _S:
        paper_mode = False
        total_equity = 1_000_000.0
        snapshots = pd.DataFrame({"date": ["2026-05-01", "2026-05-29"], "total_equity": [950_000.0, 1_000_000.0], "day_pnl": [0.0, 1234.0]})
        transactions = pd.DataFrame()
        positions = pd.DataFrame({"ticker": ["AAA"], "day_change_pct": [1.5], "unrealized_pnl": [5000.0]})
        config = {"starting_capital": 950_000.0, "strategy": {"trading_style": "momentum"}}
    class _P:
        def __init__(self, pid): self.id = pid; self.name = pid; self.exclude_from_aggregates = False

    monkeypatch.setattr(portfolio_registry, "list_portfolios", lambda active_only=True: [_P("live1")])
    monkeypatch.setattr(portfolio_state, "load_portfolio_state", lambda fetch_prices, portfolio_id: _S())
    monkeypatch.setattr(ds, "_fetch_spy_series", lambda s, e: pd.Series(dtype=float))
    monkeypatch.setattr(ds, "_bench_return_pct", lambda sym, snaps: 0.0)
    monkeypatch.setattr(ds, "_book_regime", lambda: {"label": "SIDEWAYS", "risk": 0, "risk_prev": 0})

    r = client.get("/api/digest")
    assert r.status_code == 200
    body = r.json()
    assert "book" in body and "portfolios" in body and "recap" in body
    assert "equity" in body["book"] and "health" in body["book"]
    assert "curve" in body["book"] and "book" in body["book"]["curve"]
    assert len(body["portfolios"]) == 1
    for p in body["portfolios"]:
        assert {"id", "name", "equity", "vs_bench_pct", "bench_symbol", "trend"} <= set(p)


def test_digest_excludes_paper_mode_portfolios(monkeypatch):
    import digest_service as ds

    class _S:
        def __init__(self, paper): self.paper_mode = paper; self.total_equity = 1.0
        snapshots = __import__("pandas").DataFrame()
        transactions = __import__("pandas").DataFrame()
        positions = __import__("pandas").DataFrame()
        config = {"starting_capital": 1.0}
    class _P:
        def __init__(self, pid): self.id = pid; self.name = pid; self.exclude_from_aggregates = False
    import portfolio_registry, portfolio_state
    monkeypatch.setattr(portfolio_registry, "list_portfolios", lambda active_only=True: [_P("live1"), _P("paper1")])
    monkeypatch.setattr(portfolio_state, "load_portfolio_state",
                        lambda fetch_prices, portfolio_id: _S(portfolio_id == "paper1"))
    monkeypatch.setattr(ds, "_fetch_spy_series", lambda s, e: __import__("pandas").Series(dtype=float))
    monkeypatch.setattr(ds, "_book_regime", lambda: {"label": "SIDEWAYS", "risk": 0, "risk_prev": 0})
    out = ds.build_digest(range_key="ALL")
    ids = [p["id"] for p in out["portfolios"]]
    assert "live1" in ids and "paper1" not in ids


def test_digest_narrative_parses_json(monkeypatch):
    import digest_service as ds
    fake = ('{"thesis":"Momentum is working.","body":"defense-tech leads.",'
            '"callout":"Watch microcap.","working":["defense-tech"],"watching":["microcap"]}')
    monkeypatch.setattr(ds, "_call_claude_json", lambda prompt: fake)
    out = ds.build_digest_narrative(digest={"book": {"health": {"green": 4, "red": 2}},
                                            "portfolios": [], "recap": {}},
                                    posture={"value": 0.74, "label": "Risk-on · leaning momentum"})
    assert out["thesis"].startswith("Momentum")
    assert out["posture"] == 0.74
    assert out["working"] == ["defense-tech"]


def test_digest_narrative_falls_back_on_bad_json(monkeypatch):
    import digest_service as ds
    monkeypatch.setattr(ds, "_call_claude_json", lambda prompt: "not json at all")
    out = ds.build_digest_narrative(digest={"book": {"health": {"green": 4, "red": 2}},
                                            "portfolios": [], "recap": {}},
                                    posture={"value": 0.5, "label": "Balanced · selective"})
    assert "thesis" in out and out["thesis"]   # deterministic fallback, never blank
    assert out["posture"] == 0.5


def test_narrative_cache_avoids_rebuild(monkeypatch, tmp_path):
    import digest_service as ds
    monkeypatch.setattr(ds, "_NARRATIVE_CACHE_FILE", tmp_path / "digest_narrative.json")
    calls = {"n": 0}
    def fake_build(rk="3M"):
        return {"book": {"vs_spy_alltime_pct": 1.0, "health": {"green": 1, "red": 0}}, "portfolios": [], "recap": {"regime": {"label": "BULL"}}}
    def fake_narr(d, posture):
        calls["n"] += 1
        return {"thesis": "t", "body": "b", "callout": "", "working": [], "watching": [], "posture": posture["value"], "posture_label": posture["label"]}
    monkeypatch.setattr(ds, "build_digest", fake_build)
    monkeypatch.setattr(ds, "build_digest_narrative", fake_narr)
    # cold → builds (1 call), stamps generated_at, writes cache
    n1 = ds.get_or_build_narrative()
    assert calls["n"] == 1 and "generated_at" in n1
    # warm → served from cache, NO new build
    n2 = ds.get_or_build_narrative()
    assert calls["n"] == 1
    # regenerate → rebuilds
    n3 = ds.get_or_build_narrative(regenerate=True)
    assert calls["n"] == 2
