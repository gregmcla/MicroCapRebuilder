# Screener Universe Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken ETF-holdings-based universe system (top-10 per ETF) with a `yfscreen` stock screener that returns complete, targeted ticker lists filtered by sector, industry, and market cap — with optional Claude refinement for thematic portfolios.

**Architecture:** A new `screener_provider.py` module queries Yahoo Finance's screener API via `yfscreen`, caches results for 24 hours, and returns ticker lists in the same format UniverseProvider expects. UniverseProvider gets a new `_load_screener_universe()` method that calls this provider. For thematic portfolios (defense-tech, gov-infra, tariff-moats), Claude optionally refines the screener results to match the strategy DNA. Portfolio configs get a new `screener` source block alongside existing sources. The strategy generator is updated to produce screener criteria for new portfolios.

**Tech Stack:** `yfscreen` (free Yahoo Finance screener wrapper, already installed), Python 3.12, existing `anthropic` SDK for Claude refinement.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/screener_provider.py` | **Create** | yfscreen wrapper: build queries from config, paginate, cache, filter US-listed |
| `scripts/universe_provider.py` | Modify | Add `_load_screener_universe()` calling screener_provider |
| `scripts/strategy_generator.py` | Modify | Generate `screener` config + optional `ai_refinement` prompt for new portfolios |
| `data/portfolios/gov-infra/config.json` | Modify | Test portfolio: add screener config |
| `scripts/tests/test_screener_provider.py` | **Create** | Tests for screener query building, filtering, caching |

---

### Task 1: Create Screener Provider Module

**Files:**
- Create: `scripts/screener_provider.py`
- Create: `scripts/tests/test_screener_provider.py`

- [ ] **Step 1: Write failing tests for query building**

```python
# scripts/tests/test_screener_provider.py
"""Tests for the yfscreen-based screener provider."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from screener_provider import build_screener_filters


def test_build_filters_single_sector():
    """Single sector produces correct yfscreen filter list."""
    config = {
        "sectors": ["Industrials"],
        "market_cap_min": 500000000,
        "market_cap_max": 15000000000,
        "region": "us",
    }
    filters = build_screener_filters(config)
    assert ["eq", ["region", "us"]] in filters
    assert ["eq", ["sector", "Industrials"]] in filters
    assert ["btwn", ["intradaymarketcap", 500000000, 15000000000]] in filters


def test_build_filters_multiple_industries():
    """Multiple industries each get their own eq filter."""
    config = {
        "industries": ["Engineering & Construction", "Building Products & Equipment"],
        "market_cap_min": 300000000,
        "market_cap_max": 10000000000,
        "region": "us",
    }
    filters = build_screener_filters(config)
    assert ["eq", ["industry", "Engineering & Construction"]] in filters
    assert ["eq", ["industry", "Building Products & Equipment"]] in filters


def test_build_filters_no_sector_or_industry():
    """Config with only market cap still produces valid filters."""
    config = {
        "market_cap_min": 1000000000,
        "market_cap_max": 50000000000,
        "region": "us",
    }
    filters = build_screener_filters(config)
    assert ["eq", ["region", "us"]] in filters
    assert ["btwn", ["intradaymarketcap", 1000000000, 50000000000]] in filters
    # No sector/industry filters
    assert not any(f[1][0] == "sector" for f in filters if len(f) == 2)


def test_filter_us_listed():
    """Foreign tickers (dots, 5+ chars) should be filtered out."""
    from screener_provider import filter_us_listed
    tickers = ["AAPL", "CRWOF", "STBBF", "SKBSY", "ACM", "STRL", "AVHNY", "BLD.TO"]
    result = filter_us_listed(tickers)
    assert "AAPL" in result
    assert "ACM" in result
    assert "STRL" in result
    assert "CRWOF" not in result  # 5 chars, OTC
    assert "BLD.TO" not in result  # dot = foreign exchange
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest scripts/tests/test_screener_provider.py -v`
Expected: FAIL — `screener_provider` module not found

- [ ] **Step 3: Implement screener_provider.py**

```python
#!/usr/bin/env python3
"""
Screener Provider — builds stock universes using Yahoo Finance screener API.

Replaces ETF-holdings-based universe construction with direct market screening
by sector, industry, and market cap. Uses yfscreen package (free, no API key).
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"


def build_screener_filters(config: dict) -> list:
    """Build yfscreen filter list from screener config.

    Args:
        config: dict with optional keys: sectors, industries, market_cap_min,
                market_cap_max, region (default "us")

    Returns:
        List of yfscreen filter tuples: [["eq", ["field", "value"]], ...]
    """
    filters = []

    region = config.get("region", "us")
    filters.append(["eq", ["region", region]])

    for sector in config.get("sectors", []):
        filters.append(["eq", ["sector", sector]])

    for industry in config.get("industries", []):
        filters.append(["eq", ["industry", industry]])

    cap_min = config.get("market_cap_min", 0)
    cap_max = config.get("market_cap_max", 999999999999)
    filters.append(["btwn", ["intradaymarketcap", cap_min, cap_max]])

    return filters


def filter_us_listed(tickers: list) -> list:
    """Filter to US-listed tickers only.

    Removes ADRs (5+ char symbols ending in F/Y), OTC tickers,
    and foreign exchange suffixes (dots).
    """
    us_tickers = []
    for t in tickers:
        if "." in t:
            continue
        if len(t) >= 5 and t[-1] in ("F", "Y"):
            continue
        us_tickers.append(t)
    return us_tickers


def run_screen(config: dict, portfolio_id: str = None) -> list:
    """Run a stock screen and return list of US-listed ticker strings.

    Args:
        config: screener config dict with sectors/industries/market_cap
        portfolio_id: for cache path

    Returns:
        List of ticker strings
    """
    # Check cache first
    cache = _load_cache(portfolio_id)
    if cache:
        return cache

    from yfscreen import create_query, create_payload, get_data

    filters = build_screener_filters(config)
    query = create_query(filters)

    all_symbols = []
    offset = 0
    page_size = 250
    max_pages = 20  # safety cap: 5000 tickers max

    for _ in range(max_pages):
        payload = create_payload(
            "equity", query,
            sort_field="intradaymarketcap",
            sort_type="DESC",
        )
        payload["size"] = page_size
        payload["offset"] = offset

        try:
            result = get_data(payload)
        except Exception as e:
            print(f"  [screener] Page at offset {offset} failed: {e}")
            break

        if result.empty:
            break

        symbols = result["symbol"].tolist()
        all_symbols.extend(symbols)

        if len(result) < page_size:
            break
        offset += page_size

    # Filter to US-listed only
    us_symbols = filter_us_listed(all_symbols)

    # Deduplicate
    seen = set()
    unique = []
    for s in us_symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    print(f"  [screener] {len(all_symbols)} raw → {len(unique)} US-listed unique tickers")

    # Cache results
    _save_cache(unique, portfolio_id)

    return unique


def _cache_path(portfolio_id: str = None) -> Path:
    """Get cache file path."""
    if portfolio_id:
        return DATA_DIR / "portfolios" / portfolio_id / "screener_cache.json"
    return DATA_DIR / "screener_cache.json"


def _load_cache(portfolio_id: str = None, max_age_hours: int = 24) -> Optional[list]:
    """Load cached screener results if fresh enough."""
    path = _cache_path(portfolio_id)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
        cached_at = datetime.fromisoformat(data["timestamp"])
        age_hours = (datetime.now() - cached_at).total_seconds() / 3600

        if age_hours < max_age_hours:
            tickers = data["tickers"]
            print(f"  [screener] Using cached results ({len(tickers)} tickers, {age_hours:.1f}h old)")
            return tickers
    except Exception as e:
        print(f"  [screener] Cache read failed: {e}")

    return None


def _save_cache(tickers: list, portfolio_id: str = None):
    """Save screener results to cache."""
    path = _cache_path(portfolio_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now().isoformat(),
            "count": len(tickers),
            "tickers": tickers,
        }
        path.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"  [screener] Cache write failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest scripts/tests/test_screener_provider.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/screener_provider.py scripts/tests/test_screener_provider.py
git commit -m "feat: add screener_provider module using yfscreen for universe building"
```

---

### Task 2: Integrate Screener into UniverseProvider

**Files:**
- Modify: `scripts/universe_provider.py:90-132`
- Test: `scripts/tests/test_screener_provider.py` (append)

- [ ] **Step 1: Write failing test**

Append to `scripts/tests/test_screener_provider.py`:

```python
def test_universe_provider_screener_config_recognized():
    """UniverseProvider should recognize screener source in config."""
    # Verify the config key is read
    config = {
        "universe": {
            "enabled": True,
            "sources": {
                "screener": {
                    "enabled": True,
                    "sectors": ["Industrials"],
                    "market_cap_min": 500000000,
                    "market_cap_max": 15000000000,
                }
            }
        }
    }
    screener_config = config["universe"]["sources"].get("screener", {})
    assert screener_config.get("enabled") is True
    assert "Industrials" in screener_config.get("sectors", [])
```

- [ ] **Step 2: Run test to verify it passes (structural)**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest scripts/tests/test_screener_provider.py::test_universe_provider_screener_config_recognized -v`

- [ ] **Step 3: Add screener source to UniverseProvider.__init__**

In `scripts/universe_provider.py`, after line 105 (`self.exchange_listings_enabled = ...`), add:

```python
        self.screener_enabled = sources_config.get("screener", {}).get("enabled", False)
        self.screener_config = sources_config.get("screener", {})
```

- [ ] **Step 4: Add _load_screener_universe method**

In `scripts/universe_provider.py`, after `_load_exchange_listings()` method, add:

```python
    def _load_screener_universe(self):
        """Load tickers from yfscreen stock screener."""
        try:
            from screener_provider import run_screen
            tickers = run_screen(self.screener_config, portfolio_id=self.portfolio_id)

            for ticker in tickers:
                self._add_ticker(
                    ticker=ticker,
                    tier=UniverseTier.CORE,
                    source="screener",
                    sector="",
                )

            print(f"  Screener: {len(tickers)} tickers loaded as CORE")

        except ImportError:
            print("Warning: screener_provider not available")
        except Exception as e:
            print(f"Warning: Screener universe load failed: {e}")
```

- [ ] **Step 5: Call _load_screener_universe in _build_universe**

In `scripts/universe_provider.py`, in `_build_universe()` (line ~114), add after the exchange_listings block (line ~126):

```python
        # 4. Load screener results
        if self.screener_enabled:
            self._load_screener_universe()
```

Update the comment numbering: finalize_tiers becomes step 5, save_cache becomes step 6.

- [ ] **Step 6: Run all tests**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest scripts/tests/test_screener_provider.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add scripts/universe_provider.py scripts/tests/test_screener_provider.py
git commit -m "feat: integrate screener_provider into UniverseProvider"
```

---

### Task 3: Test with Gov Infra Portfolio

**Files:**
- Modify: `data/portfolios/gov-infra/config.json`

- [ ] **Step 1: Add screener config to Gov Infra**

In `data/portfolios/gov-infra/config.json`, in the `universe.sources` section, add a `screener` block:

```json
"screener": {
    "enabled": true,
    "sectors": ["Industrials", "Basic Materials"],
    "industries": [
        "Engineering & Construction",
        "Building Products & Equipment",
        "Infrastructure Operations",
        "Farm & Heavy Construction Machinery",
        "Specialty Industrial Machinery",
        "Building Materials"
    ],
    "market_cap_min": 300000000,
    "market_cap_max": 15000000000,
    "region": "us"
}
```

Optionally set `etf_holdings.enabled` to `false` to compare results purely from screener.

- [ ] **Step 2: Test the universe builds correctly**

Run:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from universe_provider import UniverseProvider
up = UniverseProvider(portfolio_id='gov-infra')
universe = up.get_todays_scan_universe()
print(f'Universe size: {len(universe)}')
print(f'Core: {len(up.get_core_tickers())}')
print(f'Sample: {sorted(universe)[:20]}')
"
```

Expected: 100+ tickers (vs previous 38), dominated by actual infrastructure companies.

- [ ] **Step 3: Run a scan to verify watchlist quality**

Run:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from watchlist_manager import update_watchlist
stats = update_watchlist(run_discovery=True, portfolio_id='gov-infra')
print(stats)
"
```

Verify the watchlist now contains infrastructure companies, not pizza chains.

- [ ] **Step 4: Commit**

```bash
git add data/portfolios/gov-infra/config.json
git commit -m "feat: enable screener-based universe for gov-infra portfolio"
```

---

### Task 4: Add Claude Refinement for Thematic Portfolios

**Files:**
- Modify: `scripts/screener_provider.py`
- Test: `scripts/tests/test_screener_provider.py` (append)

- [ ] **Step 1: Write failing test**

Append to `scripts/tests/test_screener_provider.py`:

```python
def test_refinement_config_structure():
    """AI refinement config must have enabled flag and prompt."""
    config = {
        "enabled": True,
        "prompt": "Select companies that benefit from infrastructure spending",
    }
    assert config["enabled"] is True
    assert "infrastructure" in config["prompt"].lower()


def test_refinement_skipped_when_disabled():
    """Refinement should return original tickers when disabled."""
    from screener_provider import maybe_refine_with_claude
    tickers = ["AAPL", "MSFT", "GOOG"]
    config = {"enabled": False}
    result = maybe_refine_with_claude(tickers, config, portfolio_id="test")
    assert result == tickers


def test_refinement_skipped_when_too_few_tickers():
    """Refinement should skip if fewer than 50 tickers (not enough to filter)."""
    from screener_provider import maybe_refine_with_claude
    tickers = ["AAPL"] * 10  # only 10
    config = {"enabled": True, "prompt": "test"}
    result = maybe_refine_with_claude(tickers, config, portfolio_id="test")
    assert result == tickers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest scripts/tests/test_screener_provider.py::test_refinement_skipped_when_disabled -v`
Expected: FAIL — `maybe_refine_with_claude` not found

- [ ] **Step 3: Implement maybe_refine_with_claude**

Add to `scripts/screener_provider.py`:

```python
def maybe_refine_with_claude(
    tickers: list,
    refinement_config: dict,
    portfolio_id: str = None,
) -> list:
    """Optionally refine screener results using Claude.

    For thematic portfolios where industry codes don't capture the full thesis,
    Claude filters the screener results to match the strategy DNA.

    Args:
        tickers: list of ticker strings from screener
        refinement_config: {"enabled": bool, "prompt": str}
        portfolio_id: for cache path

    Returns:
        Filtered list of tickers (or original if refinement disabled/fails)
    """
    if not refinement_config.get("enabled", False):
        return tickers

    if len(tickers) < 50:
        print(f"  [refinement] Skipping — only {len(tickers)} tickers (need 50+)")
        return tickers

    prompt_text = refinement_config.get("prompt", "")
    if not prompt_text:
        return tickers

    # Check 7-day cache
    cache = _load_refinement_cache(portfolio_id)
    if cache:
        return cache

    try:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            env_file = Path(__file__).parent.parent / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not api_key:
            print("  [refinement] No API key — skipping")
            return tickers

        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=120.0)

        ticker_list = ", ".join(tickers)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""You are filtering a stock universe for a thematic portfolio.

SCREENER RESULTS ({len(tickers)} tickers):
{ticker_list}

FILTER CRITERIA:
{prompt_text}

Return ONLY a JSON array of ticker symbols that match the criteria. Include tickers that clearly fit and exclude those that don't. Aim for 30-100 tickers.

Example: ["STRL", "ACM", "DY", "BLD"]"""
            }],
        )

        raw = response.content[0].text.strip()
        # Parse JSON array
        import re
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            import json
            refined = json.loads(match.group())
            refined = [str(t).upper().strip() for t in refined if isinstance(t, str)]
            # Only keep tickers that were in the original list
            valid = [t for t in refined if t in set(tickers)]
            print(f"  [refinement] Claude filtered {len(tickers)} → {len(valid)} tickers")

            _save_refinement_cache(valid, portfolio_id)
            return valid

    except Exception as e:
        print(f"  [refinement] Claude refinement failed (non-fatal): {e}")

    return tickers


def _refinement_cache_path(portfolio_id: str = None) -> Path:
    """Get refinement cache file path."""
    if portfolio_id:
        return DATA_DIR / "portfolios" / portfolio_id / "refinement_cache.json"
    return DATA_DIR / "refinement_cache.json"


def _load_refinement_cache(portfolio_id: str = None, max_age_days: int = 7) -> Optional[list]:
    """Load cached refinement results if fresh enough."""
    path = _refinement_cache_path(portfolio_id)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
        cached_at = datetime.fromisoformat(data["timestamp"])
        age_days = (datetime.now() - cached_at).total_seconds() / 86400

        if age_days < max_age_days:
            tickers = data["tickers"]
            print(f"  [refinement] Using cached refinement ({len(tickers)} tickers, {age_days:.1f}d old)")
            return tickers
    except Exception as e:
        print(f"  [refinement] Refinement cache read failed: {e}")

    return None


def _save_refinement_cache(tickers: list, portfolio_id: str = None):
    """Save refinement results to cache (7-day TTL)."""
    path = _refinement_cache_path(portfolio_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now().isoformat(),
            "count": len(tickers),
            "tickers": tickers,
        }
        path.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"  [refinement] Refinement cache write failed: {e}")
```

- [ ] **Step 4: Wire refinement into UniverseProvider**

In `scripts/universe_provider.py`, in `_load_screener_universe()`, after getting tickers from `run_screen()`, add:

```python
            # Optional AI refinement for thematic portfolios
            refinement_config = self.universe_config.get("sources", {}).get("ai_refinement", {})
            if refinement_config.get("enabled", False):
                from screener_provider import maybe_refine_with_claude
                tickers = maybe_refine_with_claude(tickers, refinement_config, portfolio_id=self.portfolio_id)
```

- [ ] **Step 5: Run all tests**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest scripts/tests/test_screener_provider.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/screener_provider.py scripts/universe_provider.py scripts/tests/test_screener_provider.py
git commit -m "feat: add Claude refinement for thematic portfolio universes"
```

---

### Task 5: Update Strategy Generator for New Portfolios

**Files:**
- Modify: `scripts/strategy_generator.py:32-79` (SUGGEST_CONFIG_PROMPT)
- Modify: `scripts/strategy_generator.py:107-179` (suggest_config_for_dna return)

- [ ] **Step 1: Update the Claude prompt to generate screener config**

In `scripts/strategy_generator.py`, update `SUGGEST_CONFIG_PROMPT` (line 32) to add screener fields to the JSON schema. Add these fields to the JSON template in the prompt:

```
  "screener": {{
    "sectors": ["1-3 sectors from: Basic Materials, Consumer Cyclical, Financial Services, Real Estate, Consumer Defensive, Healthcare, Utilities, Communication Services, Energy, Industrials, Technology"],
    "industries": ["3-8 specific industries within those sectors that match the thesis"],
    "market_cap_min": <integer in dollars, e.g. 500000000 for $500M>,
    "market_cap_max": <integer in dollars, e.g. 15000000000 for $15B>
  }},
  "ai_refinement_prompt": "1-2 sentence filter: what to include/exclude from screener results. Only needed for thematic strategies where industry codes don't fully capture the thesis. Empty string if sectors+industries are sufficient."
```

Add these guidelines to the prompt:
```
- screener.sectors: pick the 1-3 GICS sectors that contain the target companies.
- screener.industries: pick the specific Yahoo Finance industries within those sectors. Be precise — "Engineering & Construction" not just "Industrials". Use the exact industry names from Yahoo Finance.
- screener market cap: match the universe preset (microcap: 50M-2B, smallcap: 300M-5B, midcap: 500M-15B, largecap: 5B+, allcap: 50M-999B).
- ai_refinement_prompt: write a clear 1-2 sentence filter for thematic strategies. E.g., "Select companies that directly benefit from federal infrastructure spending — road/bridge builders, water system contractors, grid modernization suppliers. Exclude defense primes and pure logistics." Leave empty string for generic strategies where sector+industry filters are sufficient.
```

- [ ] **Step 2: Parse screener fields in suggest_config_for_dna**

In `scripts/strategy_generator.py`, in `suggest_config_for_dna()` (around line 168), add screener fields to the return dict:

```python
    screener_data = data.get("screener", {})
    screener_config = {
        "enabled": True,
        "sectors": [str(s) for s in screener_data.get("sectors", [])],
        "industries": [str(i) for i in screener_data.get("industries", [])],
        "market_cap_min": int(screener_data.get("market_cap_min", 500000000)),
        "market_cap_max": int(screener_data.get("market_cap_max", 15000000000)),
        "region": "us",
    }

    refinement_prompt = str(data.get("ai_refinement_prompt", ""))
    ai_refinement = {
        "enabled": bool(refinement_prompt),
        "prompt": refinement_prompt,
    }
```

Add to the return dict:
```python
        "screener": screener_config,
        "ai_refinement": ai_refinement,
```

- [ ] **Step 3: Update portfolio creation to include screener in config**

In `api/routes/portfolios.py`, where the portfolio config is built from `suggest_config_for_dna()` results, add the screener and ai_refinement sections to the universe sources. Read this file first to find the exact location where the config dict is assembled from the suggestion result.

The screener config goes into `config["universe"]["sources"]["screener"]` and ai_refinement goes into `config["universe"]["sources"]["ai_refinement"]`.

- [ ] **Step 4: Verify by creating a test portfolio**

Run:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from strategy_generator import suggest_config_for_dna
result = suggest_config_for_dna('Dividend-paying utilities and REITs with stable cash flows', 500000)
print('screener:', result.get('screener'))
print('ai_refinement:', result.get('ai_refinement'))
"
```

Expected: screener config with sectors=["Utilities", "Real Estate"], relevant industries, and appropriate market cap range.

- [ ] **Step 5: Commit**

```bash
git add scripts/strategy_generator.py api/routes/portfolios.py
git commit -m "feat: strategy generator produces screener config for new portfolios"
```

---

### Task 6: Add Gov Infra AI Refinement and Verify End-to-End

**Files:**
- Modify: `data/portfolios/gov-infra/config.json`

- [ ] **Step 1: Add ai_refinement config to Gov Infra**

In `data/portfolios/gov-infra/config.json`, in the `universe.sources` section, add:

```json
"ai_refinement": {
    "enabled": true,
    "prompt": "Select companies that directly benefit from US federal and state infrastructure spending — road and bridge builders, water system contractors, broadband deployers, grid modernization suppliers, aggregate and cement producers, heavy equipment for construction. Exclude defense contractors, pure logistics/shipping, airlines, and staffing agencies."
}
```

- [ ] **Step 2: Clear the screener cache to force fresh run**

```bash
rm -f /Users/gregmclaughlin/MicroCapRebuilder/data/portfolios/gov-infra/screener_cache.json
rm -f /Users/gregmclaughlin/MicroCapRebuilder/data/portfolios/gov-infra/refinement_cache.json
```

- [ ] **Step 3: Run full scan and verify results**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from universe_provider import UniverseProvider
up = UniverseProvider(portfolio_id='gov-infra')
universe = up.get_todays_scan_universe()
print(f'Final universe: {len(universe)} tickers')
print(f'Sample: {sorted(universe)[:30]}')
"
```

Expected: 30-100 tickers, all actual infrastructure companies (STRL, ACM, DY, BLD, GVA, ROAD, etc.)

- [ ] **Step 4: Run ANALYZE to verify Claude sees the improved universe**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from unified_analysis import run_unified_analysis
result = run_unified_analysis(dry_run=True, portfolio_id='gov-infra')
print(f'ai_mode: {result.get(\"ai_mode\")}')
print(f'approved: {len(result.get(\"approved\", []))}')
for a in result.get('approved', []):
    print(f'  {a.original.action_type} {a.original.ticker}')
"
```

Expected: Buy proposals for actual infrastructure companies, not pizza chains.

- [ ] **Step 5: Commit**

```bash
git add data/portfolios/gov-infra/config.json
git commit -m "feat: enable AI refinement for gov-infra — infrastructure-focused universe"
```

---

## Verification

After all tasks complete:

1. **Unit tests:** `python3 -m pytest scripts/tests/test_screener_provider.py -v` — all 8 pass
2. **Gov Infra universe:** 30-100 infra tickers (was 38 random mid-caps)
3. **Gov Infra watchlist:** Run scan, verify watchlist has actual infrastructure companies
4. **Gov Infra analyze:** Claude proposes infra buys, not pizza chains
5. **Other portfolios unaffected:** Run analyze on MAX portfolio, verify it still works (uses ETF path since no screener config)
6. **New portfolio creation:** Create a test portfolio via API, verify screener config is generated

## What Dies (Eventually)

Once all portfolios migrate to screener configs:
- ETF holdings as primary universe source (kept as fallback)
- Core/extended tiering complexity (screener results are already targeted, go straight to core)
- Curated universe JSON files (screener + refinement replaces manual curation)

These are NOT deleted in this plan — just superseded. Cleanup is a separate task after migration is verified.
