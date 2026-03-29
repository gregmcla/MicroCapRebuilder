# Regime Advisory Mode + Microcap AI-Driven Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert microcap to AI-driven mode and replace mechanical regime constraints with rich regime context passed directly to Claude's allocation prompt.

**Architecture:** Two independent but related changes. (1) Microcap config gets `ai_driven: true` + `strategy_dna` — this makes all 9 portfolios AI-driven and the rule-based code path dead. (2) `RegimeAnalysis` gains richer fields (SMA gap %, 20d return); these flow through `unified_analysis.py` → `run_ai_allocation()` → `_build_allocation_prompt()` as a formatted context block so Claude can reason about regime rather than be mechanically constrained by it. The `get_position_size_multiplier` already returns 1.0 for all regimes — the only real gap is that Claude currently receives no regime context in the prompt at all.

**Tech Stack:** Python 3, FastAPI, Anthropic Claude API (`claude-opus-4-6`), yfinance/cached_download, pandas

---

## Key Findings (read before touching code)

- `get_position_size_multiplier()` already returns `1.0` for BEAR/SIDEWAYS/BULL — the mechanical multiplier is already neutralized. No change needed there.
- The AI prompt (`_build_allocation_prompt`) accepts `regime: MarketRegime` as a parameter but **never uses it in the prompt text**. Claude is flying blind on regime.
- The rule-based BEAR skip (`if regime == MarketRegime.BEAR: print("skipping buys")`) lives in the `else` branch — already unreachable for AI-driven portfolios. After microcap is converted, it is fully dead code.
- `RegimeAnalysis` dataclass currently has: `regime`, `benchmark_symbol`, `current_price`, `sma_50`, `sma_200`, `above_50`, `above_200`, `regime_strength`. It is missing SMA gap % and recent benchmark return — both needed for a useful prompt context block.
- **`state.regime_analysis` already exists** on `PortfolioState` (line 145 of `portfolio_state.py`, populated at load time via `_get_cached_regime_analysis()`). No extra API call needed in `unified_analysis.py` — just read `state.regime_analysis`.
- Microcap config path: `data/portfolios/microcap/config.json`

---

## Files Modified

| File | Change |
|---|---|
| `data/portfolios/microcap/config.json` | Add `ai_driven`, `strategy_dna`, `full_watchlist_prompt`, `total_watchlist_slots` |
| `scripts/market_regime.py` | Add `sma_200_gap_pct` and `recent_return_20d` fields to `RegimeAnalysis`; compute in `analyze_regime()` |
| `scripts/ai_allocator.py` | Add `regime_analysis` param to `run_ai_allocation` + `_build_allocation_prompt`; inject regime context block into prompt |
| `scripts/unified_analysis.py` | Pass `state.regime_analysis` to `run_ai_allocation` (one-line change) |

---

## Task 1: Convert Microcap to AI-Driven

**Files:**
- Modify: `data/portfolios/microcap/config.json`

### Context
Microcap is the only portfolio not in AI-driven mode. It uses `^RUT`/`IWM` as benchmark, ETF-held small caps as universe, 250 watchlist slots, `extended_max=1000`, `rotating_3day`. All of these stay — we're just flipping the allocation brain from rule-based layers to Claude.

- [ ] **Step 1: Add AI-driven fields to microcap config**

Open `data/portfolios/microcap/config.json`. Add these three top-level keys anywhere at the root level of the JSON object:

```json
"ai_driven": true,
"full_watchlist_prompt": true,
"strategy_dna": "Focused small-cap momentum and quality strategy. Hunt for micro and small-cap stocks (under $2B market cap) showing strong price momentum, solid fundamentals, and volume confirmation. Universe sourced from Russell 2000 ETF holdings. Run 6-10 concentrated positions max. Tight stops — small caps move fast and punish hesitation. Cut losers quickly, let winners run. Prioritize stocks with high value_timing and price_momentum scores. Avoid crowded sectors."
```

Also add `"total_watchlist_slots": 500` inside the existing `discovery.watchlist` object (alongside the existing `max_tickers`, `stale_days_threshold`, etc. keys). Do not touch any other existing keys.

- [ ] **Step 2: Verify config loads cleanly**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from stock_discovery import load_config
cfg = load_config('microcap')
print('ai_driven:', cfg.get('ai_driven'))
print('strategy_dna:', cfg.get('strategy_dna', '')[:60])
print('total_watchlist_slots:', cfg.get('discovery', {}).get('watchlist', {}).get('total_watchlist_slots'))
"
```

Expected output:
```
ai_driven: True
strategy_dna: Focused small-cap momentum and quality strategy. Hunt fo
total_watchlist_slots: 500
```

- [ ] **Step 3: Verify AI-driven path is taken in analysis**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from stock_discovery import load_config
cfg = load_config('microcap')
ai_driven = cfg.get('ai_driven', False)
strategy_dna = cfg.get('strategy_dna') or cfg.get('strategy', {}).get('strategy_dna')
print('ai_driven:', ai_driven)
print('strategy_dna present:', bool(strategy_dna))
assert ai_driven is True, 'ai_driven not set'
assert strategy_dna, 'strategy_dna missing'
print('PASS')
"
```

- [ ] **Step 4: Commit**

```bash
git add data/portfolios/microcap/config.json
git commit -m "feat: convert microcap portfolio to AI-driven mode

All 9 portfolios now AI-driven. Adds strategy_dna, full_watchlist_prompt,
and total_watchlist_slots=500 to microcap config. Rule-based allocation
path is now dead code across the entire system.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Enrich RegimeAnalysis with Gap and Return Data

**Files:**
- Modify: `scripts/market_regime.py`

### Context
`RegimeAnalysis` is a dataclass defined at the top of `market_regime.py` (around line 40). We need two new fields: `sma_200_gap_pct` (how far current price is from the 200d SMA, signed %) and `recent_return_20d` (benchmark's return over the last 20 trading days as %). Both are computable inside `analyze_regime()` which already has the full close series. Fields use default values so all existing call sites that don't pass them are unaffected.

- [ ] **Step 1: Add fields to RegimeAnalysis dataclass**

Find the `RegimeAnalysis` dataclass and add two new fields with defaults at the end:

```python
@dataclass
class RegimeAnalysis:
    """Detailed regime analysis data."""
    regime: MarketRegime
    benchmark_symbol: str
    current_price: float
    sma_50: float
    sma_200: float
    above_50: bool
    above_200: bool
    regime_strength: str  # "strong", "weak"
    sma_200_gap_pct: float = 0.0   # (price - sma_200) / sma_200 * 100, signed
    recent_return_20d: float = 0.0  # benchmark % return over last 20 trading days
```

- [ ] **Step 2: Compute new fields in analyze_regime()**

In `analyze_regime()`, after `sma_200` is computed and before the `return RegimeAnalysis(...)` call, add:

```python
# SMA 200 gap: signed percentage distance from 200d SMA
sma_200_gap_pct = round((current_price - sma_200) / sma_200 * 100, 2) if sma_200 > 0 else 0.0

# 20-day benchmark return
if len(close_col) >= 21:
    price_20d_ago = float(close_col.iloc[-21])
    recent_return_20d = round((current_price - price_20d_ago) / price_20d_ago * 100, 2) if price_20d_ago > 0 else 0.0
else:
    recent_return_20d = 0.0
```

Then add the two new fields to the existing `return RegimeAnalysis(...)` call at the end of `analyze_regime()`:

```python
return RegimeAnalysis(
    regime=regime,
    benchmark_symbol=symbol,
    current_price=round(current_price, 2),
    sma_50=round(sma_50, 2),
    sma_200=round(sma_200, 2),
    above_50=above_50,
    above_200=above_200,
    regime_strength=strength,
    sma_200_gap_pct=sma_200_gap_pct,
    recent_return_20d=recent_return_20d,
)
```

The failure-path `RegimeAnalysis(...)` calls in `get_regime_analysis()` do not need updating — they rely on the `= 0.0` defaults.

- [ ] **Step 3: Verify new fields populate correctly**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from market_regime import get_regime_analysis
a = get_regime_analysis(benchmark_symbol='^GSPC', fallback_benchmark='SPY')
print('regime:', a.regime.value)
print('sma_200_gap_pct:', a.sma_200_gap_pct)
print('recent_return_20d:', a.recent_return_20d)
assert isinstance(a.sma_200_gap_pct, float), 'sma_200_gap_pct not float'
assert isinstance(a.recent_return_20d, float), 'recent_return_20d not float'
assert a.sma_200_gap_pct != 0.0, 'gap is 0.0 — likely not computed'
print('PASS')
"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/market_regime.py
git commit -m "feat: enrich RegimeAnalysis with SMA gap and 20d return fields

Adds sma_200_gap_pct (signed % distance from 200d SMA) and
recent_return_20d (20-day benchmark return %) to RegimeAnalysis.
Both default to 0.0 so existing call sites are unaffected.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Thread RegimeAnalysis into run_ai_allocation

**Files:**
- Modify: `scripts/ai_allocator.py` (signature + prompt block)
- Modify: `scripts/unified_analysis.py` (one-line change to pass state.regime_analysis)

### Context
`PortfolioState` already carries `regime_analysis: RegimeAnalysis` (populated at load time in `portfolio_state.py` line 200). No extra calls or imports needed in `unified_analysis.py` — just pass `state.regime_analysis` through to `run_ai_allocation`.

`run_ai_allocation()` and `_build_allocation_prompt()` currently accept `regime: MarketRegime` but never use it in the prompt. We add an optional `regime_analysis` param to both and build a rich context block from it.

The existing `from market_regime import MarketRegime` import in `ai_allocator.py` needs `RegimeAnalysis` added. The import in `unified_analysis.py` (`from market_regime import MarketRegime, get_position_size_multiplier`) does NOT need to change.

- [ ] **Step 1: Update import in ai_allocator.py**

Find the line:
```python
from market_regime import MarketRegime
```
Replace with:
```python
from market_regime import MarketRegime, RegimeAnalysis
```

- [ ] **Step 2: Add regime_analysis param to run_ai_allocation**

Add one optional parameter at the end of `run_ai_allocation`'s signature:

```python
def run_ai_allocation(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    info_cache: Optional[dict] = None,
    regime_analysis: Optional[RegimeAnalysis] = None,
) -> list:
```

Pass it through in the `_build_allocation_prompt(...)` call inside `run_ai_allocation`:

```python
prompt = _build_allocation_prompt(
    state=state,
    layer1_sells=layer1_sells,
    scored_candidates=scored_candidates,
    sector_map=sector_map,
    regime=regime,
    warning_severity=warning_severity,
    strategy_dna=strategy_dna,
    available_cash=available_cash,
    info_cache=info_cache,
    full_watchlist=full_watchlist,
    regime_analysis=regime_analysis,
)
```

- [ ] **Step 3: Add regime_analysis param to _build_allocation_prompt**

Add one optional parameter at the end of `_build_allocation_prompt`'s signature:

```python
def _build_allocation_prompt(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    available_cash: float,
    info_cache: Optional[dict] = None,
    full_watchlist: bool = False,
    regime_analysis: Optional[RegimeAnalysis] = None,
) -> str:
```

- [ ] **Step 4: Build the regime context block inside _build_allocation_prompt**

Inside `_build_allocation_prompt`, after the `l1_block` is assembled and before the `prompt = f"""..."""` template, add:

```python
# Regime context block — rich market data for Claude's judgment
if regime_analysis is not None:
    gap = regime_analysis.sma_200_gap_pct
    ret_20d = regime_analysis.recent_return_20d
    gap_dir = "above" if gap >= 0 else "below"
    regime_block = (
        f"MARKET REGIME ({regime_analysis.benchmark_symbol}):\n"
        f"  Regime: {regime_analysis.regime.value} ({regime_analysis.regime_strength})\n"
        f"  Benchmark price: ${regime_analysis.current_price:.2f} — {gap:+.1f}% {gap_dir} 200d SMA\n"
        f"  50d SMA: ${regime_analysis.sma_50:.2f} | 200d SMA: ${regime_analysis.sma_200:.2f}\n"
        f"  20-day benchmark return: {ret_20d:+.1f}%\n"
        f"  Note: Regime is context for your judgment — not a mechanical constraint.\n"
        f"        Adjust selectivity and sizing as your mandate demands.\n"
    )
else:
    regime_block = f"MARKET REGIME: {regime.value}\n"
```

Then insert `{regime_block}` into the prompt template between `{sector_block}` and `{l1_block}`:

```python
prompt = f"""You are the portfolio manager for this trading portfolio. ...

{positions_block}

{sector_block}
{regime_block}
{l1_block}
{candidates_block}

HARD CONSTRAINTS ...
```

- [ ] **Step 5: Pass state.regime_analysis in unified_analysis.py**

In `scripts/unified_analysis.py`, find the existing `run_ai_allocation(...)` call (around line 153). Add `regime_analysis=state.regime_analysis` as a keyword argument:

```python
reviewed_actions = run_ai_allocation(
    state=state,
    layer1_sells=layer1_sell_actions,
    scored_candidates=scored_candidates,
    sector_map=sector_map,
    regime=regime,
    warning_severity=warning_severity,
    strategy_dna=strategy_dna,
    info_cache=info_cache,
    regime_analysis=state.regime_analysis,
)
```

No import changes needed in `unified_analysis.py`.

- [ ] **Step 6: Smoke test — verify regime block appears in prompt**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from market_regime import get_regime_analysis
from ai_allocator import _build_allocation_prompt
import pandas, types

ra = get_regime_analysis(benchmark_symbol='^GSPC', fallback_benchmark='SPY')

state = types.SimpleNamespace(
    positions=pandas.DataFrame(),
    total_equity=500000,
    cash=500000,
    num_positions=0,
    config={},
)

prompt = _build_allocation_prompt(
    state=state,
    layer1_sells=[],
    scored_candidates=[],
    sector_map={},
    regime=ra.regime,
    warning_severity='NORMAL',
    strategy_dna='Test strategy',
    available_cash=500000,
    regime_analysis=ra,
)
assert 'MARKET REGIME' in prompt, 'regime block missing from prompt'
assert '200d SMA' in prompt, '200d SMA data missing'
assert ra.benchmark_symbol in prompt, 'benchmark symbol missing'
assert ra.regime_analysis is None or True  # ra is RegimeAnalysis, not None
print('PASS — regime block present in prompt')
start = prompt.index('MARKET REGIME')
print(prompt[start:start+350])
"
```

- [ ] **Step 7: Commit**

```bash
git add scripts/ai_allocator.py scripts/unified_analysis.py
git commit -m "feat: regime advisory mode — pass rich market context to Claude

Claude now receives full regime context in the allocation prompt:
benchmark, regime label/strength, price vs 200d SMA (gap %), and
20-day benchmark return. Regime is framed as advisory context, not
a mechanical constraint. Uses state.regime_analysis already computed
at state load time — no extra API calls.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: End-to-End Verification

- [ ] **Step 1: Restart the API**

The API must be restarted — uvicorn does NOT auto-reload.

```bash
pkill -f "uvicorn api.main:app" 2>/dev/null || true
sleep 1
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8001 &
sleep 2
```

- [ ] **Step 2: Confirm microcap is AI-driven via API**

```bash
curl -s http://localhost:8001/api/microcap/state | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('ai_driven:', d.get('ai_driven'))
assert d.get('ai_driven') is True, 'ai_driven not True in API response'
print('PASS')
"
```

- [ ] **Step 3: Trigger a microcap analyze and confirm AI path**

```bash
curl -s -X POST http://localhost:8001/api/microcap/analyze | python3 -c "
import json, sys
d = json.load(sys.stdin)
actions = d.get('proposed_actions', [])
print(f'Actions proposed: {len(actions)}')
ai_actions = [a for a in actions if a.get('trade_rationale', {}).get('ai_reasoning')]
print(f'AI-reasoned actions: {len(ai_actions)}')
if ai_actions:
    print('Sample reasoning:', ai_actions[0]['trade_rationale']['ai_reasoning'][:150])
" || echo "Analyze timed out — check API terminal logs for '🤖 AI-DRIVEN MODE' line"
```

- [ ] **Step 4: Confirm regime block was in the prompt**

In the API terminal, look for the `AI Portfolio Thesis:` line after the analyze call. Then verify the regime block appeared by checking the prompt smoke test passed in Task 3 Step 6. Those two together confirm end-to-end flow.

- [ ] **Step 5: Push to GitHub**

```bash
git push origin main
```

---

## What Was NOT Changed (intentional)

- **`get_position_size_multiplier`** — already returns `1.0` for all regimes. No change needed.
- **`unified_analysis.py` imports** — `get_position_size_multiplier` stays imported; no `get_regime_analysis` import needed since `state.regime_analysis` is used directly.
- **Factor weight shifting in BEAR** — regime-adjusted scoring weights kept. They change which candidates float to the top of the list; they are signal, not a constraint.
- **Rule-based `else` branch** in `unified_analysis.py` — now dead code since all 9 portfolios are AI-driven. Left in place defensively; remove in a future cleanup pass.
- **Per-benchmark regime** — kept. ^RUT and ^GSPC legitimately diverge; each portfolio seeing its own benchmark regime as *context* is correct.
- **Max deployment ceiling** — not implemented. Claude already respects cash constraints via hard validation in `_validate_allocation`. Regime-based capital ceiling adds config complexity with minimal marginal value.
- **`should_buy_new_positions()`** in `market_regime.py` — still returns `False` for BEAR but is not called anywhere in the AI-driven path. Safe to ignore; note it exists if future code needs regime-based buy gating.
