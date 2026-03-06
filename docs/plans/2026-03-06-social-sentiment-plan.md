# Social Sentiment Risk Overlay Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a social heat risk signal (ApeWisdom + Stocktwits) that enriches watchlist entries and injects pump-risk warnings into the AI review layer during ANALYZE.

**Architecture:** New `scripts/social_sentiment.py` module with 2hr disk cache. Social heat (COLD/WARM/HOT/SPIKING) stored on watchlist entries and injected into AI review prompts. Never modifies quant scores. Gracefully degrades if APIs are down.

**Tech Stack:** Python `requests`, `dataclasses`, ApeWisdom free API (no key), Stocktwits free public API (no key), existing FastAPI routes, React dashboard (TypeScript).

---

## Task 1: `SocialSentimentProvider` — core module

**Files:**
- Create: `scripts/social_sentiment.py`
- Create: `tests/test_social_sentiment.py`

**Context:** Two free APIs. ApeWisdom returns top-100 trending tickers from Reddit stock subs in one call. Stocktwits returns last 30 messages per ticker with user-tagged bullish/bearish sentiment. Cache lives at `data/social_cache/{portfolio_id}_social.json`.

**Step 1: Write failing tests**

```python
# tests/test_social_sentiment.py
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, "scripts")

from social_sentiment import SocialSentimentProvider, SocialSignal, classify_heat


def test_classify_heat_cold():
    assert classify_heat(None, None) == "COLD"
    assert classify_heat(None, 40.0) == "COLD"
    assert classify_heat(80, 40.0) == "COLD"


def test_classify_heat_warm():
    assert classify_heat(75, None) == "WARM"   # rank 51-100
    assert classify_heat(None, 60.0) == "WARM" # 55-65% bullish


def test_classify_heat_hot():
    assert classify_heat(35, None) == "HOT"    # rank 21-50
    assert classify_heat(None, 72.0) == "HOT"  # 65-80% bullish


def test_classify_heat_spiking():
    assert classify_heat(10, 80.0) == "SPIKING"  # rank <=20 AND >75% bullish


def test_classify_heat_hot_not_spiking_without_both():
    # rank <=20 but no Stocktwits data → HOT not SPIKING
    assert classify_heat(5, None) == "HOT"
    # Stocktwits >75% but rank >20 → HOT not SPIKING
    assert classify_heat(30, 80.0) == "HOT"


def test_social_signal_defaults():
    sig = SocialSignal(ticker="TSLA")
    assert sig.heat == "COLD"
    assert sig.ape_rank is None
    assert sig.error is None


def test_get_signals_returns_cold_on_error():
    provider = SocialSentimentProvider(portfolio_id="test")
    with patch("social_sentiment.requests.get", side_effect=Exception("network error")):
        signals = provider.get_signals(["AAPL", "TSLA"])
    assert "AAPL" in signals
    assert signals["AAPL"].heat == "COLD"
    assert signals["AAPL"].error is not None


def test_get_signals_uses_apewisdom_rank():
    provider = SocialSentimentProvider(portfolio_id="test")
    mock_ape = {"TSLA": {"rank": 5, "mentions": 500, "upvotes": 200}}
    with patch.object(provider, "_fetch_apewisdom", return_value=mock_ape), \
         patch.object(provider, "_fetch_stocktwits", return_value=(None, 0)):
        signals = provider.get_signals(["TSLA"])
    assert signals["TSLA"].ape_rank == 5
    assert signals["TSLA"].heat == "HOT"  # rank <=20 but no ST → HOT


def test_cache_is_written_and_read(tmp_path):
    provider = SocialSentimentProvider(portfolio_id="test")
    provider._cache_file = tmp_path / "test_social.json"
    mock_ape = {}
    with patch.object(provider, "_fetch_apewisdom", return_value=mock_ape), \
         patch.object(provider, "_fetch_stocktwits", return_value=(None, 0)):
        provider.get_signals(["NVDA"])
    assert provider._cache_file.exists()
    # Second call should read from cache without fetching
    with patch.object(provider, "_fetch_apewisdom", side_effect=Exception("should not call")):
        signals = provider.get_signals(["NVDA"])
    assert "NVDA" in signals
```

**Step 2: Run to verify failure**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pytest tests/test_social_sentiment.py -v 2>&1 | head -20
```
Expected: ImportError — `social_sentiment` doesn't exist yet.

**Step 3: Implement `scripts/social_sentiment.py`**

```python
#!/usr/bin/env python3
"""
Social Sentiment Provider — ApeWisdom + Stocktwits risk overlay.

Fetches retail sentiment signals to detect pump-and-dump risk.
Never modifies quant scores — metadata only.

Heat levels:
  COLD    — not trending, factor signal likely organic
  WARM    — some retail interest, watch it
  HOT     — high retail attention, scrutinize entry
  SPIKING — pump watch, AI gets hard warning
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
SOCIAL_CACHE_DIR = DATA_DIR / "social_cache"
SOCIAL_CACHE_DIR.mkdir(exist_ok=True)

CACHE_TTL = 7200  # 2 hours

APE_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
ST_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

APE_TIMEOUT = 8
ST_TIMEOUT = 5
ST_DELAY = 0.4  # seconds between Stocktwits calls (~150/hr max)


@dataclass
class SocialSignal:
    ticker: str
    ape_rank: Optional[int] = None
    ape_mentions: int = 0
    ape_upvotes: int = 0
    st_bullish_pct: Optional[float] = None
    st_message_count: int = 0
    heat: str = "COLD"
    fetched_at: float = field(default_factory=time.time)
    error: Optional[str] = None


def classify_heat(ape_rank: Optional[int], st_bullish_pct: Optional[float]) -> str:
    """
    Classify social heat level from ApeWisdom rank and Stocktwits bullish %.

    SPIKING requires BOTH rank <=20 AND st_bullish_pct > 75.
    HOT requires rank 21-50 OR st_bullish_pct 65-80 (or rank <=20 without ST data).
    WARM requires rank 51-100 OR st_bullish_pct 55-65.
    COLD otherwise.
    """
    rank_spiking = ape_rank is not None and ape_rank <= 20
    st_spiking = st_bullish_pct is not None and st_bullish_pct > 75

    if rank_spiking and st_spiking:
        return "SPIKING"

    rank_hot = ape_rank is not None and ape_rank <= 50
    st_hot = st_bullish_pct is not None and st_bullish_pct > 65

    if rank_hot or st_hot:
        return "HOT"

    rank_warm = ape_rank is not None and ape_rank <= 100
    st_warm = st_bullish_pct is not None and st_bullish_pct > 55

    if rank_warm or st_warm:
        return "WARM"

    return "COLD"


class SocialSentimentProvider:
    """Fetches and caches social sentiment signals for a portfolio's watchlist."""

    def __init__(self, portfolio_id: str = None):
        self.portfolio_id = portfolio_id or "default"
        self._cache_file = SOCIAL_CACHE_DIR / f"{self.portfolio_id}_social.json"
        self._cache: dict[str, dict] = self._load_cache()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_signals(self, tickers: list[str]) -> dict[str, SocialSignal]:
        """
        Return SocialSignal for each ticker. Uses cache where fresh.
        Fetches ApeWisdom once then Stocktwits per-ticker for uncached.
        """
        tickers = [t.upper() for t in tickers]
        now = time.time()

        # Check which tickers need fresh data
        stale = [t for t in tickers if not self._is_fresh(t, now)]

        if stale:
            try:
                ape_map = self._fetch_apewisdom()
            except Exception as e:
                ape_map = {}
                print(f"[social] ApeWisdom fetch failed: {e}")

            for ticker in stale:
                try:
                    st_bullish, st_count = self._fetch_stocktwits(ticker)
                    time.sleep(ST_DELAY)
                except Exception as e:
                    st_bullish, st_count = None, 0
                    print(f"[social] Stocktwits fetch failed for {ticker}: {e}")

                ape_data = ape_map.get(ticker, {})
                heat = classify_heat(ape_data.get("rank"), st_bullish)

                self._cache[ticker] = {
                    "ticker": ticker,
                    "ape_rank": ape_data.get("rank"),
                    "ape_mentions": ape_data.get("mentions", 0),
                    "ape_upvotes": ape_data.get("upvotes", 0),
                    "st_bullish_pct": st_bullish,
                    "st_message_count": st_count,
                    "heat": heat,
                    "fetched_at": now,
                    "error": None,
                }

            self._save_cache()

        return {t: self._to_signal(self._cache.get(t, {"ticker": t})) for t in tickers}

    # ── Fetchers ──────────────────────────────────────────────────────────────

    def _fetch_apewisdom(self) -> dict[str, dict]:
        """One call — returns rank map for all top-100 tickers."""
        resp = requests.get(APE_URL, timeout=APE_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return {
            r["ticker"].upper(): {
                "rank": r["rank"],
                "mentions": r.get("mentions", 0),
                "upvotes": r.get("upvotes", 0),
            }
            for r in results
            if r.get("ticker")
        }

    def _fetch_stocktwits(self, ticker: str) -> tuple[Optional[float], int]:
        """Returns (bullish_pct, message_count) from last 30 Stocktwits messages."""
        url = ST_URL.format(ticker=ticker)
        resp = requests.get(url, timeout=ST_TIMEOUT)
        if resp.status_code == 404:
            return None, 0
        resp.raise_for_status()
        messages = resp.json().get("messages", [])
        sentiments = [
            m["entities"]["sentiment"]["basic"]
            for m in messages
            if m.get("entities", {}).get("sentiment")
        ]
        if not sentiments:
            return None, 0
        bullish = sum(1 for s in sentiments if s == "Bullish")
        return round(bullish / len(sentiments) * 100, 1), len(sentiments)

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _is_fresh(self, ticker: str, now: float) -> bool:
        entry = self._cache.get(ticker)
        if not entry:
            return False
        return (now - entry.get("fetched_at", 0)) < CACHE_TTL

    def _load_cache(self) -> dict:
        if self._cache_file.exists():
            try:
                return json.loads(self._cache_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        self._cache_file.write_text(json.dumps(self._cache, indent=2))

    def _to_signal(self, d: dict) -> SocialSignal:
        return SocialSignal(
            ticker=d.get("ticker", ""),
            ape_rank=d.get("ape_rank"),
            ape_mentions=d.get("ape_mentions", 0),
            ape_upvotes=d.get("ape_upvotes", 0),
            st_bullish_pct=d.get("st_bullish_pct"),
            st_message_count=d.get("st_message_count", 0),
            heat=d.get("heat", "COLD"),
            fetched_at=d.get("fetched_at", 0.0),
            error=d.get("error"),
        )
```

**Step 4: Run tests**

```bash
pytest tests/test_social_sentiment.py -v
```
Expected: all 9 tests pass.

**Step 5: Commit**

```bash
git add scripts/social_sentiment.py tests/test_social_sentiment.py
git commit -m "feat: add SocialSentimentProvider with ApeWisdom + Stocktwits"
```

---

## Task 2: Enrich `WatchlistEntry` with social fields

**Files:**
- Modify: `scripts/watchlist_manager.py` (lines ~57-75, ~395-450)
- Modify: `scripts/enhanced_structures.py` (not needed — WatchlistEntry lives in watchlist_manager.py)

**Context:** `WatchlistEntry` is a dataclass at line 57 of `watchlist_manager.py`. `update_watchlist()` is at line 395. We add 3 optional fields and call `SocialSentimentProvider.get_signals()` after the discovery scan completes.

**Step 1: Write failing test**

```python
# tests/test_watchlist_social.py
import pytest
import sys
sys.path.insert(0, "scripts")
from watchlist_manager import WatchlistEntry

def test_watchlist_entry_has_social_fields():
    e = WatchlistEntry(ticker="AAPL")
    assert hasattr(e, "social_heat")
    assert hasattr(e, "social_rank")
    assert hasattr(e, "social_bullish_pct")
    assert e.social_heat == ""
    assert e.social_rank is None
    assert e.social_bullish_pct is None

def test_watchlist_entry_serializes_social_fields():
    import dataclasses
    e = WatchlistEntry(ticker="AAPL", social_heat="HOT", social_rank=35, social_bullish_pct=71.5)
    d = dataclasses.asdict(e)
    assert d["social_heat"] == "HOT"
    assert d["social_rank"] == 35
    assert d["social_bullish_pct"] == 71.5
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_watchlist_social.py -v
```
Expected: FAIL — `WatchlistEntry` has no `social_heat` attribute.

**Step 3: Add fields to `WatchlistEntry` in `scripts/watchlist_manager.py`**

Find the `WatchlistEntry` dataclass (line ~57). Add after `notes: str = ""`:

```python
    # Social sentiment (populated by SocialSentimentProvider after scan)
    social_heat: str = ""            # COLD / WARM / HOT / SPIKING
    social_rank: Optional[int] = None  # ApeWisdom rank (1=most mentioned)
    social_bullish_pct: Optional[float] = None  # Stocktwits bullish %
```

Also add `from typing import Optional` if not already imported at top.

**Step 4: Enrich entries in `update_watchlist()`**

Find `update_watchlist()` at line ~395. After the block that calls `_backfill_missing_sectors()` (near the end, before `return stats`), add:

```python
        # Enrich active entries with social sentiment
        try:
            from social_sentiment import SocialSentimentProvider
            active_entries = [e for e in entries if e.status == "ACTIVE"]
            if active_entries:
                provider = SocialSentimentProvider(portfolio_id=self.portfolio_id)
                tickers = [e.ticker for e in active_entries]
                signals = provider.get_signals(tickers)
                for entry in active_entries:
                    sig = signals.get(entry.ticker)
                    if sig:
                        entry.social_heat = sig.heat
                        entry.social_rank = sig.ape_rank
                        entry.social_bullish_pct = sig.st_bullish_pct
                self._save_watchlist(entries)
        except Exception as e:
            print(f"[watchlist] Social enrichment failed (non-fatal): {e}")
```

**Step 5: Run tests**

```bash
pytest tests/test_watchlist_social.py -v
```
Expected: both tests pass.

**Step 6: Commit**

```bash
git add scripts/watchlist_manager.py tests/test_watchlist_social.py
git commit -m "feat: add social_heat/rank/bullish_pct fields to WatchlistEntry"
```

---

## Task 3: Attach `SocialSignal` to `BuyProposal`

**Files:**
- Modify: `scripts/enhanced_structures.py` (~line 95, `BuyProposal` dataclass)
- Modify: `scripts/opportunity_layer.py` (`_generate_buy_proposals`, line ~392)
- Modify: `scripts/unified_analysis.py` (pass signal map to OpportunityLayer)

**Context:** `BuyProposal` is in `scripts/enhanced_structures.py` at line 95. `OpportunityLayer._generate_buy_proposals()` is at line ~392. `run_unified_analysis()` in `unified_analysis.py` calls the opportunity layer at line ~169.

**Step 1: Write failing test**

```python
# tests/test_buy_proposal_social.py
import sys
sys.path.insert(0, "scripts")
from enhanced_structures import BuyProposal
from social_sentiment import SocialSignal

def test_buy_proposal_has_social_field():
    # BuyProposal needs a social_signal optional field
    from enhanced_structures import ConvictionScore, ConvictionLevel
    cs = ConvictionScore(ticker="AAPL", composite_score=75, final_conviction=75,
                         conviction_level=ConvictionLevel.GOOD,
                         base_multiplier=1.0, conviction_multiplier=1.0,
                         patterns_detected=[], atr_pct=2.0, factors={})
    bp = BuyProposal(ticker="AAPL", shares=100, price=150.0, total_value=15000.0,
                     conviction_score=cs, position_size_pct=5.0, rationale="test")
    assert hasattr(bp, "social_signal")
    assert bp.social_signal is None
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_buy_proposal_social.py -v
```
Expected: FAIL — `BuyProposal` has no `social_signal`.

**Step 3: Add field to `BuyProposal` in `scripts/enhanced_structures.py`**

Find `class BuyProposal` (~line 95). Add after `rationale: str`:

```python
    social_signal: Optional["SocialSignal"] = None  # populated by unified_analysis
```

Add `from typing import Optional` at top of file if not present. Use string annotation `"SocialSignal"` to avoid circular import.

**Step 4: Pass social signals into `_generate_buy_proposals` in `scripts/opportunity_layer.py`**

Find `_generate_buy_proposals` signature (~line 392):
```python
def _generate_buy_proposals(self, conviction_scores, state, price_map=None) -> List[BuyProposal]:
```

Change to:
```python
def _generate_buy_proposals(self, conviction_scores, state, price_map=None, social_signals=None) -> List[BuyProposal]:
```

Find the `proposal = BuyProposal(...)` call (~line 494). After the existing fields, add:
```python
                social_signal=social_signals.get(ticker) if social_signals else None,
```

Do the same for the rotation `BuyProposal` at ~line 670.

Also update `analyze()` to pass `social_signals` through to `_generate_buy_proposals`. Find the call:
```python
buy_proposals = self._generate_buy_proposals(conviction_scores, state, price_map)
```
Change to:
```python
buy_proposals = self._generate_buy_proposals(conviction_scores, state, price_map,
                                              social_signals=social_signals)
```

Add `social_signals=None` param to `analyze()` signature too.

**Step 5: Fetch signals in `scripts/unified_analysis.py`**

In `run_unified_analysis()`, find where OpportunityLayer is called (~line 169). Before calling `layer2.analyze(state)`, add:

```python
    # Fetch social signals for watchlist candidates
    social_signals = {}
    try:
        from social_sentiment import SocialSentimentProvider
        watchlist_tickers = load_watchlist(portfolio_id=portfolio_id)
        if watchlist_tickers:
            provider = SocialSentimentProvider(portfolio_id=portfolio_id)
            social_signals = provider.get_signals(watchlist_tickers)
    except Exception as e:
        print(f"[analysis] Social sentiment fetch failed (non-fatal): {e}")
```

Then pass it to the layer2 call:
```python
    layer2_output = layer2.analyze(state, social_signals=social_signals)
```

Update `OpportunityLayer.analyze()` signature to accept and forward `social_signals`:
```python
def analyze(self, state, social_signals=None):
    ...
    buy_proposals = self._generate_buy_proposals(conviction_scores, state, price_map,
                                                  social_signals=social_signals)
```

**Step 6: Run tests**

```bash
pytest tests/test_buy_proposal_social.py -v
```
Expected: PASS.

**Step 7: Commit**

```bash
git add scripts/enhanced_structures.py scripts/opportunity_layer.py scripts/unified_analysis.py tests/test_buy_proposal_social.py
git commit -m "feat: attach SocialSignal to BuyProposal through analysis pipeline"
```

---

## Task 4: Inject social context into AI review prompt

**Files:**
- Modify: `scripts/ai_review.py` (lines ~90-110, the `actions_text` loop)

**Context:** The AI review prompt is built in `ai_review.py` at ~line 90. Each action gets a text block with ticker, score, factor scores, regime, etc. We add a social heat line to each BUY action's block.

The `proposed_actions` at review time are `ProposedAction` objects (converted from `BuyProposal` in `unified_analysis.py` ~line 173). We need to either pass the social signal through `ProposedAction` or look it up via a passed-in signals dict.

**Step 1: Write failing test**

```python
# tests/test_ai_review_social.py
import sys, json
sys.path.insert(0, "scripts")

def test_spiking_heat_appears_in_prompt():
    """When a buy has SPIKING heat, the AI prompt must contain a pump warning."""
    from ai_review import _build_review_prompt
    from social_sentiment import SocialSignal

    # Build a minimal proposed action dict + social signals dict
    action = {
        "action_type": "BUY",
        "ticker": "MEME",
        "shares": 100,
        "price": 10.0,
        "stop_loss": 9.0,
        "take_profit": 12.0,
        "quant_score": 75.0,
        "factor_scores": {"momentum": 80, "volatility": 60},
        "regime": "SIDEWAYS",
        "reason": "Strong momentum",
    }
    social_signals = {
        "MEME": SocialSignal(ticker="MEME", ape_rank=5, st_bullish_pct=82.0,
                             heat="SPIKING")
    }
    portfolio_context = {"total_equity": 50000, "cash": 40000,
                         "num_positions": 2, "regime": "SIDEWAYS", "win_rate": 0.6}

    prompt = _build_review_prompt([action], portfolio_context,
                                  social_signals=social_signals)
    assert "SPIKING" in prompt
    assert "pump" in prompt.lower() or "retail" in prompt.lower()


def test_cold_heat_shows_cold_note():
    from ai_review import _build_review_prompt
    from social_sentiment import SocialSignal

    action = {
        "action_type": "BUY", "ticker": "QUIET", "shares": 50, "price": 20.0,
        "stop_loss": 18.0, "take_profit": 25.0, "quant_score": 70.0,
        "factor_scores": {}, "regime": "BULL", "reason": "Momentum",
    }
    social_signals = {
        "QUIET": SocialSignal(ticker="QUIET", heat="COLD")
    }
    prompt = _build_review_prompt([action], {"total_equity": 50000, "cash": 40000,
                                              "num_positions": 2, "regime": "BULL",
                                              "win_rate": 0.6},
                                  social_signals=social_signals)
    assert "COLD" in prompt or "independent" in prompt.lower()
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_ai_review_social.py -v
```
Expected: FAIL — `_build_review_prompt` doesn't accept `social_signals` kwarg.

**Step 3: Modify `scripts/ai_review.py`**

Find the function that builds the prompt (contains `actions_text += f"""` at ~line 91). The function is likely named something like `review_proposed_actions` or is inside the review flow. Add `social_signals=None` parameter and inject into the per-action text block.

In the `actions_text` loop, after `  Quant Reason: {action.reason}`, add:

```python
        # Inject social heat
        if social_signals:
            ticker = action.get("ticker") if isinstance(action, dict) else action.ticker
            sig = social_signals.get(ticker)
            if sig:
                heat_lines = {
                    "COLD":    f"  Social Heat: COLD — factor signal appears independent of retail sentiment.",
                    "WARM":    f"  Social Heat: WARM — some retail interest, watch entry timing.",
                    "HOT":     f"  Social Heat: HOT — high retail attention, verify this is not crowded.",
                    "SPIKING": f"  Social Heat: SPIKING (WSB rank #{sig.ape_rank}, {sig.st_bullish_pct:.0f}% bullish on Stocktwits) — elevated pump risk, apply extra scrutiny before approving.",
                }
                actions_text += heat_lines.get(sig.heat, "") + "\n"
```

Also pass `social_signals` through from wherever `_build_review_prompt` (or equivalent) is called in `ai_review.py`.

**Step 4: Run tests**

```bash
pytest tests/test_ai_review_social.py -v
```
Expected: both tests pass.

**Step 5: Commit**

```bash
git add scripts/ai_review.py tests/test_ai_review_social.py
git commit -m "feat: inject social heat warnings into AI review prompt"
```

---

## Task 5: Dashboard — social heat badge on watchlist candidates

**Files:**
- Modify: `dashboard/src/lib/types.ts` (add fields to `WatchlistCandidate`)
- Modify: `dashboard/src/components/FocusPane.tsx` or wherever the pre-flight watchlist is rendered (Actions tab)

**Context:** `WatchlistCandidate` is defined in `dashboard/src/lib/types.ts` at line ~362. The pre-flight dashboard in the Actions tab shows watchlist candidates — find the component that renders them (likely in `ActionsTab.tsx` or similar inside `FocusPane`).

**Step 1: Add fields to `WatchlistCandidate` in `dashboard/src/lib/types.ts`**

Find `interface WatchlistCandidate`. Add:
```typescript
  social_heat?: string        // "COLD" | "WARM" | "HOT" | "SPIKING"
  social_rank?: number | null
  social_bullish_pct?: number | null
```

**Step 2: Add `SocialHeatBadge` component and render in watchlist list**

Find where watchlist candidates are rendered (search for `WatchlistCandidate` usage in components). Add a small badge:

```tsx
const HEAT_STYLE: Record<string, { label: string; color: string; bg: string; pulse?: boolean }> = {
  COLD:    { label: "COLD",    color: "var(--text-0)",  bg: "var(--surface-2)" },
  WARM:    { label: "WARM",    color: "var(--amber)",   bg: "rgba(251,191,36,0.12)" },
  HOT:     { label: "HOT",     color: "#f97316",        bg: "rgba(249,115,22,0.12)" },
  SPIKING: { label: "SPIKING", color: "var(--red)",     bg: "rgba(248,113,113,0.15)", pulse: true },
};

function SocialHeatBadge({ heat }: { heat?: string }) {
  if (!heat || heat === "COLD") return null;
  const style = HEAT_STYLE[heat] ?? HEAT_STYLE.COLD;
  return (
    <span
      className={style.pulse ? "animate-pulse" : ""}
      style={{
        fontSize: "9px",
        fontWeight: 600,
        padding: "1px 5px",
        borderRadius: "3px",
        letterSpacing: "0.06em",
        color: style.color,
        background: style.bg,
      }}
    >
      {style.label}
    </span>
  );
}
```

In the watchlist candidate row, add `<SocialHeatBadge heat={candidate.social_heat} />` next to the ticker name.

**Step 3: Build to verify no TypeScript errors**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -10
```
Expected: `✓ built in Xs` with no errors.

**Step 4: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/components/
git commit -m "feat: social heat badge on watchlist candidates in Actions tab"
```

---

## Task 6: Wire it all together + smoke test

**Files:**
- No new files — integration verification

**Step 1: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pytest tests/ -v 2>&1 | tail -30
```
Expected: all tests pass including new social tests.

**Step 2: Smoke test the full pipeline end-to-end**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from social_sentiment import SocialSentimentProvider, classify_heat

# Test classify_heat
assert classify_heat(5, 82.0) == 'SPIKING'
assert classify_heat(30, None) == 'HOT'
assert classify_heat(None, None) == 'COLD'

# Test provider with real APIs (will actually call ApeWisdom)
provider = SocialSentimentProvider(portfolio_id='microcap')
signals = provider.get_signals(['AAPL', 'NVDA', 'TSLA'])
for ticker, sig in signals.items():
    print(f'{ticker}: heat={sig.heat}, ape_rank={sig.ape_rank}, st_bullish={sig.st_bullish_pct}')
print('OK')
"
```

**Step 3: Update MEMORY.md**

Add to the MicroCapRebuilder section:
```
### Social Sentiment Feature (2026-03-06)
- `scripts/social_sentiment.py` — SocialSentimentProvider, ApeWisdom + Stocktwits, 2hr cache in `data/social_cache/`
- `classify_heat(ape_rank, st_bullish_pct)` → COLD/WARM/HOT/SPIKING
- WatchlistEntry: social_heat, social_rank, social_bullish_pct fields
- BuyProposal: social_signal field (SocialSignal | None)
- AI review prompt includes social heat line per BUY action
- Dashboard: SocialHeatBadge on watchlist candidates (WARM=amber, HOT=orange, SPIKING=red+pulse)
```

**Step 4: Final commit + push**

```bash
git add -A
git commit -m "feat: complete social sentiment risk overlay (ARIA vs Reddit)"
git push origin main
```
