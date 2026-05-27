import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from reflection import (
    read_observations,
    write_observations,
    read_shared_observations,
    write_shared_observations,
    format_observations_block,
    build_reflection_prompt,
    parse_reflection_response,
    apply_curation_operations,
    run_reflection,
    MAX_OBSERVATIONS_PER_PORTFOLIO,
    MIN_SAMPLE_FOR_NEW,
)


def _seed(tmp_path, portfolio_id, observations):
    pdir = tmp_path / "portfolios" / portfolio_id
    pdir.mkdir(parents=True)
    (pdir / "observations.json").write_text(json.dumps({
        "updated": "2026-05-20T00:00:00Z", "cycle_count": 0, "observations": observations
    }))


def test_read_observations_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    (tmp_path / "portfolios" / "p1").mkdir(parents=True)
    assert read_observations("p1") == []


def test_format_observations_block_filters_to_regime(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    obs = [
        {"id": "o1", "regime": "BULL",     "claim": "BULL only claim", "sample_size": 12, "win_rate": 0.6, "last_updated": "2026-05-27T00:00:00Z"},
        {"id": "o2", "regime": "BEAR",     "claim": "BEAR only claim", "sample_size": 8,  "win_rate": 0.3, "last_updated": "2026-05-27T00:00:00Z"},
        {"id": "o3", "regime": "ALL",      "claim": "Universal claim", "sample_size": 30, "win_rate": 0.5, "last_updated": "2026-05-27T00:00:00Z"},
        {"id": "o4", "regime": "SIDEWAYS", "claim": "Sideways claim",  "sample_size": 5,  "win_rate": 0.4, "last_updated": "2026-05-27T00:00:00Z"},
    ]
    text = format_observations_block(obs, regime="BULL")
    assert "BULL only claim" in text
    assert "Universal claim" in text
    assert "BEAR only claim" not in text
    assert "Sideways claim" not in text


def test_format_observations_block_empty():
    assert format_observations_block([], regime="BULL") == ""


def test_build_reflection_prompt_includes_inputs():
    prompt = build_reflection_prompt(
        portfolio_id="p1",
        regime="BULL",
        portfolio_observations=[{"id": "o1", "regime": "BULL", "claim": "A claim", "sample_size": 10, "win_rate": 0.5}],
        shared_observations=[{"id": "s1", "regime": "ALL", "claim": "Shared claim", "sample_size": 50, "win_rate": 0.55, "portfolios": ["max"]}],
        clustered_history="CLUSTERED HISTORY HERE",
        per_trade_history="DETAILED TRADES HERE",
    )
    assert "p1" in prompt
    assert "BULL" in prompt
    assert "A claim" in prompt
    assert "Shared claim" in prompt
    assert "CLUSTERED HISTORY HERE" in prompt
    assert "DETAILED TRADES HERE" in prompt
    assert "retire" in prompt.lower()
    assert "update" in prompt.lower()
    assert "add" in prompt.lower()
    assert "json" in prompt.lower()


def test_parse_reflection_response_extracts_operations():
    response = '''Here is my curation:
```json
{
  "retire": ["obs-2026-05-01-003"],
  "update": [
    {"id": "obs-2026-05-15-002", "claim": "Updated claim", "sample_size": 18, "win_rate": 0.61, "evidence_tickers": ["A","B"]}
  ],
  "add": [
    {"regime": "BULL", "claim": "New BULL observation", "sample_size": 7, "win_rate": 0.71, "evidence_tickers": ["X","Y"]}
  ],
  "add_shared": [
    {"regime": "ALL", "claim": "New shared observation", "sample_size": 12, "win_rate": 0.42, "evidence_tickers": ["P"]}
  ]
}
```
'''
    ops = parse_reflection_response(response)
    assert ops["retire"] == ["obs-2026-05-01-003"]
    assert len(ops["update"]) == 1
    assert ops["update"][0]["id"] == "obs-2026-05-15-002"
    assert len(ops["add"]) == 1
    assert ops["add"][0]["regime"] == "BULL"
    assert len(ops["add_shared"]) == 1


def test_parse_reflection_response_handles_raw_json():
    raw = '{"retire": [], "update": [], "add": [], "add_shared": []}'
    ops = parse_reflection_response(raw)
    assert ops == {"retire": [], "update": [], "add": [], "add_shared": []}


def test_parse_reflection_response_handles_garbage():
    ops = parse_reflection_response("not json at all")
    assert ops == {"retire": [], "update": [], "add": [], "add_shared": []}


def test_apply_curation_operations_retires_updates_adds():
    existing = [
        {"id": "o1", "regime": "BULL", "claim": "old1", "sample_size": 5, "win_rate": 0.4, "first_seen": "2026-01-01T00:00:00Z", "last_updated": "2026-01-01T00:00:00Z"},
        {"id": "o2", "regime": "BULL", "claim": "old2", "sample_size": 8, "win_rate": 0.5, "first_seen": "2026-02-01T00:00:00Z", "last_updated": "2026-02-01T00:00:00Z"},
    ]
    ops = {
        "retire": ["o1"],
        "update": [{"id": "o2", "claim": "refreshed", "sample_size": 12, "win_rate": 0.66, "evidence_tickers": ["A"]}],
        "add": [{"regime": "BULL", "claim": "brand new", "sample_size": 4, "win_rate": 0.75, "evidence_tickers": ["B"]}],
    }
    result = apply_curation_operations(existing, ops, now="2026-05-27T12:00:00Z")
    ids = {o["id"] for o in result}
    assert "o1" not in ids                          # retired
    refreshed = next(o for o in result if o["id"] == "o2")
    assert refreshed["claim"] == "refreshed"         # updated
    assert refreshed["sample_size"] == 12
    assert refreshed["last_updated"] == "2026-05-27T12:00:00Z"
    assert refreshed["first_seen"] == "2026-02-01T00:00:00Z"  # preserved
    assert any(o["claim"] == "brand new" for o in result)     # added
    new_obs = next(o for o in result if o["claim"] == "brand new")
    assert new_obs["first_seen"] == "2026-05-27T12:00:00Z"
    assert new_obs["id"].startswith("obs-")


def test_apply_curation_operations_rejects_low_sample_adds():
    existing = []
    ops = {"retire": [], "update": [], "add": [
        {"regime": "BULL", "claim": "too small", "sample_size": MIN_SAMPLE_FOR_NEW - 1, "win_rate": 0.5, "evidence_tickers": []}
    ]}
    result = apply_curation_operations(existing, ops, now="2026-05-27T12:00:00Z")
    assert result == []


def test_apply_curation_operations_caps_at_max():
    existing = [
        {"id": f"o{i}", "regime": "BULL", "claim": f"c{i}", "sample_size": 5, "win_rate": 0.5,
         "first_seen": "2026-01-01T00:00:00Z", "last_updated": f"2026-05-{i+1:02d}T00:00:00Z"}
        for i in range(MAX_OBSERVATIONS_PER_PORTFOLIO)
    ]
    ops = {"retire": [], "update": [], "add": [
        {"regime": "BULL", "claim": "newest", "sample_size": 10, "win_rate": 0.8, "evidence_tickers": []}
    ]}
    result = apply_curation_operations(existing, ops, now="2026-05-27T12:00:00Z")
    assert len(result) == MAX_OBSERVATIONS_PER_PORTFOLIO
    # The newest add should be present; the oldest last_updated should be gone
    assert any(o["claim"] == "newest" for o in result)
    assert "o0" not in {o["id"] for o in result}  # oldest last_updated dropped


def test_run_reflection_full_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    _seed(tmp_path, "p1", observations=[
        {"id": "obs-existing-1", "regime": "BULL", "claim": "Existing", "sample_size": 10, "win_rate": 0.5,
         "first_seen": "2026-05-01T00:00:00Z", "last_updated": "2026-05-01T00:00:00Z"}
    ])

    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps({
        "retire": [],
        "update": [{"id": "obs-existing-1", "claim": "Refreshed claim", "sample_size": 15, "win_rate": 0.6, "evidence_tickers": ["NVDA"]}],
        "add": [{"regime": "BULL", "claim": "New BULL pattern with confirmation criterion", "sample_size": 5, "win_rate": 0.6, "evidence_tickers": ["HIMX","NVEC"]}],
        "add_shared": [{"regime": "ALL", "claim": "Cross-portfolio factor pattern", "sample_size": 22, "win_rate": 0.45, "evidence_tickers": ["X","Y"]}],
    }))]
    fake_client.messages.create.return_value = fake_response

    with patch("reflection.get_ai_client", return_value=fake_client):
        ok = run_reflection(
            portfolio_id="p1",
            regime="BULL",
            recent_trades=[{"ticker": "NVDA", "top_factors": [("price_momentum", 80)], "pnl_pct": 5.0, "holding_days": 8, "regime": "BULL",
                            "entry_date": "2026-05-20", "exit_date": "2026-05-28", "exit_reason": "TAKE_PROFIT",
                            "entry_reasoning": "AI demand thesis", "exit_summary": "Hit target", "pattern_tags": []}],
        )
    assert ok is True

    obs = read_observations("p1")
    refreshed = next(o for o in obs if o["id"] == "obs-existing-1")
    assert refreshed["claim"] == "Refreshed claim"
    assert refreshed["sample_size"] == 15
    assert any(o["claim"].startswith("New BULL pattern") for o in obs)

    shared = read_shared_observations()
    assert any(o["claim"] == "Cross-portfolio factor pattern" for o in shared)
    cross = next(o for o in shared if o["claim"] == "Cross-portfolio factor pattern")
    assert "p1" in cross.get("portfolios", [])


def test_run_reflection_fails_soft_on_api_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    (tmp_path / "portfolios" / "p1").mkdir(parents=True)
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = Exception("rate limit")
    with patch("reflection.get_ai_client", return_value=fake_client):
        result = run_reflection(portfolio_id="p1", regime="BULL", recent_trades=[
            {"ticker": "X", "top_factors": [("price_momentum", 70)], "pnl_pct": 1.0, "holding_days": 5, "regime": "BULL",
             "entry_date": "2026-05-20", "exit_date": "2026-05-25", "exit_reason": "TAKE_PROFIT",
             "entry_reasoning": "", "exit_summary": "", "pattern_tags": []}
        ])
    assert result is False


def test_run_reflection_skips_when_no_trades(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    (tmp_path / "portfolios" / "p1").mkdir(parents=True)
    fake_client = MagicMock()
    with patch("reflection.get_ai_client", return_value=fake_client):
        result = run_reflection(portfolio_id="p1", regime="BULL", recent_trades=[])
    assert result is False
    fake_client.messages.create.assert_not_called()
