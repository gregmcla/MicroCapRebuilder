#!/usr/bin/env python3
"""
ETF Holdings Provider for Mommy Bot.

Fetches holdings from small-cap ETFs to populate the extended universe tier.
Uses yfinance for data retrieval with fallback to cached holdings.

Usage:
    from etf_holdings_provider import ETFHoldingsProvider

    provider = ETFHoldingsProvider()
    holdings = provider.get_all_holdings()
    print(f"Found {len(holdings)} tickers from ETFs")
"""

import json
import warnings
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"
CACHE_FILE = DATA_DIR / "etf_holdings_cache.json"


# ─── Configuration ────────────────────────────────────────────────────────────
@dataclass
class ETFConfig:
    """Configuration for an ETF."""
    symbol: str
    name: str
    focus: str  # small-cap, mid-cap, etc.
    max_holdings: int = 100


# Default ETF configurations
DEFAULT_ETFS = [
    ETFConfig("IWM", "iShares Russell 2000 ETF", "small-cap", 150),
    ETFConfig("IJR", "iShares Core S&P Small-Cap ETF", "small-cap", 100),
    ETFConfig("VB", "Vanguard Small-Cap ETF", "small-cap", 100),
    ETFConfig("SCHA", "Schwab U.S. Small-Cap ETF", "small-cap", 75),
    ETFConfig("VBR", "Vanguard Small-Cap Value ETF", "small-cap-value", 75),
]


def load_config(portfolio_id: str = None) -> dict:
    """Load configuration, optionally portfolio-scoped."""
    if portfolio_id:
        from data_files import load_config as load_config_from_files
        return load_config_from_files(portfolio_id)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


class ETFHoldingsProvider:
    """
    Fetches and manages ETF holdings for the universe.

    Uses yfinance to fetch ETF holdings with fallback to cached data.
    Includes filtering by market cap, volume, and price.
    """

    def __init__(self, etf_symbols: List[str] = None, portfolio_id: str = None):
        """
        Initialize the provider.

        Args:
            etf_symbols: List of ETF symbols to fetch. Defaults to config-based ETFs.
            portfolio_id: Optional portfolio ID for portfolio-scoped config.
        """
        self.portfolio_id = portfolio_id
        self.config = load_config(portfolio_id)
        self.universe_config = self.config.get("universe", {})
        self.filters = self.universe_config.get("filters", {})

        # Get ETF list from config or use defaults
        if etf_symbols is None:
            etf_config = self.universe_config.get("sources", {}).get("etf_holdings", {})
            etf_symbols = etf_config.get("etfs", ["IWM", "IJR", "VB"])

        self.etf_configs = {
            cfg.symbol: cfg for cfg in DEFAULT_ETFS
            if cfg.symbol in etf_symbols
        }

        # Add any custom ETFs not in defaults
        for sym in etf_symbols:
            if sym not in self.etf_configs:
                self.etf_configs[sym] = ETFConfig(sym, f"{sym} ETF", "unknown", 100)

        # Portfolio-scoped cache file
        if portfolio_id:
            from data_files import _resolve_data_dir
            self._cache_file = _resolve_data_dir(portfolio_id) / "etf_holdings_cache.json"
        else:
            self._cache_file = CACHE_FILE

        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cached holdings."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"holdings": {}, "last_updated": {}}

    def _save_cache(self):
        """Save holdings to cache."""
        try:
            with open(self._cache_file, "w") as f:
                json.dump(self._cache, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save cache: {e}")

    def _is_cache_fresh(self, etf: str, max_age_days: int = 7) -> bool:
        """Check if cached data is fresh enough."""
        last_updated = self._cache.get("last_updated", {}).get(etf)
        if not last_updated:
            return False

        try:
            updated_dt = datetime.fromisoformat(last_updated)
            return datetime.now() - updated_dt < timedelta(days=max_age_days)
        except (ValueError, TypeError):
            return False

    def fetch_holdings(self, etf_symbol: str, use_cache: bool = True) -> List[str]:
        """
        Fetch holdings for a single ETF.

        Args:
            etf_symbol: ETF ticker symbol (e.g., "IWM")
            use_cache: Whether to use cached data if available

        Returns:
            List of ticker symbols from ETF holdings
        """
        # Check cache first
        if use_cache and self._is_cache_fresh(etf_symbol):
            cached = self._cache.get("holdings", {}).get(etf_symbol, [])
            if cached:
                return cached

        holdings = []

        try:
            ticker = yf.Ticker(etf_symbol)

            # Try to get holdings from yfinance
            # Note: yfinance may not provide holdings for all ETFs
            if hasattr(ticker, 'funds_data'):
                try:
                    funds_data = ticker.funds_data
                    if funds_data and hasattr(funds_data, 'top_holdings'):
                        top_holdings = funds_data.top_holdings
                        if top_holdings is not None and not top_holdings.empty:
                            holdings = top_holdings.index.tolist()
                except Exception:
                    pass

            # Fallback: try the older API
            if not holdings:
                try:
                    info = ticker.info
                    if 'holdings' in info:
                        holdings = [h.get('symbol', '') for h in info['holdings'] if h.get('symbol')]
                except Exception:
                    pass

            # If we got holdings, cache them
            if holdings:
                max_holdings = self.etf_configs.get(etf_symbol, ETFConfig(etf_symbol, "", "", 100)).max_holdings
                holdings = holdings[:max_holdings]

                self._cache.setdefault("holdings", {})[etf_symbol] = holdings
                self._cache.setdefault("last_updated", {})[etf_symbol] = datetime.now().isoformat()
                self._save_cache()

                print(f"  Fetched {len(holdings)} holdings from {etf_symbol}")
            else:
                # Use cached data as fallback
                holdings = self._cache.get("holdings", {}).get(etf_symbol, [])
                if holdings:
                    print(f"  Using {len(holdings)} cached holdings for {etf_symbol}")
                else:
                    print(f"  No holdings available for {etf_symbol}")

        except Exception as e:
            print(f"  Error fetching {etf_symbol}: {e}")
            # Use cached data as fallback
            holdings = self._cache.get("holdings", {}).get(etf_symbol, [])
            if holdings:
                print(f"  Falling back to {len(holdings)} cached holdings")

        return holdings

    def get_all_holdings(self, use_cache: bool = True) -> Set[str]:
        """
        Get holdings from all configured ETFs.

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            Set of unique ticker symbols from all ETFs
        """
        all_holdings = set()

        print("Fetching ETF holdings...")
        for etf_symbol in self.etf_configs:
            holdings = self.fetch_holdings(etf_symbol, use_cache)
            all_holdings.update(holdings)

        print(f"Total unique tickers from ETFs: {len(all_holdings)}")
        return all_holdings

    def get_filtered_holdings(self, use_cache: bool = True) -> List[str]:
        """
        Get ETF holdings that pass the configured filters.

        Filters applied:
        - Market cap range
        - Minimum average volume
        - Price range

        Args:
            use_cache: Whether to use cached data

        Returns:
            List of tickers that pass all filters
        """
        all_holdings = list(self.get_all_holdings(use_cache))

        if not all_holdings:
            return []

        # Get filter config
        min_cap = self.filters.get("min_market_cap_m", 300) * 1_000_000
        max_cap = self.filters.get("max_market_cap_m", 50000) * 1_000_000
        min_volume = self.filters.get("min_avg_volume", 200000)
        min_price = self.filters.get("min_price", 5.0)
        max_price = self.filters.get("max_price", 1000.0)

        # Filter holdings
        filtered = []
        batch_size = 20

        print(f"Filtering {len(all_holdings)} tickers...")

        for i in range(0, len(all_holdings), batch_size):
            batch = all_holdings[i:i + batch_size]

            try:
                # Fetch info for batch
                for ticker_symbol in batch:
                    try:
                        ticker = yf.Ticker(ticker_symbol)
                        info = ticker.info

                        market_cap = info.get("marketCap", 0) or 0
                        avg_volume = info.get("averageVolume", 0) or 0
                        price = info.get("regularMarketPrice") or info.get("previousClose") or 0

                        # Apply filters
                        if (min_cap <= market_cap <= max_cap and
                            avg_volume >= min_volume and
                            min_price <= price <= max_price):
                            filtered.append(ticker_symbol)

                    except Exception:
                        # Skip tickers that fail
                        continue

            except Exception as e:
                print(f"  Batch error: {e}")
                continue

        print(f"Filtered to {len(filtered)} tickers passing all criteria")
        return filtered

    def get_sector_breakdown(self, holdings: List[str] = None) -> Dict[str, List[str]]:
        """
        Get holdings organized by sector.

        Args:
            holdings: List of tickers to categorize. If None, uses all ETF holdings.

        Returns:
            Dict mapping sector names to lists of tickers
        """
        if holdings is None:
            holdings = list(self.get_all_holdings())

        sectors: Dict[str, List[str]] = {}

        for ticker_symbol in holdings[:50]:  # Limit to avoid rate limits
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info
                sector = info.get("sector", "Unknown")

                sectors.setdefault(sector, []).append(ticker_symbol)

            except Exception:
                sectors.setdefault("Unknown", []).append(ticker_symbol)

        return sectors


# ─── Static Fallback Holdings ─────────────────────────────────────────────────
# These are used when yfinance can't fetch live holdings

FALLBACK_HOLDINGS = {
    # --- Small-cap / Micro-cap ETFs ---
    "IWM": [
        "SMCI", "MSTR", "CORT", "INSM", "FTAI", "CRDO", "SPR", "LNTH", "GKOS", "NBIX",
        "ANF", "JANX", "FN", "BOOT", "MARA", "CIVI", "EXAS", "EME", "CVLT", "STEP",
        "RIOT", "SIGI", "PIPR", "PRIM", "SFM", "VNT", "WULF", "RUN", "ABG", "MOD",
        "TMDX", "RDNT", "CNX", "ITCI", "ONTO", "SHAK", "ACLX", "VERA", "OSCR", "VIRT"
    ],
    "IJR": [
        "OMCL", "MMSI", "HAYW", "FWRD", "CADE", "RLJ", "PECO", "MGRC", "TILE", "LXP",
        "SIG", "VCEL", "CARG", "IIPR", "RHP", "KLIC", "IPAR", "APAM", "EXPO", "CALM",
        "MGEE", "NXRT", "IOSP", "IIVI", "CHEF", "GBX", "CXW", "WK", "CENX", "NHC",
        "AWR", "PRDO", "AEIS", "TRNO", "MTH", "ALKS", "CATY", "HURN", "GVA", "DFIN"
    ],
    "VB": [
        "SMCI", "MSTR", "FTAI", "CORT", "INSM", "CRDO", "SPR", "LNTH", "GKOS", "NBIX",
        "ANF", "BOOT", "JANX", "FN", "EME", "MARA", "CIVI", "STEP", "EXAS", "CVLT",
        "RIOT", "SIGI", "SFM", "PIPR", "PRIM", "VNT", "ABG", "WULF", "MOD", "RUN",
        "RDNT", "CNX", "TMDX", "ONTO", "SHAK", "ITCI", "ACLX", "VIRT", "VERA", "OSCR"
    ],
    # --- Large-cap ETFs (S&P 500 components) ---
    "SPY": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "AVGO", "LLY", "JPM",
        "TSLA", "UNH", "V", "XOM", "MA", "COST", "PG", "JNJ", "HD", "ABBV",
        "WMT", "NFLX", "BAC", "CRM", "CVX", "MRK", "KO", "ORCL", "AMD", "PEP",
        "ACN", "TMO", "LIN", "MCD", "CSCO", "ADBE", "ABT", "WFC", "DHR", "GE",
        "PM", "ISRG", "TXN", "QCOM", "INTU", "CAT", "BKNG", "AMGN", "AMAT", "PFE",
        "CMCSA", "GS", "NOW", "VZ", "RTX", "NEE", "T", "LOW", "SYK", "BLK",
        "HON", "SPGI", "UNP", "ELV", "DE", "BA", "PLD", "MDLZ", "LMT", "CB",
        "ADP", "SCHW", "GILD", "MMC", "VRTX", "BMY", "CI", "SO", "DUK", "AMT",
    ],
    "IVV": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "AVGO", "LLY", "JPM",
        "TSLA", "UNH", "V", "XOM", "MA", "COST", "PG", "JNJ", "HD", "ABBV",
        "WMT", "NFLX", "BAC", "CRM", "CVX", "MRK", "KO", "ORCL", "AMD", "PEP",
        "ACN", "TMO", "LIN", "MCD", "CSCO", "ADBE", "ABT", "WFC", "DHR", "GE",
    ],
    "VOO": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "AVGO", "LLY", "JPM",
        "TSLA", "UNH", "V", "XOM", "MA", "COST", "PG", "JNJ", "HD", "ABBV",
        "WMT", "NFLX", "BAC", "CRM", "CVX", "MRK", "KO", "ORCL", "AMD", "PEP",
        "ACN", "TMO", "LIN", "MCD", "CSCO", "ADBE", "ABT", "WFC", "DHR", "GE",
    ],
    # --- Mid-cap ETFs ---
    "IJH": [
        "SMCI", "WSM", "TRGP", "EQT", "IBKR", "RCL", "BURL", "DECK", "NCLH", "TOL",
        "CZR", "RPM", "CLH", "JBL", "POOL", "EXEL", "MANH", "FNF", "NTNX", "HLI",
        "WSO", "ATI", "UFPI", "OC", "GPK", "DTM", "LECO", "CHE", "MTZ", "FHN",
        "RBC", "SAIA", "PCVX", "LPX", "SNX", "FMC", "MIDD", "THC", "PNW", "WH",
    ],
    "VO": [
        "CRH", "WEC", "FAST", "VRSK", "CTVA", "EFX", "XYL", "ANSS", "DOV", "AWK",
        "GPN", "BR", "WRB", "ZBRA", "TDY", "FTV", "STT", "WAT", "NTRS", "BAX",
        "DGX", "LH", "TRMB", "STE", "ALGN", "HOLX", "PKG", "WMS", "JBHT", "EXPD",
        "PTC", "MKTX", "FFIV", "WAB", "IEX", "DPZ", "CHRW", "TER", "AKAM", "TECH",
    ],
    "MDY": [
        "SMCI", "WSM", "TRGP", "EQT", "IBKR", "RCL", "BURL", "DECK", "NCLH", "TOL",
        "CZR", "RPM", "CLH", "JBL", "POOL", "EXEL", "MANH", "FNF", "NTNX", "HLI",
        "WSO", "ATI", "UFPI", "OC", "GPK", "DTM", "LECO", "CHE", "MTZ", "FHN",
    ],
}


def seed_cache_with_fallbacks(portfolio_id: str = None):
    """Seed the cache with fallback holdings if empty.

    Args:
        portfolio_id: Optional portfolio ID for portfolio-scoped cache.
    """
    provider = ETFHoldingsProvider(portfolio_id=portfolio_id)

    # Only seed ETFs that this provider is configured to use
    configured_etfs = set(provider.etf_configs.keys())

    seeded = 0
    for etf, holdings in FALLBACK_HOLDINGS.items():
        if etf in configured_etfs and not provider._is_cache_fresh(etf):
            provider._cache.setdefault("holdings", {})[etf] = holdings
            provider._cache.setdefault("last_updated", {})[etf] = datetime.now().isoformat()
            seeded += 1

    if seeded > 0:
        provider._save_cache()
        print(f"Seeded cache with fallback holdings for {seeded} ETFs ({', '.join(configured_etfs)})")


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ETF HOLDINGS PROVIDER")
    print("=" * 60)

    # Seed cache with fallbacks first
    seed_cache_with_fallbacks()

    provider = ETFHoldingsProvider()

    # Get all holdings
    all_holdings = provider.get_all_holdings(use_cache=True)
    print(f"\nTotal unique tickers: {len(all_holdings)}")

    # Show sample
    print("\nSample tickers:")
    for ticker in sorted(list(all_holdings))[:20]:
        print(f"  {ticker}")
