#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import digest_service


def test_book_rollup_sums_provided_rows_and_counts_health():
    # `_roll_up_book` sums the rows it's given (live-filtering happens upstream
    # in build_digest — see Task 6). Two live, non-excluded portfolios.
    rows = [
        {"id": "max", "equity": 5_000_000.0, "day_pnl": 12_000.0, "total_return_pct": 18.4, "exclude": False},
        {"id": "gov-infra", "equity": 1_000_000.0, "day_pnl": 6_420.0, "total_return_pct": 9.3, "exclude": False},
    ]
    book = digest_service._roll_up_book(rows)
    assert book["equity"] == 6_000_000.0
    assert book["day_pnl"] == 18_420.0
    assert book["health"]["green"] == 2
    assert book["health"]["red"] == 0


def test_book_rollup_respects_exclude_from_aggregates():
    rows = [
        {"id": "max", "equity": 5_000_000.0, "day_pnl": 10.0, "total_return_pct": 1.0, "exclude": False},
        {"id": "max2", "equity": 4_960_000.0, "day_pnl": 5.0, "total_return_pct": 1.0, "exclude": True},
    ]
    book = digest_service._roll_up_book(rows)
    assert book["equity"] == 5_000_000.0  # max2 excluded
    assert book["day_pnl"] == 10.0          # max2's 5.0 excluded
    assert book["health"]["green"] == 1     # only max counted
    assert book["health"]["red"] == 0


def test_derive_trend_from_sparkline_and_alpha():
    rising = [100, 101, 103, 106, 110]
    falling = [110, 106, 103, 101, 98]
    flat = [100, 100.2, 99.9, 100.1, 100.0]
    assert digest_service.derive_trend(rising, vs_bench_pct=12.0) == "ahead"
    assert digest_service.derive_trend(falling, vs_bench_pct=-21.0) == "fading"
    assert digest_service.derive_trend(flat, vs_bench_pct=-0.5) == "flat"


def test_derive_trend_handles_short_series():
    assert digest_service.derive_trend([], vs_bench_pct=0.0) == "flat"
    assert digest_service.derive_trend([100.0], vs_bench_pct=0.0) == "flat"
