"""
Seed a real portfolio directory for integration tests.

Tests use a unique `_test_pipeline_<hex>` portfolio_id in the real
`data/portfolios/` tree. This avoids monkeypatching the 20+ scattered
`Path(__file__).parent.parent / "data"` constants and works with
load_portfolio_state(portfolio_id=...) which scopes most writes to the
portfolio dir. Cleanup runs in fixture teardown.
"""
import json
import secrets
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
PORTFOLIOS_DIR = DATA_DIR / "portfolios"
PIPELINE_STATUS_DIR = DATA_DIR / "pipeline_status"

TEST_ID_PREFIX = "_test_pipeline_"


def _baseline_config(starting_capital: float) -> dict:
    """Minimal config matching the real schema. Tests override what they need."""
    base = REPO_ROOT / "data" / "portfolios" / "microcap" / "config.json"
    if base.exists():
        cfg = json.loads(base.read_text())
    else:
        cfg = {}
    cfg = deepcopy(cfg)
    cfg["starting_capital"] = starting_capital
    # mode="live" — is_paper_mode() reads this and chooses positions.csv vs
    # positions_paper.csv. Tests write to the non-suffixed files; live mode
    # makes the loader read those files. paper_trading.enabled has no effect
    # on file resolution.
    cfg["mode"] = "live"
    cfg.setdefault("paper_trading", {})["enabled"] = True
    return cfg


def _deep_merge(base: dict, overrides: dict) -> dict:
    out = deepcopy(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class SeededPortfolio:
    def __init__(
        self,
        portfolio_id: str,
        portfolio_dir: Path,
        starting_capital: float,
    ):
        self.portfolio_id = portfolio_id
        self.portfolio_dir = portfolio_dir
        self.starting_capital = starting_capital

    def positions_path(self) -> Path:
        return self.portfolio_dir / "positions.csv"

    def transactions_path(self) -> Path:
        return self.portfolio_dir / "transactions.csv"

    def watchlist_path(self) -> Path:
        return self.portfolio_dir / "watchlist.jsonl"

    def daily_snapshots_path(self) -> Path:
        return self.portfolio_dir / "daily_snapshots.csv"

    def pipeline_status_path(self) -> Path:
        return PIPELINE_STATUS_DIR / f"{self.portfolio_id}.json"

    def last_analysis_path(self) -> Path:
        return self.portfolio_dir / ".last_analysis.json"

    def cleanup(self) -> None:
        if self.portfolio_dir.exists():
            shutil.rmtree(self.portfolio_dir, ignore_errors=True)
        ps = self.pipeline_status_path()
        if ps.exists():
            try:
                ps.unlink()
            except OSError:
                pass


def seed_portfolio(
    *,
    starting_capital: float = 1_000_000.0,
    config_overrides: Optional[dict] = None,
    positions: Optional[list[dict]] = None,
    transactions: Optional[list[dict]] = None,
    watchlist: Optional[list[dict]] = None,
    snapshots: Optional[list[dict]] = None,
) -> SeededPortfolio:
    """Build a real portfolio directory under data/portfolios/_test_pipeline_<hex>/."""
    from schema import (
        DAILY_SNAPSHOT_COLUMNS,
        POSITION_COLUMNS,
        TRANSACTION_COLUMNS,
    )

    portfolio_id = f"{TEST_ID_PREFIX}{secrets.token_hex(6)}"
    portfolio_dir = PORTFOLIOS_DIR / portfolio_id
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    cfg = _baseline_config(starting_capital)
    if config_overrides:
        cfg = _deep_merge(cfg, config_overrides)
    (portfolio_dir / "config.json").write_text(json.dumps(cfg, indent=2))

    pos_df = pd.DataFrame(positions or [], columns=POSITION_COLUMNS)
    pos_df.to_csv(portfolio_dir / "positions.csv", index=False)

    txn_df = pd.DataFrame(transactions or [], columns=TRANSACTION_COLUMNS)
    txn_df.to_csv(portfolio_dir / "transactions.csv", index=False)

    snap_df = pd.DataFrame(snapshots or [], columns=DAILY_SNAPSHOT_COLUMNS)
    snap_df.to_csv(portfolio_dir / "daily_snapshots.csv", index=False)

    wl_path = portfolio_dir / "watchlist.jsonl"
    with wl_path.open("w") as f:
        for entry in watchlist or []:
            f.write(json.dumps(entry) + "\n")

    return SeededPortfolio(
        portfolio_id=portfolio_id,
        portfolio_dir=portfolio_dir,
        starting_capital=starting_capital,
    )


def cleanup_orphans() -> int:
    """Clean up _test_pipeline_* portfolios from prior crashed runs. Returns count removed."""
    if not PORTFOLIOS_DIR.exists():
        return 0
    removed = 0
    for d in PORTFOLIOS_DIR.iterdir():
        if d.is_dir() and d.name.startswith(TEST_ID_PREFIX):
            shutil.rmtree(d, ignore_errors=True)
            ps = PIPELINE_STATUS_DIR / f"{d.name}.json"
            if ps.exists():
                try:
                    ps.unlink()
                except OSError:
                    pass
            removed += 1
    return removed
