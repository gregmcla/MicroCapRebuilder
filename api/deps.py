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

# Make scripts/ importable
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


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
