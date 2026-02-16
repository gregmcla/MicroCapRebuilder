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
            "momentum": 0.30,
            "volatility": 0.15,
            "volume": 0.10,
            "relative_strength": 0.20,
            "mean_reversion": 0.10,
            "rsi": 0.15,
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
    },
    "smallcap": {
        "label": "Small-Cap ($300M–$2B)",
        "default_stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
        "scoring_weights": {
            "momentum": 0.20,
            "volatility": 0.18,
            "volume": 0.15,
            "relative_strength": 0.20,
            "mean_reversion": 0.12,
            "rsi": 0.15,
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
    },
    "midcap": {
        "label": "Mid-Cap ($2B–$10B)",
        "default_stop_loss_pct": 6.0,
        "risk_per_trade_pct": 7.0,
        "max_position_pct": 10.0,
        "scoring_weights": {
            "momentum": 0.15,
            "volatility": 0.15,
            "volume": 0.12,
            "relative_strength": 0.18,
            "mean_reversion": 0.25,
            "rsi": 0.15,
        },
        "benchmark_symbol": "^MID",
        "fallback_benchmark": "MDY",
    },
    "largecap": {
        "label": "Large-Cap ($10B+)",
        "default_stop_loss_pct": 5.0,
        "risk_per_trade_pct": 6.0,
        "max_position_pct": 10.0,
        "scoring_weights": {
            "momentum": 0.15,
            "volatility": 0.15,
            "volume": 0.10,
            "relative_strength": 0.30,
            "mean_reversion": 0.15,
            "rsi": 0.15,
        },
        "benchmark_symbol": "^GSPC",
        "fallback_benchmark": "SPY",
    },
    "custom": {
        "label": "Custom Universe",
        "default_stop_loss_pct": 8.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "scoring_weights": {
            "momentum": 0.30,
            "volatility": 0.15,
            "volume": 0.10,
            "relative_strength": 0.20,
            "mean_reversion": 0.10,
            "rsi": 0.15,
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
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
) -> PortfolioMeta:
    """Create a new portfolio: directory, config, and registry entry.

    Clones the current data/config.json and applies universe preset overrides.
    """
    # Validate universe
    if universe not in UNIVERSE_PRESETS:
        raise ValueError(
            f"Unknown universe '{universe}'. "
            f"Valid options: {', '.join(UNIVERSE_PRESETS.keys())}"
        )

    # Create portfolio directory
    portfolio_dir = get_portfolio_dir(portfolio_id)
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    # Clone and customize config
    base_config_file = Path(__file__).parent.parent / "data" / "config.json"
    if base_config_file.exists():
        with open(base_config_file) as f:
            config = json.load(f)
    else:
        config = {}

    # Apply universe preset overrides
    preset = UNIVERSE_PRESETS[universe]
    config["starting_capital"] = starting_capital
    config["default_stop_loss_pct"] = preset["default_stop_loss_pct"]
    config["risk_per_trade_pct"] = preset["risk_per_trade_pct"]
    config["max_position_pct"] = preset["max_position_pct"]
    config["benchmark_symbol"] = preset["benchmark_symbol"]
    config["fallback_benchmark"] = preset["fallback_benchmark"]

    # Apply scoring weights
    if "scoring" not in config:
        config["scoring"] = {}
    config["scoring"]["default_weights"] = dict(preset["scoring_weights"])

    # Write portfolio config
    config_path = portfolio_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Create portfolio metadata
    meta = PortfolioMeta(
        id=portfolio_id,
        name=name,
        universe=universe,
        created=datetime.now().isoformat(timespec="seconds"),
        starting_capital=starting_capital,
        active=True,
    )

    # Register in portfolios.json
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
