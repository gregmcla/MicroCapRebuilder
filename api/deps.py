"""Shared dependencies for the API layer.

Inserts scripts/ into sys.path so route modules can import
from the existing trading system.
"""

import sys
from pathlib import Path
from dataclasses import asdict, fields
from datetime import datetime, date
import math

import numpy as np
import pandas as pd
from fastapi import HTTPException, Path as FPath

# Make scripts/ importable
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def validate_portfolio_id(portfolio_id: str = FPath(...)) -> str:
    """Reject any portfolio_id not in the registry — prevents path traversal.

    Import is lazy because portfolio_registry depends on scripts/ being on
    sys.path, which this module sets up at import time.
    """
    from portfolio_registry import list_portfolios
    valid_ids = {p.id for p in list_portfolios(active_only=False)}
    if portfolio_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")
    return portfolio_id


def serialize(obj):
    """Recursively serialize dataclasses, DataFrames, enums, and numpy types to JSON-safe dicts."""
    if obj is None:
        return None
    if isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, pd.Timestamp):
        if pd.isna(obj):
            return None
        return obj.isoformat()
    if isinstance(obj, pd.DataFrame):
        records = obj.to_dict(orient="records")
        return [serialize(r) for r in records]
    if isinstance(obj, pd.Series):
        return serialize(obj.to_dict())
    if hasattr(obj, "__dataclass_fields__"):
        return {f.name: serialize(getattr(obj, f.name)) for f in fields(obj)}
    if hasattr(obj, "value") and hasattr(obj, "name"):
        # Enum
        return obj.value
    if isinstance(obj, dict):
        return {str(k): serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize(item) for item in obj]
    # Fallback
    return str(obj)
