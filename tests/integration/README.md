# Integration Test Suite — analyze→execute Pipeline

Hermetic, regression-focused tests for `run_unified_analysis()` and
`execute_approved_actions()` in `scripts/unified_analysis.py`.

## Running

```
python3 -m pytest tests/integration/ -v
```

Full project suite:
```
python3 -m pytest tests/ scripts/tests/
```

With coverage:
```
python3 -m pytest tests/integration/ --cov=unified_analysis --cov-report=term-missing
```

## Layout

```
tests/integration/
├── conftest.py              # fixtures: seed_portfolio, mock_anthropic, mock_yfinance,
│                            #           mock_public_com, mock_bars, mock_info_prewarm,
│                            #           mock_news_off; auto-applied: mock_social_off,
│                            #           _no_real_anthropic_key
├── fixtures/
│   ├── seed_portfolio.py    # SeededPortfolio + factory helper
│   └── mock_responses.py    # canned Anthropic payloads (allocator + reviewer)
├── test_analyze_pipeline.py # tests 1-5 (analyze branches + analyze-side regressions)
├── test_execute_pipeline.py # tests 6-15 (execute + 8 known regressions)
└── test_pipeline_e2e.py     # tests 16-17 (full round-trip; 17 xfails until Fix 3)
```

## Strategy

- **Real fixture portfolios in `data/portfolios/_test_pipeline_<hex>/`** — the
  internal trading code runs against real CSVs/JSON. No path monkeypatching.
  Cleaned up after each test (orphan sweep at session start).
- **All external services mocked**: Anthropic, yfinance, Public.com, social,
  news. Patched at *every* consumer reference because `from x import y` rebinds
  the name in the importing module.
- **`mode: "live"`** in fixture config so loaders read `positions.csv` (not
  `positions_paper.csv`). `paper_trading.enabled` is harmless — file paths
  resolve from `mode`.

## Adding a Test

1. Use the `seed_portfolio` factory fixture:
   ```python
   sp = seed_portfolio(
       starting_capital=100_000.0,
       config_overrides={"ai_driven": True},
       positions=[...],
       transactions=[...],
       watchlist=[...],
   )
   ```
2. Set price mocks BEFORE running pipeline:
   ```python
   mock_yfinance.prices = {"AAPL": 150.0}
   mock_public_com.prices = {"AAPL": 150.0}
   ```
3. Queue an Anthropic response if the path calls Claude:
   ```python
   mock_anthropic.next_response = ai_allocator_buy_basket(["AAPL"])
   ```
4. Call the function under test and assert on either the return dict or the
   files written (under `sp.transactions_path()`, `sp.positions_path()`, etc.).

## Coverage Status

`scripts/unified_analysis.py` — **74% line coverage** (target: 80%).
All 3 analysis branches and 8 known regressions are covered. Remaining gaps:
- Watchlist scoring path inside enhanced_layers (lines 560-625)
- Partial-sell handling and modified actions (lines 1080-1189)
- `_run_ai_driven_analysis` edge cases (warning suppression, empty candidates)
- `if __name__ == "__main__"` CLI block (~20 unreachable lines)

These can be added incrementally as Fix 16 (split god functions) progresses.

## Known Status

- **Test 17** (failure recovery) is **xfail** until Fix 3 (atomic transactions+positions
  rollback) lands. The test codifies the desired post-Fix-3 invariant; once Fix 3
  ships, remove the `@pytest.mark.xfail` decorator and it should pass.

## Performance

- Full integration suite: ~4 seconds
- With coverage: ~6.5 seconds
- All 17 tests run hermetically; no real network calls.
