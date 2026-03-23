#!/usr/bin/env python3
"""
Portfolio registry — manages the list of portfolios and their metadata.

Each portfolio gets its own directory under data/portfolios/{id}/ with its own
config.json, positions, transactions, snapshots, and watchlist files.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import shutil

# ─── Paths ────────────────────────────────────────────────────────────────────
REGISTRY_FILE = Path(__file__).parent.parent / "data" / "portfolios.json"
PORTFOLIOS_DIR = Path(__file__).parent.parent / "data" / "portfolios"

# ─── Universe Presets ─────────────────────────────────────────────────────────
UNIVERSE_PRESETS = {
    "microcap": {
        "label": "Micro-Cap ($50M–$300M)",
        "default_stop_loss_pct": 8.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "scoring_weights": {
            "price_momentum": 0.25,
            "earnings_growth": 0.15,
            "quality": 0.15,
            "volume": 0.10,
            "volatility": 0.15,
            "value_timing": 0.20,
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
        "discovery_filters": {
            "min_market_cap_m": 50,
            "max_market_cap_m": 2000,
            "min_avg_volume": 100000,
            "min_price": 2.0,
            "max_price": 500.0,
        },
        "etf_sources": ["IWM", "IJR", "VB"],
    },
    "smallcap": {
        "label": "Small-Cap ($300M–$2B)",
        "default_stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
        "scoring_weights": {
            "price_momentum": 0.25,
            "earnings_growth": 0.15,
            "quality": 0.15,
            "volume": 0.10,
            "volatility": 0.15,
            "value_timing": 0.20,
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
        "discovery_filters": {
            "min_market_cap_m": 300,
            "max_market_cap_m": 5000,
            "min_avg_volume": 200000,
            "min_price": 5.0,
            "max_price": 500.0,
        },
        "etf_sources": ["IWM", "IJR", "VB"],
        "exchange_listings_enabled": True,
        "extended_max": 6000,
        "total_watchlist_slots": 300,
    },
    "midcap": {
        "label": "Mid-Cap ($2B–$10B)",
        "default_stop_loss_pct": 6.0,
        "risk_per_trade_pct": 7.0,
        "max_position_pct": 10.0,
        "scoring_weights": {
            "price_momentum": 0.25,
            "earnings_growth": 0.15,
            "quality": 0.15,
            "volume": 0.10,
            "volatility": 0.15,
            "value_timing": 0.20,
        },
        "benchmark_symbol": "^MID",
        "fallback_benchmark": "MDY",
        "discovery_filters": {
            "min_market_cap_m": 2000,
            "max_market_cap_m": 15000,
            "min_avg_volume": 300000,
            "min_price": 10.0,
            "max_price": 1000.0,
        },
        "etf_sources": ["IJH", "VO", "MDY"],
        "exchange_listings_enabled": True,
        "extended_max": 6000,
        "total_watchlist_slots": 300,
    },
    "largecap": {
        "label": "Large-Cap ($10B+)",
        "default_stop_loss_pct": 5.0,
        "risk_per_trade_pct": 6.0,
        "max_position_pct": 10.0,
        "scoring_weights": {
            "price_momentum": 0.25,
            "earnings_growth": 0.15,
            "quality": 0.15,
            "volume": 0.10,
            "volatility": 0.15,
            "value_timing": 0.20,
        },
        "benchmark_symbol": "^GSPC",
        "fallback_benchmark": "SPY",
        "discovery_filters": {
            "min_market_cap_m": 10000,
            "max_market_cap_m": 999999,
            "min_avg_volume": 500000,
            "min_price": 20.0,
            "max_price": 5000.0,
        },
        "etf_sources": ["SPY", "IVV", "VOO"],
        "exchange_listings_enabled": True,
        "extended_max": 6000,
        "total_watchlist_slots": 300,
    },
    "allcap": {
        "label": "All-Cap (Everything)",
        "default_stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
        "scoring_weights": {
            "price_momentum": 0.25,
            "earnings_growth": 0.15,
            "quality": 0.15,
            "volume": 0.10,
            "volatility": 0.15,
            "value_timing": 0.20,
        },
        "benchmark_symbol": "^GSPC",
        "fallback_benchmark": "SPY",
        "discovery_filters": {
            "min_market_cap_m": 50,
            "max_market_cap_m": 999999,
            "min_avg_volume": 100000,
            "min_price": 2.0,
            "max_price": 5000.0,
        },
        "etf_sources": [],  # Uses all DEFAULT_ETFS — no restriction
        "exchange_listings_enabled": True,
        "extended_max": 6000,
        "total_watchlist_slots": 300,
    },
    "custom": {
        "label": "Custom Universe",
        "default_stop_loss_pct": 8.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "scoring_weights": {
            "price_momentum": 0.25,
            "earnings_growth": 0.15,
            "quality": 0.15,
            "volume": 0.10,
            "volatility": 0.15,
            "value_timing": 0.20,
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
        "discovery_filters": {
            "min_market_cap_m": 300,
            "max_market_cap_m": 50000,
            "min_avg_volume": 200000,
            "min_price": 5.0,
            "max_price": 1000.0,
        },
        "etf_sources": ["IWM", "IJR", "VB"],
    },
}

# ─── Sector ETF Map ──────────────────────────────────────────────────────────
# Maps GICS sectors to ETF tickers used as data sources for stock discovery.
# We never buy ETFs — these are used to find individual stocks.
SECTOR_ETF_MAP = {
    "Technology": ["XLK", "SOXX"],
    "Communication": ["XLC"],
    "Healthcare": ["XLV", "XBI"],
    "Financials": ["XLF"],
    "Consumer Discretionary": ["XLY"],
    "Consumer Staples": ["XLP"],
    "Industrials": ["XLI"],
    "Energy": ["XLE", "XOP"],
    "Materials": ["XLB"],
    "Utilities": ["XLU"],
    "Real Estate": ["XLRE"],
}

ALL_SECTORS = list(SECTOR_ETF_MAP.keys())

# ─── Trading Style Presets ────────────────────────────────────────────────────
TRADING_STYLES = {
    "aggressive_momentum": {
        "label": "Aggressive Momentum",
        "description": "High momentum + relative strength, tight stops, larger positions",
        "scoring_weights": {
            "price_momentum": 0.40,
            "earnings_growth": 0.10,
            "quality": 0.05,
            "volume": 0.15,
            "volatility": 0.10,
            "value_timing": 0.20,
        },
        "default_stop_loss_pct": 5.0,
        "risk_per_trade_pct": 5.0,
        "max_position_pct": 10.0,
        "trailing_stop_trigger_pct": 8.0,
        "trailing_stop_distance_pct": 5.0,
        "scan_types": {
            "momentum_breakouts": True,
            "oversold_bounces": False,
            "sector_leaders": True,
            "volume_anomalies": True,
        },
    },
    "balanced": {
        "label": "Balanced",
        "description": "Even factor weights, moderate risk, all scan types",
        "scoring_weights": {
            "price_momentum": 0.25,
            "earnings_growth": 0.15,
            "quality": 0.15,
            "volume": 0.10,
            "volatility": 0.15,
            "value_timing": 0.20,
        },
        "default_stop_loss_pct": 7.0,
        "risk_per_trade_pct": 3.0,
        "max_position_pct": 8.0,
        "trailing_stop_trigger_pct": 12.0,
        "trailing_stop_distance_pct": 7.0,
        "scan_types": {
            "momentum_breakouts": True,
            "oversold_bounces": True,
            "sector_leaders": True,
            "volume_anomalies": True,
        },
    },
    "conservative_value": {
        "label": "Conservative Value",
        "description": "Low volatility preference, wide stops, smaller positions",
        "scoring_weights": {
            "price_momentum": 0.10,
            "earnings_growth": 0.15,
            "quality": 0.25,
            "volume": 0.10,
            "volatility": 0.20,
            "value_timing": 0.20,
        },
        "default_stop_loss_pct": 8.0,
        "risk_per_trade_pct": 2.0,
        "max_position_pct": 6.0,
        "trailing_stop_trigger_pct": 15.0,
        "trailing_stop_distance_pct": 8.0,
        "scan_types": {
            "momentum_breakouts": False,
            "oversold_bounces": True,
            "sector_leaders": True,
            "volume_anomalies": False,
        },
    },
    "mean_reversion": {
        "label": "Mean Reversion",
        "description": "Buy dips in quality stocks, oversold bounces, moderate risk",
        "scoring_weights": {
            "price_momentum": 0.10,
            "earnings_growth": 0.10,
            "quality": 0.15,
            "volume": 0.15,
            "volatility": 0.10,
            "value_timing": 0.40,
        },
        "default_stop_loss_pct": 6.0,
        "risk_per_trade_pct": 3.0,
        "max_position_pct": 8.0,
        "trailing_stop_trigger_pct": 10.0,
        "trailing_stop_distance_pct": 6.0,
        "scan_types": {
            "momentum_breakouts": False,
            "oversold_bounces": True,
            "sector_leaders": False,
            "volume_anomalies": True,
        },
    },
}


# ─── Data Classes ─────────────────────────────────────────────────────────────
@dataclass
class PortfolioMeta:
    id: str
    name: str
    universe: str
    created: str
    starting_capital: float
    active: bool = True


# ─── Registry I/O ─────────────────────────────────────────────────────────────
def load_registry() -> dict:
    """Load the portfolio registry from disk. Returns default if not exists."""
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: failed to load registry: {e}")
    return {"default_portfolio": None, "portfolios": {}}


def save_registry(registry: dict) -> None:
    """Save the portfolio registry to disk, creating parent dirs if needed."""
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def list_portfolios(active_only: bool = True) -> list[PortfolioMeta]:
    """List all portfolios, optionally filtering to active only."""
    registry = load_registry()
    result = []
    for pid, meta in registry.get("portfolios", {}).items():
        pm = PortfolioMeta(
            id=pid,
            name=meta.get("name", pid),
            universe=meta.get("universe", "microcap"),
            created=meta.get("created", ""),
            starting_capital=meta.get("starting_capital", 50000.0),
            active=meta.get("active", True),
        )
        if active_only and not pm.active:
            continue
        result.append(pm)
    return result


def get_default_portfolio_id() -> Optional[str]:
    """Get the default portfolio ID, or None if not set."""
    registry = load_registry()
    return registry.get("default_portfolio")


def get_portfolio_dir(portfolio_id: str) -> Path:
    """Get the data directory for a specific portfolio."""
    return PORTFOLIOS_DIR / portfolio_id


def create_portfolio(
    portfolio_id: str,
    name: str,
    universe: str,
    starting_capital: float,
    sectors: list[str] = None,
    trading_style: str = None,
    ai_config: dict = None,
    sector_weights: dict = None,
    ai_driven: bool = False,
    strategy_dna: str = None,
) -> PortfolioMeta:
    """Create a new portfolio: directory, config, and registry entry.

    Clones the current data/config.json and applies:
    1. Universe preset overrides (cap size)
    2. Trading style overrides (scoring weights, risk params, scan types)
    3. Sector focus (ETF sources, sector filter)
    4. AI-generated config overrides (if provided)
    """
    if universe not in UNIVERSE_PRESETS:
        raise ValueError(
            f"Unknown universe '{universe}'. "
            f"Valid options: {', '.join(UNIVERSE_PRESETS.keys())}"
        )

    portfolio_dir = get_portfolio_dir(portfolio_id)
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    # Clone base config
    base_config_file = Path(__file__).parent.parent / "data" / "config.json"
    if base_config_file.exists():
        with open(base_config_file) as f:
            config = json.load(f)
    else:
        config = {}

    # --- Layer 1: Universe preset (cap size) ---
    preset = UNIVERSE_PRESETS[universe]
    config["starting_capital"] = starting_capital
    config["default_stop_loss_pct"] = preset["default_stop_loss_pct"]
    config["risk_per_trade_pct"] = preset["risk_per_trade_pct"]
    config["max_position_pct"] = preset["max_position_pct"]
    config["benchmark_symbol"] = preset["benchmark_symbol"]
    config["fallback_benchmark"] = preset["fallback_benchmark"]

    if "scoring" not in config:
        config["scoring"] = {}
    config["scoring"]["default_weights"] = dict(preset["scoring_weights"])

    if "discovery" not in config:
        config["discovery"] = {}
    config["discovery"]["filters"] = dict(preset["discovery_filters"])

    if "universe" not in config:
        config["universe"] = {}
    if "sources" not in config["universe"]:
        config["universe"]["sources"] = {}
    if "etf_holdings" not in config["universe"]["sources"]:
        config["universe"]["sources"]["etf_holdings"] = {}
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

    # --- Layer 2: Trading style overrides ---
    if trading_style and trading_style in TRADING_STYLES:
        style = TRADING_STYLES[trading_style]
        config["scoring"]["default_weights"] = dict(style["scoring_weights"])
        config["default_stop_loss_pct"] = style["default_stop_loss_pct"]
        config["risk_per_trade_pct"] = style["risk_per_trade_pct"]
        config["max_position_pct"] = style["max_position_pct"]
        config["discovery"]["scan_types"] = dict(style["scan_types"])

        # Apply trailing stop settings
        if "enhanced_trading" not in config:
            config["enhanced_trading"] = {}
        if "layer1" not in config["enhanced_trading"]:
            config["enhanced_trading"]["layer1"] = {}
        config["enhanced_trading"]["layer1"]["trailing_stop_trigger_pct"] = style["trailing_stop_trigger_pct"]
        config["enhanced_trading"]["layer1"]["trailing_stop_distance_pct"] = style["trailing_stop_distance_pct"]


    # --- Layer 3: Sector focus ---
    if sectors and len(sectors) < len(ALL_SECTORS):
        # Build ETF sources from selected sectors + cap-size base ETF
        sector_etfs = []
        for sector in sectors:
            sector_etfs.extend(SECTOR_ETF_MAP.get(sector, []))
        # Keep first cap-size ETF for breadth
        base_etf = preset["etf_sources"][0] if preset["etf_sources"] else None
        if base_etf and base_etf not in sector_etfs:
            sector_etfs.insert(0, base_etf)
        # Deduplicate while preserving order
        seen = set()
        unique_etfs = []
        for etf in sector_etfs:
            if etf not in seen:
                seen.add(etf)
                unique_etfs.append(etf)
        config["universe"]["sources"]["etf_holdings"]["etfs"] = unique_etfs
        config["discovery"]["sector_filter"] = list(sectors)
    else:
        # "All" sectors — no filter
        config["discovery"].pop("sector_filter", None)

    # --- Sector watchlist config ---
    if "watchlist" not in config["discovery"]:
        config["discovery"]["watchlist"] = {}
    config["discovery"]["watchlist"]["total_watchlist_slots"] = preset.get(
        "total_watchlist_slots", config["discovery"].get("watchlist", {}).get("max_tickers", 250)
    )
    if sector_weights:
        config["discovery"]["watchlist"]["sector_weights"] = dict(sector_weights)
        # Ensure sector_filter is set from sector_weights keys when sectors param not provided
        if not sectors:
            config["discovery"]["sector_filter"] = list(sector_weights.keys())
    else:
        config["discovery"]["watchlist"].pop("sector_weights", None)

    # --- Layer 4: AI-generated overrides ---
    if ai_config:
        if "scoring_weights" in ai_config:
            from stock_scorer import StockScorer
            config["scoring"]["default_weights"] = StockScorer._migrate_weight_keys(ai_config["scoring_weights"])
        if "stop_loss_pct" in ai_config:
            config["default_stop_loss_pct"] = ai_config["stop_loss_pct"]
        if "risk_per_trade_pct" in ai_config:
            config["risk_per_trade_pct"] = ai_config["risk_per_trade_pct"]
        if "max_position_pct" in ai_config:
            config["max_position_pct"] = ai_config["max_position_pct"]
        if "scan_types" in ai_config:
            config["discovery"]["scan_types"] = ai_config["scan_types"]
        if "sectors" in ai_config:
            sector_etfs = []
            for sector in ai_config["sectors"]:
                sector_etfs.extend(SECTOR_ETF_MAP.get(sector, []))
            base_etf = preset["etf_sources"][0] if preset["etf_sources"] else None
            if base_etf and base_etf not in sector_etfs:
                sector_etfs.insert(0, base_etf)
            config["universe"]["sources"]["etf_holdings"]["etfs"] = list(dict.fromkeys(sector_etfs))
            config["discovery"]["sector_filter"] = ai_config["sectors"]
        if "sector_weights" in ai_config:
            if "watchlist" not in config["discovery"]:
                config["discovery"]["watchlist"] = {}
            config["discovery"]["watchlist"]["sector_weights"] = ai_config["sector_weights"]
            # Ensure sector_filter is set from sector_weights keys when not already set via sectors
            if "sector_filter" not in config["discovery"]:
                config["discovery"]["sector_filter"] = list(ai_config["sector_weights"].keys())
        if "etf_sources" in ai_config:
            existing = config["universe"]["sources"]["etf_holdings"]["etfs"]
            for etf in ai_config["etf_sources"]:
                if etf not in existing:
                    existing.append(etf)

    # Store strategy metadata
    created_via = "ai_driven" if ai_driven else ("ai" if ai_config else "wizard")
    config["strategy"] = {
        "name": (TRADING_STYLES[trading_style]["label"] if trading_style and trading_style in TRADING_STYLES
                 else ai_config.get("strategy_name", "Custom") if ai_config else "Default"),
        "sectors": sectors or [],
        "trading_style": trading_style or (ai_config.get("trading_style") if ai_config else None),
        "created_via": created_via,
        "ai_prompt": ai_config.get("prompt") if ai_config else None,
        "ai_rationale": ai_config.get("rationale") if ai_config else None,
    }

    # AI-driven mode: store flag, strategy DNA, harden defaults
    if ai_driven:
        config["ai_driven"] = True
        if strategy_dna:
            config["strategy_dna"] = strategy_dna
        # Hardened scan defaults — prevent timeout issues
        config["universe"]["tiers"]["extended"]["max_tickers"] = 3000
        config["universe"]["tiers"]["extended"]["scan_frequency"] = "rotating_3day"
        config["universe"]["sources"]["exchange_listings"]["enabled"] = False
        # Larger watchlist gives Claude more candidates to reason across
        config.setdefault("discovery", {}).setdefault("watchlist", {})
        config["discovery"]["watchlist"]["total_watchlist_slots"] = 500

    # Write config
    config_path = portfolio_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Register
    meta = PortfolioMeta(
        id=portfolio_id,
        name=name,
        universe=universe,
        created=datetime.now().isoformat(timespec="seconds"),
        starting_capital=starting_capital,
        active=True,
    )
    registry = load_registry()
    registry["portfolios"][portfolio_id] = asdict(meta)
    if registry.get("default_portfolio") is None:
        registry["default_portfolio"] = portfolio_id
    save_registry(registry)

    return meta


def archive_portfolio(portfolio_id: str) -> None:
    """Archive a portfolio by setting active=False in the registry."""
    registry = load_registry()
    portfolios = registry.get("portfolios", {})
    if portfolio_id not in portfolios:
        raise ValueError(f"Portfolio '{portfolio_id}' not found in registry")
    portfolios[portfolio_id]["active"] = False

    # If this was the default, clear or pick another active one
    if registry.get("default_portfolio") == portfolio_id:
        active_ids = [
            pid for pid, p in portfolios.items()
            if p.get("active", True) and pid != portfolio_id
        ]
        registry["default_portfolio"] = active_ids[0] if active_ids else None

    save_registry(registry)


if __name__ == "__main__":
    # Show current registry status
    portfolios = list_portfolios(active_only=False)
    if not portfolios:
        print("No portfolios registered yet.")
    else:
        default_id = get_default_portfolio_id()
        for p in portfolios:
            marker = " (default)" if p.id == default_id else ""
            status = "active" if p.active else "archived"
            print(f"  {p.id}: {p.name} [{p.universe}] ${p.starting_capital:,.0f} — {status}{marker}")
