#!/usr/bin/env python3
"""
ETF Holdings Provider for GScott.

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


# Default ETF configurations — ALL market caps so every portfolio has the full universe.
# The discovery scanner's market cap / sector filters handle portfolio-specific selection.
DEFAULT_ETFS = [
    # Small-cap / Micro-cap
    ETFConfig("IWM", "iShares Russell 2000 ETF", "small-cap", 40),
    ETFConfig("IJR", "iShares Core S&P Small-Cap ETF", "small-cap", 40),
    ETFConfig("VB", "Vanguard Small-Cap ETF", "small-cap", 40),
    # Mid-cap
    ETFConfig("IJH", "iShares Core S&P Mid-Cap ETF", "mid-cap", 40),
    ETFConfig("VO", "Vanguard Mid-Cap ETF", "mid-cap", 40),
    ETFConfig("MDY", "SPDR S&P MidCap 400 ETF", "mid-cap", 30),
    # Large-cap
    ETFConfig("SPY", "SPDR S&P 500 ETF", "large-cap", 80),
    ETFConfig("QQQ", "Invesco QQQ Trust", "large-cap-growth", 80),
    ETFConfig("VTV", "Vanguard Value ETF", "large-cap-value", 80),
    ETFConfig("VUG", "Vanguard Growth ETF", "large-cap-growth", 80),
    ETFConfig("DIA", "SPDR Dow Jones Industrial Average ETF", "large-cap", 30),
    # Sectors
    ETFConfig("XLK", "Technology Select Sector SPDR", "sector-tech", 30),
    ETFConfig("XLV", "Health Care Select Sector SPDR", "sector-health", 30),
    ETFConfig("XLF", "Financial Select Sector SPDR", "sector-finance", 30),
    ETFConfig("XLI", "Industrial Select Sector SPDR", "sector-industrial", 30),
    ETFConfig("XLY", "Consumer Discretionary Select Sector SPDR", "sector-consumer-disc", 25),
    ETFConfig("XLP", "Consumer Staples Select Sector SPDR", "sector-consumer-staples", 25),
    ETFConfig("XLE", "Energy Select Sector SPDR", "sector-energy", 20),
    ETFConfig("XLB", "Materials Select Sector SPDR", "sector-materials", 20),
    ETFConfig("XLU", "Utilities Select Sector SPDR", "sector-utilities", 20),
    ETFConfig("XLRE", "Real Estate Select Sector SPDR", "sector-realestate", 20),
    ETFConfig("XBI", "SPDR S&P Biotech ETF", "sector-biotech", 20),
    ETFConfig("XOP", "SPDR Oil & Gas Exploration ETF", "sector-energy", 20),
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

        # Get ETF list from config or use all defaults
        if etf_symbols is None:
            etf_config = self.universe_config.get("sources", {}).get("etf_holdings", {})
            configured_etfs = etf_config.get("etfs", None)
            if configured_etfs:
                etf_symbols = configured_etfs
            else:
                # No override — use ALL DEFAULT_ETFS for maximum universe coverage
                etf_symbols = [cfg.symbol for cfg in DEFAULT_ETFS]

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
        "ANF", "JANX", "FN", "BOOT", "MARA", "EXAS", "EME", "CVLT", "STEP",
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
        "ANF", "BOOT", "JANX", "FN", "EME", "MARA", "STEP", "EXAS", "CVLT",
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
    # --- Large-cap Growth/Value/Nasdaq ETFs ---
    "QQQ": [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "AVGO", "TSLA", "GOOGL", "COST", "NFLX",
        "AMD", "ADBE", "PEP", "CSCO", "LIN", "QCOM", "INTU", "ISRG", "TXN", "AMAT",
        "BKNG", "AMGN", "CMCSA", "HON", "PANW", "LRCX", "MU", "ADP", "GILD", "MELI",
        "ADI", "KLAC", "SBUX", "MDLZ", "SNPS", "CDNS", "PYPL", "REGN", "CRWD", "MAR",
        "CTAS", "CEG", "MRVL", "ABNB", "ORLY", "FTNT", "WDAY", "DASH", "CSX", "PCAR",
        "ROP", "TTD", "TEAM", "NXPI", "MNST", "DXCM", "FANG", "FAST", "ODFL", "EXC",
        "KDP", "CTSH", "VRSK", "BKR", "KHC", "GEHC", "ON", "ANSS", "CDW", "DDOG",
        "BIIB", "GFS", "TTWO", "ILMN", "ZS", "XEL", "IDXX", "WBD", "DLTR", "EA",
    ],
    "DIA": [
        "UNH", "GS", "MSFT", "HD", "CAT", "SHW", "V", "AMGN", "CRM", "MCD",
        "AXP", "TRV", "AAPL", "JPM", "AMZN", "BA", "HON", "IBM", "JNJ", "PG",
        "CVX", "MRK", "DIS", "NKE", "KO", "WMT", "CSCO", "INTC", "DOW", "MMM",
    ],
    "VTV": [
        "BRK-B", "JPM", "XOM", "UNH", "JNJ", "PG", "ABBV", "HD", "CVX", "MRK",
        "BAC", "KO", "PEP", "WFC", "CSCO", "ABT", "PM", "GE", "RTX", "LOW",
        "HON", "SPGI", "UNP", "DE", "BA", "LMT", "CB", "MMC", "CI", "SO",
        "DUK", "BMY", "PFE", "ICE", "BDX", "CL", "CME", "USB", "PNC", "TGT",
        "EMR", "AON", "WM", "NSC", "SLB", "SPG", "EQIX", "APD", "MET", "AIG",
        "F", "GM", "COP", "EOG", "PSX", "VLO", "MPC", "HES", "OXY", "DVN",
        "PRU", "TFC", "ALL", "AJG", "D", "SRE", "ED", "WEC", "PPL", "FE",
        "ETR", "AEP", "XEL", "CMS", "ES", "EVRG", "PEG", "AWK", "ATO", "NI",
    ],
    "VUG": [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AVGO", "LLY", "TSLA", "V",
        "MA", "COST", "NFLX", "CRM", "ORCL", "AMD", "ACN", "TMO", "LIN", "ADBE",
        "NOW", "ISRG", "TXN", "QCOM", "INTU", "BKNG", "AMAT", "PLD", "VRTX", "PANW",
        "LRCX", "MU", "SNPS", "CDNS", "KLAC", "CRWD", "ADP", "GILD", "ADI", "MELI",
        "ROP", "CTAS", "CEG", "ABNB", "ORLY", "FTNT", "WDAY", "MRVL", "DASH", "MNST",
        "MCO", "NXPI", "MSCI", "TTD", "DXCM", "IT", "CPRT", "FANG", "ODFL", "ANSS",
        "CDW", "EW", "TEAM", "GWW", "MPWR", "ON", "FAST", "VRSK", "DDOG", "ZS",
        "HLT", "MAR", "CMG", "UBER", "SPOT", "SQ", "SHOP", "SNOW", "NET", "COIN",
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
    # --- Sector ETFs ---
    "XLK": [
        "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "CSCO", "ACN",
        "IBM", "INTU", "TXN", "QCOM", "AMAT", "NOW", "PANW", "ADI", "LRCX", "KLAC",
        "SNPS", "CDNS", "CRWD", "FTNT", "MCHP", "MU", "MSI", "APH", "NXPI", "TEL",
    ],
    "SOXX": [
        "NVDA", "AVGO", "AMD", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "ADI", "MCHP",
        "MU", "NXPI", "MRVL", "ON", "MPWR", "INTC", "GFS", "SWKS", "QRVO", "ENTG",
    ],
    "XLC": [
        "META", "GOOG", "GOOGL", "NFLX", "TMUS", "CMCSA", "DIS", "T", "VZ", "CHTR",
        "EA", "TTWO", "OMC", "IPG", "LYV", "WBD", "MTCH", "PARA", "FOXA", "FOX",
    ],
    "XLV": [
        "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "AMGN", "PFE", "DHR",
        "ISRG", "SYK", "BSX", "GILD", "VRTX", "MDT", "ELV", "CI", "ZTS", "BDX",
        "REGN", "HCA", "MCK", "IDXX", "A", "IQV", "EW", "DXCM", "MTD", "BAX",
    ],
    "XBI": [
        "MRNA", "EXAS", "PCVX", "CYTK", "IONS", "SRPT", "ALNY", "BMRN", "HALO", "INCY",
        "RPRX", "NBIX", "CRNX", "INSM", "ITCI", "CORT", "NUVB", "KRYS", "GPCR", "DAWN",
    ],
    "XLF": [
        "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "SPGI", "BLK",
        "C", "AXP", "PGR", "CB", "MMC", "SCHW", "ICE", "CME", "AON", "MCO",
        "USB", "TFC", "PNC", "MET", "AIG", "AFL", "TRV", "ALL", "PRU", "MSCI",
    ],
    "XLY": [
        "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "CMG",
        "ORLY", "AZO", "ROST", "MAR", "HLT", "GM", "F", "DHI", "LEN", "GPC",
        "ULTA", "DRI", "POOL", "BBY", "EBAY",
    ],
    "XLP": [
        "PG", "COST", "KO", "PEP", "WMT", "PM", "MO", "MDLZ", "CL", "EL",
        "KMB", "GIS", "SYY", "HSY", "ADM", "STZ", "K", "MKC", "CHD", "CAG",
        "CLX", "SJM", "TSN", "KHC", "HRL",
    ],
    "XLI": [
        "GE", "CAT", "RTX", "UNP", "HON", "DE", "BA", "UPS", "LMT", "ADP",
        "WM", "ETN", "ITW", "EMR", "NOC", "GD", "FDX", "CSX", "NSC", "PCAR",
        "TT", "PH", "CTAS", "ROK", "AME", "CARR", "FAST", "ODFL", "VRSK", "IR",
    ],
    "XLE": [
        "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PXD", "PSX", "VLO", "OKE",
        "WMB", "HES", "KMI", "FANG", "DVN", "HAL", "BKR", "TRGP", "CTRA", "OXY",
    ],
    "XOP": [
        "COP", "EOG", "PXD", "DVN", "FANG", "CTRA", "OVV", "MRO", "APA", "EQT",
        "RRC", "AR", "SM", "CHRD", "MGY", "MTDR", "PR", "CRGY", "CPG", "NOG",
    ],
    "XLB": [
        "LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "VMC", "MLM", "DOW",
        "DD", "PPG", "CE", "EMN", "IFF", "ALB", "CF", "MOS", "FMC", "BALL",
    ],
    "XLU": [
        "NEE", "SO", "DUK", "CEG", "SRE", "D", "AEP", "PCG", "EXC", "XEL",
        "ED", "PEG", "WEC", "AWK", "ES", "ETR", "FE", "DTE", "PPL", "CMS",
    ],
    "XLRE": [
        "PLD", "AMT", "EQIX", "CCI", "PSA", "O", "SPG", "WELL", "DLR", "VICI",
        "AVB", "EQR", "SBAC", "WY", "ARE", "VTR", "MAA", "UDR", "ESS", "INVH",
    ],
    # --- Defense & Aerospace ETFs ---
    "ITA": [
        "RTX", "LMT", "NOC", "GD", "BA", "L3H", "HII", "TDG", "HEI", "LDOS",
        "SAIC", "BAH", "CACI", "KTOS", "BWXT", "DRS", "TXT", "SPR", "HXL", "CW",
        "MOOG", "AXON", "ACHR", "JOBY", "RKLB", "SPCE", "ASTR", "RDW", "LUNR", "MNTS",
    ],
    "PPA": [
        "RTX", "LMT", "NOC", "GD", "BA", "L3H", "HII", "TDG", "HEI", "LDOS",
        "SAIC", "BAH", "KTOS", "BWXT", "DRS", "MOOG", "CW", "TXT", "SPR", "HXL",
        "AXON", "RKLB", "ACHR", "JOBY", "OSIS", "MRCY", "VVX", "TGI", "AEROJET",
    ],
    # --- Cybersecurity ETFs ---
    "HACK": [
        "PANW", "CRWD", "FTNT", "ZS", "NET", "OKTA", "S", "CYBR", "TENB", "QLYS",
        "RPD", "SAIL", "VRNS", "PING", "CWAN", "LYFT", "CHKP", "SIEM", "OSPN", "EVBG",
        "CACI", "LDOS", "SAIC", "BAH", "LEIDOS", "MFNC", "PFPT", "MIME", "IRTC", "TELOS",
    ],
    "CIBR": [
        "PANW", "CRWD", "FTNT", "ZS", "NET", "OKTA", "S", "CYBR", "TENB", "QLYS",
        "RPD", "VRNS", "CHKP", "CACI", "SAIC", "LDOS", "BAH", "SAIL", "PING", "OSPN",
        "TELOS", "BBAI", "PLTR", "MSFT", "GOOGL", "CSCO", "IBM", "ANET", "FFIV", "JNPR",
    ],
    "BUG": [
        "PANW", "CRWD", "FTNT", "ZS", "NET", "OKTA", "S", "CYBR", "TENB", "QLYS",
        "RPD", "VRNS", "CHKP", "SAIL", "PING", "OSPN", "BBAI", "PLTR", "TELOS", "CACI",
        "SAIC", "BAH", "LDOS", "MSFT", "GOOGL", "CSCO", "ANET", "FFIV", "JNPR", "F5",
    ],
    # --- Energy / Oil & Gas ETFs ---
    "FENY": [
        "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "OKE", "WMB",
        "HES", "KMI", "FANG", "DVN", "HAL", "BKR", "TRGP", "CTRA", "OXY", "APA",
        "RRC", "AR", "SM", "EQT", "MRO", "CHRD", "NOG", "MGY", "MTDR", "PR",
    ],
    "OIH": [
        "SLB", "HAL", "BKR", "FTI", "NOV", "OIS", "WTTR", "LBRT", "PUMP", "NINE",
        "NR", "HP", "AROC", "PKD", "PTEN", "RES", "SOI", "FET", "CCLP", "KLXE",
        "DNOW", "MRC", "DRIL", "FLOTEK", "ODP", "NGAS", "TUSK", "DKNG", "NEX", "CKH",
    ],
    # --- Small-cap Tech ETF ---
    "PSCT": [
        "SMCI", "CRDO", "ONTO", "FORM", "ICHR", "COHU", "ACLS", "MKSI", "UCTT", "AEHR",
        "AMBA", "CEVA", "EMKR", "SLAB", "LYTS", "PCYG", "SMTC", "PDFS", "RMBS", "SITM",
        "OSIS", "PLXS", "SANM", "CTS", "TTEC", "PCVX", "DIOD", "KLIC", "AEIS", "NTGR",
    ],
    # --- Tech / AI / Robotics ETFs ---
    "VGT": [
        "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "CSCO", "ACN",
        "IBM", "INTU", "TXN", "QCOM", "AMAT", "NOW", "PANW", "ADI", "LRCX", "KLAC",
        "SNPS", "CDNS", "CRWD", "FTNT", "MCHP", "MU", "MSI", "APH", "NXPI", "TEL",
    ],
    "SMH": [
        "NVDA", "AVGO", "TSM", "ASML", "AMD", "QCOM", "TXN", "AMAT", "LRCX", "KLAC",
        "ADI", "MCHP", "MU", "NXPI", "MRVL", "ON", "MPWR", "INTC", "GFS", "SWKS",
        "ENTG", "QRVO", "COHR", "ONTO", "ACLS", "UCTT", "ICHR", "MKSI", "FORM", "CEVA",
    ],
    "IGV": [
        "MSFT", "ORCL", "CRM", "ADBE", "NOW", "INTU", "PANW", "SNPS", "CDNS", "CRWD",
        "FTNT", "WDAY", "TEAM", "DDOG", "ZS", "OKTA", "NET", "SNOW", "MDB", "HUBS",
        "BILL", "GTLB", "DOCN", "ESTC", "CFLT", "BRZE", "DOMO", "APPN", "ALTR", "TENB",
    ],
    "BOTZ": [
        "NVDA", "ABB", "ISRG", "KEYB", "FANUY", "IRBT", "AIXI", "OMCL", "KRNT", "ZBRA",
        "BRKS", "AZTA", "ONTO", "FORM", "ACLS", "NOVT", "LSCC", "AMBA", "TRMB", "CGNX",
        "MKSI", "COHU", "ICHR", "SMCI", "ACMR", "ENVX", "IRIAF", "IIVI", "ITRN", "KUKA",
    ],
    "ROBO": [
        "ISRG", "ABB", "CGNX", "TRMB", "IRBT", "ZBRA", "NOVT", "BRKS", "AZTA", "OMCL",
        "SMCI", "ONTO", "ACLS", "MKSI", "COHU", "ICHR", "FORM", "KRNT", "LSCC", "AMBA",
        "AIXI", "ENVX", "ACMR", "PTC", "ANSS", "CDNS", "SNPS", "ROP", "IDEX", "NDSN",
    ],
    "ARKQ": [
        "TSLA", "PLTR", "KTOS", "PATH", "ACHR", "JOBY", "RKLB", "ARCHER", "LILM", "EVTL",
        "TER", "TRMB", "ISRG", "DE", "AXON", "NVDA", "GOOGL", "AMZN", "MSFT", "AAPL",
        "AVAV", "SPCE", "ASTR", "RDW", "LUNR", "MNTS", "UAVS", "ACHR", "LAAX", "BLDE",
    ],
    # --- Cloud / SaaS / Internet ETFs ---
    "ARKW": [
        "TSLA", "COIN", "MSTR", "NVDA", "META", "GOOGL", "SHOP", "SNAP", "TWTR", "ROKU",
        "SQ", "HOOD", "OPEN", "UNITY", "U", "RBLX", "SPOT", "PINS", "DDOG", "SNOW",
        "NET", "CRWD", "ZS", "OKTA", "BILL", "MDB", "HUBS", "DOCN", "BRZE", "CFLT",
    ],
    "WCLD": [
        "NOW", "CRM", "WDAY", "DDOG", "SNOW", "MDB", "HUBS", "BILL", "ZS", "NET",
        "OKTA", "CRWD", "TEAM", "GTLB", "DOCN", "ESTC", "CFLT", "BRZE", "APPN", "TENB",
        "MNDY", "FRSH", "SMAR", "BOX", "ALTR", "DOMO", "VMWARE", "PCTY", "PAYC", "NCNO",
    ],
    "SKYY": [
        "MSFT", "GOOGL", "AMZN", "NOW", "CRM", "ADBE", "ORCL", "IBM", "CSCO", "ANET",
        "WDAY", "DDOG", "SNOW", "MDB", "HUBS", "NET", "ZS", "OKTA", "TEAM", "CFLT",
        "DOCN", "ESTC", "BRZE", "GTLB", "MNDY", "FRSH", "SMAR", "BOX", "APPN", "ALTR",
    ],
    # --- AI & Innovation ETFs ---
    "AIQ": [
        "NVDA", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AVGO", "AMD", "ORCL", "CRM",
        "PLTR", "PATH", "AI", "BBAI", "SOUN", "GFAI", "SYNTX", "DTST", "AIOT", "MIND",
        "NOW", "ADBE", "INTU", "SNPS", "CDNS", "CRWD", "PANW", "FTNT", "NET", "DDOG",
    ],
    "KOMP": [
        "TSLA", "NVDA", "PLTR", "MSTR", "COIN", "RBLX", "U", "SHOP", "SQ", "HOOD",
        "PATH", "AI", "BBAI", "SOUN", "KTOS", "AXON", "ACHR", "JOBY", "RKLB", "AVAV",
        "CRSP", "EDIT", "NTLA", "BEAM", "ARKG", "MRNA", "BNTX", "NVAX", "PACB", "ILMN",
    ],
    # --- ARK Genomics ---
    "ARKG": [
        "CRSP", "EDIT", "NTLA", "BEAM", "PACB", "ILMN", "RXRX", "SEER", "NUVB", "VERV",
        "FATE", "KYMR", "ARQT", "RCUS", "TWST", "CDNA", "GKOS", "EXAS", "OLINK", "PRNT",
        "IOVA", "TMDX", "ACCD", "MASS", "PGEN", "AGEN", "CLLS", "NKTR", "BLUE", "PTGX",
    ],
    # --- FinTech ETF ---
    "FINX": [
        "V", "MA", "PYPL", "SQ", "AFRM", "SOFI", "UPST", "LC", "OPEN", "HOOD",
        "COIN", "MSTR", "NU", "FLYW", "BILL", "PCTY", "PAYC", "NCNO", "LPRO", "DAVE",
        "TREE", "CURO", "OPORTUN", "MGNI", "EVBG", "WRLD", "EZCORP", "QFIN", "LMND", "ROOT",
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
