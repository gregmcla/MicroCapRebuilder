#!/usr/bin/env python3
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))
from main import app

client = TestClient(app)


def test_digest_endpoint_shape():
    r = client.get("/api/digest")
    assert r.status_code == 200
    body = r.json()
    assert "book" in body and "portfolios" in body and "recap" in body
    assert "equity" in body["book"] and "health" in body["book"]
    assert "curve" in body["book"] and "book" in body["book"]["curve"]
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
        all_time_pnl = 0.0
    class _P:
        def __init__(self, pid): self.id = pid; self.name = pid; self.exclude_from_aggregates = False
    import portfolio_registry, portfolio_state
    monkeypatch.setattr(portfolio_registry, "list_portfolios", lambda active_only=True: [_P("live1"), _P("paper1")])
    monkeypatch.setattr(portfolio_state, "load_portfolio_state",
                        lambda fetch_prices, portfolio_id: _S(portfolio_id == "paper1"))
    monkeypatch.setattr(ds, "_fetch_spy_series", lambda s, e: __import__("pandas").Series(dtype=float))
    monkeypatch.setattr(ds, "_book_movers", lambda: [])
    monkeypatch.setattr(ds, "_book_regime", lambda: {"label": "SIDEWAYS", "risk": 0, "risk_prev": 0})
    out = ds.build_digest(range_key="ALL")
    ids = [p["id"] for p in out["portfolios"]]
    assert "live1" in ids and "paper1" not in ids
