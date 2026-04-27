"""Per-portfolio file lock for cross-process write coordination.

Why: cron jobs (update.sh, analyze.sh) and the API process can read+modify+write
positions.csv / transactions.csv / watchlist.jsonl concurrently. The atomic
tmp+replace pattern protects against in-process tearing but NOT cross-process
last-writer-wins races. fcntl.flock blocks across processes AND threads, and
the kernel releases automatically on process death.

Usage:
    from portfolio_lock import portfolio_lock

    with portfolio_lock(portfolio_id):
        # read-modify-write — guaranteed exclusive across processes
        ...

The lock file lives at data/portfolios/{id}/.write.lock — created lazily.
"""

import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent.parent / "data" / "portfolios"


def _lock_path(portfolio_id: str) -> Path:
    return _DATA_DIR / portfolio_id / ".write.lock"


@contextmanager
def portfolio_lock(portfolio_id: Optional[str]):
    """Exclusive lock on a portfolio's write operations.

    If portfolio_id is None or empty, this is a no-op (some legacy code
    paths don't carry a portfolio_id). Lock acquisition blocks until the
    holder releases — fine for the typical seconds-long write critical
    section, would need timeout handling if writes ever became long.
    """
    if not portfolio_id:
        yield
        return

    lock_file = _lock_path(portfolio_id)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    # Open in append mode so the file is created if missing without
    # truncating an existing one. The fd is what flock attaches to.
    with open(lock_file, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # blocks until acquired
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
