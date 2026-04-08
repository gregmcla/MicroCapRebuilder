#!/usr/bin/env python3
"""Tests for macro_context module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from macro_context import INDICATORS


def test_indicators_constant_has_expected_symbols():
    symbols = {ind["symbol"] for ind in INDICATORS}
    assert symbols == {"CL=F", "BZ=F", "GC=F", "DX-Y.NYB", "^VIX", "^TNX", "SPY"}


def test_indicators_have_display_names():
    for ind in INDICATORS:
        assert "symbol" in ind
        assert "name" in ind
        assert ind["name"]
