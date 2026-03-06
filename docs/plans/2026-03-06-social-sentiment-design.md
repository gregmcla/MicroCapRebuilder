# Social Sentiment (ARIA vs. Reddit) Design

**Goal:** Add a social heat risk overlay to ARIA's ANALYZE pipeline — detect when retail sentiment on WSB/Stocktwits overlaps with factor-scored candidates, and use that signal to warn the AI review layer about potential pump-and-dump risk.

**Architecture:** Standalone `SocialSentimentProvider` module. Social heat is metadata, never inflates quant scores. Two free APIs, 2hr disk cache, graceful degradation.

---

## Data Sources

| Source | API | Auth | Rate Limit | What we get |
|--------|-----|------|------------|-------------|
| ApeWisdom | `https://apewisdom.io/api/v1.0/filter/all-stocks/page/1` | None | Unknown, generous | Top 100 trending tickers across WSB/pennystocks/stocks — rank, 24h mentions, upvotes |
| Stocktwits | `https://api.stocktwits.com/api/2/streams/symbol/{TICKER}.json` | None | 200 req/hr | Last 30 messages with user-tagged bullish/bearish sentiment |

One ApeWisdom call per session covers the full top-100 list. Stocktwits called only for tickers that passed scoring thresholds — typically 10-30 per ANALYZE run.

---

## Signal Classification

```
heat = COLD     not in ApeWisdom top 100, Stocktwits bullish < 55%
              → factor signal independent of retail — good sign

heat = WARM     ApeWisdom rank 51-100, OR Stocktwits 55-65% bullish
              → some retail interest, watch it

heat = HOT      ApeWisdom rank 21-50, OR Stocktwits 65-80% bullish
              → high retail attention — scrutinize entry timing

heat = SPIKING  ApeWisdom rank ≤ 20 AND Stocktwits > 75% bullish
              → pump watch — AI gets a hard warning in review prompt
```

Social heat never boosts the composite score. It is risk metadata only.

---

## New File: `scripts/social_sentiment.py`

```python
@dataclass
class SocialSignal:
    ticker: str
    ape_rank: int | None        # position in ApeWisdom top 100, None if not trending
    ape_mentions: int           # 24h mention count
    ape_upvotes: int            # 24h upvote count
    st_bullish_pct: float | None  # 0-100, from Stocktwits last 30 msgs
    st_message_count: int       # how many messages had sentiment tags
    heat: str                   # COLD / WARM / HOT / SPIKING
    fetched_at: str             # ISO timestamp
    error: str | None           # set if API failed, heat defaults to COLD

class SocialSentimentProvider:
    CACHE_TTL = 7200  # 2 hours
    CACHE_FILE = data/social_cache/{portfolio_id}_social.json

    def get_signals(tickers: list[str]) -> dict[str, SocialSignal]
    def _fetch_apewisdom() -> dict[str, dict]   # one call, returns rank map
    def _fetch_stocktwits(ticker) -> tuple[float | None, int]
    def _classify_heat(ape_rank, st_bullish_pct) -> str
    def _load_cache() / _save_cache()
```

Graceful degradation: any network error → `heat=COLD`, `error="<reason>"`. Never blocks a trade.

---

## Modified Files

### `watchlist_manager.py`
Add 3 optional fields to `WatchlistEntry`:
```python
social_heat: str = ""           # COLD / WARM / HOT / SPIKING
social_rank: int | None = None  # ApeWisdom rank
social_bullish_pct: float | None = None
```
`update_watchlist()` calls `SocialSentimentProvider.get_signals()` on active entries after discovery scan completes. Results persisted to watchlist.jsonl.

### `opportunity_layer.py`
`BuyProposal` gets a `social_signal: SocialSignal | None` field. `_generate_buy_proposals()` attaches the signal from a pre-fetched signal map passed in from `unified_analysis.py`.

### `ai_review.py`
Social signal injected into per-ticker review prompt context:
- COLD: *"Social heat: COLD — factor signal appears independent of retail sentiment."*
- WARM: *"Social heat: WARM — some retail interest present."*
- HOT: *"Social heat: HOT — high retail attention, verify entry timing."*
- SPIKING: *"Social heat: SPIKING (WSB rank #N, X% bullish on Stocktwits) — elevated pump risk, apply extra scrutiny."*

### `unified_analysis.py`
Fetch social signals once before the opportunity layer runs, pass the signal map through to proposals and AI review.

### `api/routes/discovery.py`
`GET /api/{portfolio_id}/watchlist` already returns watchlist entries — new fields appear automatically.

### `dashboard/src/lib/types.ts`
Add to `WatchlistCandidate`:
```typescript
social_heat?: string
social_rank?: number | null
social_bullish_pct?: number | null
```

### `dashboard` (Actions tab pre-flight panel)
Small colored badge next to each watchlist candidate:
- COLD → gray
- WARM → amber
- HOT → orange
- SPIKING → red + pulse animation

---

## Data Flow

```
SCAN completes
  → WatchlistManager.update_watchlist()
      → SocialSentimentProvider.get_signals(active_tickers)
          → ApeWisdom (1 call)
          → Stocktwits (N calls, paced)
      → WatchlistEntry.social_heat updated
      → watchlist.jsonl saved

ANALYZE triggered
  → unified_analysis.py fetches social signals for scored candidates
  → OpportunityLayer attaches SocialSignal to each BuyProposal
  → AIReview includes heat level in per-ticker review prompt
  → ReviewedAction returned with social context visible in rationale
```

---

## Error Handling

- ApeWisdom down → skip ApeWisdom ranking, use Stocktwits only
- Stocktwits rate limited → use ApeWisdom rank only, log warning
- Both down → all tickers get `heat=COLD`, scan/analyze proceeds normally
- Stale cache (> 2hr) → re-fetch; if fetch fails, use stale data with warning

---

## What This Does NOT Do

- Does not scrape Reddit directly (no PRAW, no credentials needed)
- Does not boost quant scores based on social momentum
- Does not add a new dashboard tab or page
- Does not block or veto trades automatically — AI review layer decides
