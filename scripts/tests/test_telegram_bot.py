"""Tests for telegram_bot command helpers.

Skipped automatically where python-telegram-bot is not installed (importing
telegram_bot requires the `telegram` package). Runs in any environment that
has the bot's runtime dependencies.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# telegram_bot imports `telegram` at module load — skip the whole module if absent.
pytest.importorskip("telegram")

from telegram_bot import _match_portfolio  # noqa: E402


def test_match_portfolio_exact():
    assert _match_portfolio("microcap", ["microcap", "max2"]) == "microcap"


def test_match_portfolio_case_insensitive():
    # User types uppercase (e.g. "/scan MAX") but ids are stored lowercase.
    assert _match_portfolio("MAX", ["max", "microcap"]) == "max"
    assert _match_portfolio("MicroCap", ["microcap"]) == "microcap"


def test_match_portfolio_strips_whitespace():
    assert _match_portfolio("  max2 ", ["max2", "microcap"]) == "max2"


def test_match_portfolio_no_match_returns_none():
    assert _match_portfolio("nope", ["microcap", "max2"]) is None


def test_match_portfolio_empty_returns_none():
    assert _match_portfolio("", ["microcap"]) is None
