# Exchange Universe Coverage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the ETF-fallback-only universe (~838 tickers) with the full NASDAQ/NYSE exchange listing (~6,500 real stocks) for smallcap, midcap, largecap, and allcap portfolios, while leaving microcap unchanged.

**Architecture:** A new `ExchangeUniverseProvider` downloads two free public NASDAQ tab-delimited files, filters to real common stocks (no ETFs, no test issues, no special-purpose symbols), caches the result for 7 days, and returns a flat `List[str]`. `UniverseProvider` calls it as a third source when `exchange_listings.enabled = true` in config. Portfolio presets in `portfolio_registry.py` get updated to set that flag and bump `extended_max` to 3000.

**Tech Stack:** Python 3, `urllib.request` (stdlib — no new deps), existing `universe_provider.py` extension pattern.

---

## Task 1: Create `exchange_universe_provider.py`

**Files:**
- Create: `scripts/exchange_universe_provider.py`

**Context:**
NASDAQ publishes two nightly tab-delimited files of all US-listed securities:
- `https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt` — all tickers traded on NASDAQ systems
- `https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt` — NYSE Arca, BATS, etc.

**nasdaqtraded.txt column layout** (pipe-delimited):
```
Nasdaq Traded | Symbol | Security Name | Listing Exchange | Market Category | ETF | Round Lot Size | Test Issue | Financial Status | CQS Symbol | NASDAQ Symbol | NextShares
```
Filter: `parts[5] == "N"` (not ETF), `parts[7] == "N"` (not test issue), `parts[8] == "N"` (financial status normal), symbol is alpha-only, length ≤ 5, not a 5-char warrant/right/unit (skip if len==5 and last char in `W`, `R`, `U`).

**otherlisted.txt column layout** (pipe-delimited):
```
ACT Symbol | Security Name | Exchange | CQS Symbol | ETF | Round Lot Size | Test Issue | NASDAQ Symbol
```
Filter: `parts[4] == "N"` (not ETF), `parts[6] == "N"` (not test issue), same symbol quality checks.

**Expected counts after filtering:**
- nasdaqtraded: ~3,877 symbols
- otherlisted: ~2,632 symbols
- Combined unique: ~6,509 symbols

**Step 1: Write the file**

```python
#!/usr/bin/env python3
"""
Exchange Universe Provider for GScott.

Downloads NASDAQ exchange listing files to build a complete universe of
all US-listed common stocks. Used by UniverseProvider as a third source
alongside curated tickers and ETF holdings.

No API key required. Files are published daily by NASDAQ for free.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CACHE_FILE = DATA_DIR / "exchange_universe_cache.json"

CACHE_TTL_DAYS = 7

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
OTHER_LISTED_URL  = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


class ExchangeUniverseProvider:
    """
    Provides a complete list of US-listed common stock tickers from NASDAQ's
    free public exchange listing files.

    Caches results for 7 days. Falls back to stale cache if download fails.
    """

    def __init__(self, cache_file: Path = CACHE_FILE):
        self._cache_file = cache_file

    # ── Public API ──────────────────────────────────────────────────────────

    def get_tickers(self) -> List[str]:
        """Return all US common stock tickers, using cache when fresh."""
        cache = self._load_cache()
        if cache and self._is_fresh(cache):
            return cache["tickers"]

        try:
            tickers = self._download_and_parse()
            self._save_cache(tickers)
            print(f"  [ExchangeUniverse] Downloaded {len(tickers):,} tickers from exchange listings")
            return tickers
        except Exception as e:
            print(f"  [ExchangeUniverse] Download failed ({e}), using cached data")
            if cache:
                return cache["tickers"]
            return []

    # ── Internal ────────────────────────────────────────────────────────────

    def _download_and_parse(self) -> List[str]:
        """Download both NASDAQ files and return combined filtered ticker list."""
        tickers: set = set()
        tickers.update(self._parse_nasdaq_traded())
        tickers.update(self._parse_other_listed())
        return sorted(tickers)

    def _parse_nasdaq_traded(self) -> set:
        """Parse nasdaqtraded.txt — all tickers traded on NASDAQ systems."""
        symbols = set()
        lines = self._fetch_lines(NASDAQ_TRADED_URL)
        for line in lines[1:]:  # skip header
            if line.startswith("File Creation"):
                break
            parts = line.split("|")
            if len(parts) < 9:
                continue
            # parts[5]=ETF, parts[7]=Test Issue, parts[8]=Financial Status
            if parts[5] != "N" or parts[7] != "Y" or parts[8] != "N":
                # ETF must be N, Test Issue must NOT be Y, FinStatus must be N
                pass
            if parts[5] == "N" and parts[7] == "N" and parts[8] == "N":
                sym = parts[1].strip()
                if self._is_valid_symbol(sym):
                    symbols.add(sym)
        return symbols

    def _parse_other_listed(self) -> set:
        """Parse otherlisted.txt — NYSE Arca, BATS, and other exchanges."""
        symbols = set()
        lines = self._fetch_lines(OTHER_LISTED_URL)
        for line in lines[1:]:  # skip header
            if line.startswith("File Creation"):
                break
            parts = line.split("|")
            if len(parts) < 7:
                continue
            # parts[4]=ETF, parts[6]=Test Issue
            if parts[4] == "N" and parts[6] == "N":
                sym = parts[0].strip()
                if self._is_valid_symbol(sym):
                    symbols.add(sym)
        return symbols

    def _is_valid_symbol(self, sym: str) -> bool:
        """Return True if this looks like a real common stock symbol."""
        if not sym or not sym.isalpha():
            return False
        if len(sym) > 5:
            return False
        # Exclude 5-char SPAC derivatives: warrants (W), rights (R), units (U)
        if len(sym) == 5 and sym[-1] in ("W", "R", "U"):
            return False
        return True

    def _fetch_lines(self, url: str) -> List[str]:
        """Download a URL and return its lines."""
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8").splitlines()

    def _is_fresh(self, cache: dict) -> bool:
        """Return True if cache was populated within TTL."""
        ts = cache.get("timestamp")
        if not ts:
            return False
        try:
            age = datetime.now() - datetime.fromisoformat(ts)
            return age < timedelta(days=CACHE_TTL_DAYS)
        except (ValueError, TypeError):
            return False

    def _load_cache(self) -> dict:
        """Load cache file, return empty dict if missing/corrupt."""
        if not self._cache_file.exists():
            return {}
        try:
            with open(self._cache_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_cache(self, tickers: List[str]):
        """Save tickers to cache with timestamp."""
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "count": len(tickers),
                "tickers": tickers,
            }, f)
```

**Step 2: Verify file is created**

```bash
ls /Users/gregmclaughlin/MicroCapRebuilder/scripts/exchange_universe_provider.py
```

**Step 3: Smoke-test the provider**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/scripts
python3 -c "
from exchange_universe_provider import ExchangeUniverseProvider
p = ExchangeUniverseProvider()
tickers = p.get_tickers()
print(f'Total tickers: {len(tickers)}')
print(f'Sample: {tickers[:10]}')
assert len(tickers) > 5000, f'Expected 5000+, got {len(tickers)}'
assert 'AAPL' in tickers
assert 'MSFT' in tickers
assert 'NVDA' in tickers
print('PASS')
"
```
Expected: `Total tickers: ~6500`, `PASS`

**Step 4: Verify cache file written**

```bash
python3 -c "
import json
cache = json.load(open('/Users/gregmclaughlin/MicroCapRebuilder/data/exchange_universe_cache.json'))
print('Count:', cache['count'])
print('Timestamp:', cache['timestamp'])
assert cache['count'] > 5000
print('PASS')
"
```

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add scripts/exchange_universe_provider.py
git commit -m "Add ExchangeUniverseProvider: NASDAQ/NYSE listing files, 7-day cache"
```

---

## Task 2: Integrate into `UniverseProvider`

**Files:**
- Modify: `scripts/universe_provider.py` — `__init__` (line ~100), `_build_universe` (line ~112), add new method

**Context:**
`UniverseProvider.__init__` reads source toggles from config (e.g. `self.curated_enabled`, `self.etf_enabled`). `_build_universe` calls `_load_curated()` and `_load_etf_holdings()` then `_finalize_tiers()`. We add a third source in the same pattern.

**Step 1: Add the `exchange_listings_enabled` toggle to `__init__`**

In `universe_provider.py` around line 103, after `self.etf_enabled = ...`, add:

```python
        self.exchange_listings_enabled = sources_config.get("exchange_listings", {}).get("enabled", False)
```

**Step 2: Call `_load_exchange_listings()` in `_build_universe`**

Replace the existing `_build_universe` method:

```python
    def _build_universe(self):
        """Build the universe from all sources."""
        # 1. Load curated universe
        if self.curated_enabled:
            self._load_curated()

        # 2. Load ETF holdings
        if self.etf_enabled:
            self._load_etf_holdings()

        # 3. Load exchange listings (full NASDAQ/NYSE file)
        if self.exchange_listings_enabled:
            self._load_exchange_listings()

        # 4. Deduplicate and assign final tiers
        self._finalize_tiers()

        # 5. Save cache
        self._save_cache()
```

**Step 3: Add the `_load_exchange_listings` method**

Add after `_load_etf_holdings` (around line 181):

```python
    def _load_exchange_listings(self):
        """Load tickers from the full NASDAQ/NYSE exchange listing files."""
        try:
            from exchange_universe_provider import ExchangeUniverseProvider
            provider = ExchangeUniverseProvider()
            tickers = provider.get_tickers()
            for ticker in tickers:
                # Exchange listings go to extended tier
                self._add_ticker(ticker, UniverseTier.EXTENDED, "EXCHANGE_LISTING", "")
        except ImportError as e:
            print(f"Warning: Could not load exchange listings: {e}")
        except Exception as e:
            print(f"Warning: Error loading exchange listings: {e}")
```

**Step 4: Verify TypeScript-free Python compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/scripts
python3 -c "from universe_provider import UniverseProvider; print('import OK')"
```
Expected: `import OK`

**Step 5: Smoke-test with exchange_listings disabled (default)**

```bash
python3 -c "
from universe_provider import UniverseProvider
p = UniverseProvider()  # no portfolio_id = default config, exchange_listings off
stats = p.get_stats()
print('Sources:', stats['sources'])
assert 'EXCHANGE_LISTING' not in stats['sources'], 'Should not load exchange listings by default'
print('PASS')
"
```
Expected: `PASS` (no EXCHANGE_LISTING source, universe unchanged at ~838)

**Step 6: Smoke-test with exchange_listings enabled via config override**

```bash
python3 -c "
from universe_provider import UniverseProvider

# Manually inject a config that enables exchange listings
class PatchedProvider(UniverseProvider):
    def __init__(self):
        from pathlib import Path
        self.portfolio_id = None
        self.config = {
            'universe': {
                'sources': {
                    'exchange_listings': {'enabled': True},
                    'etf_holdings': {'enabled': False},
                    'curated': {'enabled': False},
                },
                'tiers': {
                    'extended': {'max_tickers': 9999}
                }
            }
        }
        self.universe_config = self.config['universe']
        self.enabled = True
        self.core_max = 100
        self.extended_max = 9999
        sources = self.universe_config.get('sources', {})
        self.curated_enabled = sources.get('curated', {}).get('enabled', True)
        self.etf_enabled = sources.get('etf_holdings', {}).get('enabled', True)
        self.exchange_listings_enabled = sources.get('exchange_listings', {}).get('enabled', False)
        self._universe = {}
        self._core_tickers = []
        self._extended_tickers = []
        self._build_universe()

p = PatchedProvider()
stats = p.get_stats()
print('Total:', stats['total_count'])
print('Sources:', stats['sources'])
assert stats['total_count'] > 5000, f'Expected 5000+, got {stats[\"total_count\"]}'
assert 'EXCHANGE_LISTING' in stats['sources']
print('PASS')
"
```
Expected: `Total: ~6500`, `PASS`

**Step 7: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add scripts/universe_provider.py
git commit -m "Add exchange_listings source to UniverseProvider (disabled by default)"
```

---

## Task 3: Enable in portfolio presets and update `create_portfolio`

**Files:**
- Modify: `scripts/portfolio_registry.py` — `UNIVERSE_PRESETS` dict (~line 21), `create_portfolio` function (~line 395)

**Context:**
`UNIVERSE_PRESETS` defines per-universe settings including `etf_sources`. `create_portfolio()` reads these presets and writes them into `config["universe"]`. We need to:
1. Add `"exchange_listings_enabled": True` to `smallcap`, `midcap`, `largecap`, `allcap` presets
2. Add `"extended_max": 3000` to those same presets (default in `universe_provider.py` is 300)
3. Wire both into `create_portfolio()` so new portfolios pick them up

**Step 1: Add `exchange_listings_enabled` and `extended_max` to the four presets**

In `UNIVERSE_PRESETS`, update `smallcap`, `midcap`, `largecap`, `allcap` to add two keys each. Example for `smallcap`:

```python
    "smallcap": {
        "label": "Small-Cap ($300M–$2B)",
        # ... existing keys unchanged ...
        "etf_sources": ["IWM", "IJR", "VB"],
        "exchange_listings_enabled": True,   # ← add
        "extended_max": 3000,                # ← add
    },
```

Apply the same two lines to `midcap`, `largecap`, and `allcap`. Do NOT add them to `microcap` or `custom`.

For reference, here is what each preset's last few lines look like before the change:

`smallcap` (line ~68):
```python
        "etf_sources": ["IWM", "IJR", "VB"],
    },
```

`midcap` (line ~92):
```python
        "etf_sources": ["IJH", "VO", "MDY"],
    },
```

`largecap` (line ~116):
```python
        "etf_sources": ["SPY", "IVV", "VOO"],
    },
```

`allcap` (line ~140):
```python
        "etf_sources": [],  # Uses all DEFAULT_ETFS — no restriction
    },
```

After the change they become:

```python
        "etf_sources": ["IWM", "IJR", "VB"],
        "exchange_listings_enabled": True,
        "extended_max": 3000,
    },
```
(and same pattern for the other three)

**Step 2: Wire both keys in `create_portfolio()`**

Find the block in `create_portfolio()` that writes ETF config (~line 395). After the existing ETF lines, add:

```python
    config["universe"]["sources"]["etf_holdings"]["etfs"] = list(preset["etf_sources"])
    config["universe"]["filters"] = dict(preset["discovery_filters"])

    # Exchange listings: enabled for smallcap/midcap/largecap/allcap, off for microcap
    if "exchange_listings" not in config["universe"]["sources"]:
        config["universe"]["sources"]["exchange_listings"] = {}
    config["universe"]["sources"]["exchange_listings"]["enabled"] = preset.get("exchange_listings_enabled", False)

    # Extended tier size: larger for exchange-listing-enabled portfolios
    if "tiers" not in config["universe"]:
        config["universe"]["tiers"] = {}
    if "extended" not in config["universe"]["tiers"]:
        config["universe"]["tiers"]["extended"] = {}
    config["universe"]["tiers"]["extended"]["max_tickers"] = preset.get("extended_max", 1000)
```

**Step 3: Verify**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/scripts
python3 -c "
from portfolio_registry import UNIVERSE_PRESETS
for name in ['smallcap', 'midcap', 'largecap', 'allcap']:
    p = UNIVERSE_PRESETS[name]
    assert p.get('exchange_listings_enabled') == True, f'{name} missing exchange_listings_enabled'
    assert p.get('extended_max') == 3000, f'{name} missing extended_max'
    print(f'{name}: OK')

for name in ['microcap', 'custom']:
    p = UNIVERSE_PRESETS[name]
    assert p.get('exchange_listings_enabled', False) == False, f'{name} should NOT have exchange_listings'
    print(f'{name}: correctly disabled')

print('PASS')
"
```
Expected: all lines print OK/correctly disabled, then `PASS`.

**Step 4: Smoke-test create_portfolio wires the config correctly**

```bash
python3 -c "
from portfolio_registry import UNIVERSE_PRESETS, create_portfolio
import json, tempfile, os
from pathlib import Path

# Patch the portfolios dir to a temp dir so we don't create real data
import portfolio_registry as pr
orig = pr.PORTFOLIOS_DIR
tmp = Path(tempfile.mkdtemp())
pr.PORTFOLIOS_DIR = tmp

try:
    cfg = create_portfolio('test-allcap', 'Test AllCap', 50000.0, universe='allcap')
    sources = cfg['universe']['sources']
    assert sources['exchange_listings']['enabled'] == True
    assert cfg['universe']['tiers']['extended']['max_tickers'] == 3000
    print('allcap config: OK')

    cfg2 = create_portfolio('test-microcap', 'Test Micro', 50000.0, universe='microcap')
    sources2 = cfg2['universe']['sources']
    assert sources2.get('exchange_listings', {}).get('enabled', False) == False
    assert cfg2['universe']['tiers']['extended']['max_tickers'] == 1000
    print('microcap config: OK')
    print('PASS')
finally:
    pr.PORTFOLIOS_DIR = orig
    import shutil; shutil.rmtree(tmp)
"
```
Expected: `allcap config: OK`, `microcap config: OK`, `PASS`

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add scripts/portfolio_registry.py
git commit -m "Enable exchange listings for smallcap/midcap/largecap/allcap; extended_max=3000"
```

---

## Task 4: End-to-end verify and push

**Step 1: Verify full universe stats for a real portfolio**

This reads the actual `largeboi` config (largecap preset) to confirm the exchange listings path would activate.

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/scripts
python3 -c "
from universe_provider import UniverseProvider
# largeboi is a largecap portfolio
p = UniverseProvider(portfolio_id='largeboi')
stats = p.get_stats()
print('largeboi universe stats:')
for k, v in stats.items():
    print(f'  {k}: {v}')
"
```
Expected: if largeboi was created with the new registry, `EXCHANGE_LISTING` appears in sources. If it was created before this change, it won't (that's fine — existing portfolio configs aren't retroactively updated, only new ones get the new defaults).

**Note:** Existing portfolios (microcap, ai, new, largeboi) were created before this change and have their existing `config.json` on disk. The new exchange_listings config only flows in when a portfolio is *created* via `create_portfolio()`. To manually enable for an existing portfolio, set in its `config.json`:

```json
"universe": {
  "sources": {
    "exchange_listings": { "enabled": true }
  },
  "tiers": {
    "extended": { "max_tickers": 3000 }
  }
}
```

**Step 2: Verify microcap is unaffected**

```bash
python3 -c "
from universe_provider import UniverseProvider
p = UniverseProvider(portfolio_id='microcap')
stats = p.get_stats()
print('microcap sources:', stats['sources'])
assert 'EXCHANGE_LISTING' not in stats['sources']
print('PASS — microcap unchanged')
"
```

**Step 3: Push to GitHub**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git push origin main
```

---

## Summary

| File | Change |
|------|--------|
| `scripts/exchange_universe_provider.py` | New — downloads + caches NASDAQ/NYSE exchange files |
| `scripts/universe_provider.py` | Add `exchange_listings_enabled` toggle + `_load_exchange_listings()` |
| `scripts/portfolio_registry.py` | Add `exchange_listings_enabled: true` + `extended_max: 3000` to smallcap/midcap/largecap/allcap presets; wire both in `create_portfolio()` |

**Universe size after implementation:**
- microcap: ~838 (unchanged)
- smallcap/midcap/largecap/allcap (new portfolios): ~6,500 tickers in scope, capped to 3,000 extended by `extended_max`; portfolio-specific market cap/volume filters in `stock_discovery.py` further narrow per scan

**No changes to:** `stock_discovery.py`, `etf_holdings_provider.py`, API routes, dashboard, data files.
