"""
Structured logging setup for the trading system.

Centralizes logger configuration so every module in `scripts/` and `api/` can
import a configured logger without each file rolling its own format.

Goals:
  1. Consistent format across cron scripts, the API, and ad-hoc python -m runs.
  2. Levels controllable via LOG_LEVEL env var (default INFO; cron sets DEBUG).
  3. Plays nicely with the existing cache_layer.CacheLogger — that uses its own
     "cache" namespace and structured `extra` fields. logging_setup configures
     the root logger and lets the cache logger inherit it.
  4. Doesn't try to migrate every print() in one go — the foundation is here;
     individual modules switch over as they're touched.

Usage:
    from logging_setup import get_logger
    log = get_logger(__name__)
    log.info("scan started", extra={"portfolio": portfolio_id, "tickers": len(tickers)})
    log.warning("yfinance rate-limited, retrying", extra={"ticker": ticker})

Patterns to migrate (when touching a module):
    print(f"Warning: X failed: {e}")            →   log.warning("X failed: %s", e)
    print(f"  [warn] {ticker}: skipping")       →   log.warning("skipping %s", ticker)
    print(f"  ⚠️ {msg}")  (diagnostic)         →   log.warning(msg)

Patterns to LEAVE as print():
    User-facing summary output (analyze pipeline emojis, table rendering,
    "✅ EXECUTED N actions"). Those are terminal ergonomics, not diagnostics.
"""
from __future__ import annotations

import logging
import os
import sys

_DEFAULT_FORMAT = (
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """
    Initialize root logger formatting + level. Idempotent — safe to call multiple
    times across module imports without duplicating handlers.

    Reads LOG_LEVEL env var if `level` is not passed. Anything that already
    configured a handler on the root logger (pytest's caplog, uvicorn's own
    setup) is left alone — we only add our handler when the root has none.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    effective = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, effective, logging.INFO)

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        root.addHandler(handler)
    root.setLevel(log_level)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger after ensuring root config is in place."""
    configure_logging()
    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]
