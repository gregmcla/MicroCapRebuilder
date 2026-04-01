#!/usr/bin/env python3
"""
Shared Universe Cache for GScott.

Centralizes discovery scan results across all portfolios. When any portfolio runs
discovery, its results are written here. Other portfolios can read from this cache
and apply their own buy filters instead of re-scanning the same tickers.

Usage:
    from shared_universe import SharedUniverse, SharedScanResult
    cache = SharedUniverse()
    cache.write_results("microcap", scan_results)
    all_results = cache.read_results(max_age_hours=24)
    convergent = cache.get_convergent_tickers(min_portfolios=2)
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List


SCRIPT_DIR = Path(__file__).parent
DEFAULT_CACHE_DIR = SCRIPT_DIR.parent / "data" / "shared_scan_cache"


@dataclass
class SharedScanResult:
    """A single scan result in the shared cache."""
    ticker: str
    composite_score: float
    scan_type: str
    sector: str
    scanned_by: str      # portfolio_id that found it
    scanned_at: str      # ISO timestamp
    factor_scores: dict  # factor breakdown from scorer


class SharedUniverse:
    """Manages the shared scan result cache across portfolios."""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, portfolio_id: str) -> Path:
        return self.cache_dir / f"{portfolio_id}.json"

    def write_results(self, portfolio_id: str, results: List[SharedScanResult]):
        """Write scan results for a portfolio, merging with existing entries.

        Merge key is ticker + scan_type. Newer results overwrite older ones.
        """
        existing = self._load_portfolio_results(portfolio_id)

        result_map = {}
        for r in existing:
            result_map[f"{r.ticker}:{r.scan_type}"] = r
        for r in results:
            result_map[f"{r.ticker}:{r.scan_type}"] = r

        self._save_portfolio_results(portfolio_id, list(result_map.values()))

    def read_results(self, max_age_hours: int = 24) -> List[SharedScanResult]:
        """Read all scan results from all portfolios, filtering by age."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        all_results = []

        for cache_file in self.cache_dir.glob("*.json"):
            for r in self._load_portfolio_results(cache_file.stem):
                try:
                    if datetime.fromisoformat(r.scanned_at) >= cutoff:
                        all_results.append(r)
                except (ValueError, TypeError):
                    pass  # skip malformed timestamps

        return all_results

    def get_convergent_tickers(self, min_portfolios: int = 2, max_age_hours: int = 24) -> Dict:
        """Find tickers discovered independently by multiple portfolios.

        Returns dict: ticker -> {portfolio_count, portfolios, best_score, scan_types}
        """
        by_ticker: Dict[str, dict] = {}
        for r in self.read_results(max_age_hours=max_age_hours):
            if r.ticker not in by_ticker:
                by_ticker[r.ticker] = {"portfolios": set(), "scan_types": set(), "best_score": 0.0}
            entry = by_ticker[r.ticker]
            entry["portfolios"].add(r.scanned_by)
            entry["scan_types"].add(r.scan_type)
            entry["best_score"] = max(entry["best_score"], r.composite_score)

        return {
            ticker: {
                "portfolio_count": len(data["portfolios"]),
                "portfolios": list(data["portfolios"]),
                "scan_types": list(data["scan_types"]),
                "best_score": data["best_score"],
            }
            for ticker, data in by_ticker.items()
            if len(data["portfolios"]) >= min_portfolios
        }

    def get_best_score(self, ticker: str, max_age_hours: int = 24) -> float:
        """Get the highest composite score for a ticker across all portfolios."""
        scores = [r.composite_score for r in self.read_results(max_age_hours=max_age_hours) if r.ticker == ticker]
        return max(scores) if scores else 0.0

    def cleanup(self, max_age_hours: int = 48):
        """Remove entries older than max_age_hours from all portfolio cache files."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        for cache_file in self.cache_dir.glob("*.json"):
            results = self._load_portfolio_results(cache_file.stem)
            fresh = []
            for r in results:
                try:
                    if datetime.fromisoformat(r.scanned_at) >= cutoff:
                        fresh.append(r)
                except (ValueError, TypeError):
                    pass
            if len(fresh) < len(results):
                self._save_portfolio_results(cache_file.stem, fresh)

    def _load_portfolio_results(self, portfolio_id: str) -> List[SharedScanResult]:
        cache_file = self._cache_file(portfolio_id)
        if not cache_file.exists():
            return []
        try:
            return [SharedScanResult(**entry) for entry in json.loads(cache_file.read_text())]
        except Exception as e:
            print(f"  Shared cache load error for {portfolio_id}: {e}")
            return []

    def _save_portfolio_results(self, portfolio_id: str, results: List[SharedScanResult]):
        self._cache_file(portfolio_id).write_text(json.dumps([asdict(r) for r in results], indent=2))
