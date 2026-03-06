import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from strategy_generator import GeneratedStrategy, _normalize_sector_weights


def test_generated_strategy_has_sector_weights_field():
    import inspect, dataclasses
    fields = {f.name for f in dataclasses.fields(GeneratedStrategy)}
    assert "sector_weights" in fields


def test_normalize_sector_weights_sums_correctly():
    weights = {"Technology": 60, "Healthcare": 40}
    result = _normalize_sector_weights(weights, ["Technology", "Healthcare"])
    assert result == {"Technology": 60, "Healthcare": 40}


def test_normalize_sector_weights_fills_missing_sectors():
    weights = {"Technology": 100}
    result = _normalize_sector_weights(weights, ["Technology", "Healthcare"])
    assert "Healthcare" in result
    assert result["Healthcare"] > 0


def test_normalize_sector_weights_handles_empty():
    result = _normalize_sector_weights({}, ["Technology", "Healthcare"])
    # Equal weights when nothing specified
    assert result["Technology"] == result["Healthcare"]
