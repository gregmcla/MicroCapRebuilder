"""
Cache invalidation endpoints.

Provides a manual escape hatch for the per-portfolio caches in case automatic
hash-keyed invalidation isn't enough — e.g. you want to force a fresh fetch
right now, or you've manually edited a config file outside the dashboard.

The portfolio-scoped endpoint covers screener_cache.* and refinement_cache.*
files (both per-portfolio, both hash-keyed). It deliberately does NOT touch
the global yfinance bars cache — that's shared across portfolios so a rogue
"invalidate" on one portfolio shouldn't bust prices for all the others.
Global bars invalidation can be added later as a separate admin endpoint
once we know we want it.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from api.deps import validate_portfolio_id

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PORTFOLIOS_DIR = DATA_DIR / "portfolios"

router = APIRouter(prefix="/api/{portfolio_id}")


_CACHE_PREFIX_BY_SCOPE = {
    "screener": ["screener_cache"],
    "refinement": ["refinement_cache"],
    "all": ["screener_cache", "refinement_cache"],
}


@router.post("/cache/invalidate")
def invalidate_cache(
    portfolio_id: str = Depends(validate_portfolio_id),
    scope: str = Query(
        "all",
        description="Cache scope: 'screener', 'refinement', or 'all' (default).",
    ),
):
    """
    Delete this portfolio's screener/refinement cache files.

    Returns the list of filenames removed. Idempotent — calling it twice with
    the same scope yields an empty list the second time.
    """
    if scope not in _CACHE_PREFIX_BY_SCOPE:
        return {
            "deleted": [],
            "error": f"unknown scope '{scope}' — valid: {sorted(_CACHE_PREFIX_BY_SCOPE)}",
        }

    portfolio_dir = PORTFOLIOS_DIR / portfolio_id
    if not portfolio_dir.exists():
        return {"deleted": [], "error": f"portfolio dir not found: {portfolio_id}"}

    deleted: list[str] = []
    for prefix in _CACHE_PREFIX_BY_SCOPE[scope]:
        # Hash-keyed files use the pattern "<prefix>.<hash>.json".
        # Legacy non-hashed files use the pattern "<prefix>.json". Cover both.
        for pattern in (f"{prefix}.*.json", f"{prefix}.json"):
            for f in portfolio_dir.glob(pattern):
                try:
                    f.unlink()
                    deleted.append(f.name)
                except OSError:
                    pass

    return {"portfolio_id": portfolio_id, "scope": scope, "deleted": deleted}
