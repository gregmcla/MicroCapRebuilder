#!/usr/bin/env python3
"""Daily Digest aggregation endpoint."""

from fastapi import APIRouter, Query
from api.deps import serialize

import digest_service

router = APIRouter(prefix="/api", tags=["digest"])


@router.get("/digest")
def get_digest(range: str = Query("3M", pattern="^(1W|1M|3M|YTD|ALL)$")):
    return serialize(digest_service.build_digest(range_key=range))


@router.get("/digest/narrative")
def get_digest_narrative(range: str = Query("3M", pattern="^(1W|1M|3M|YTD|ALL)$")):
    d = digest_service.build_digest(range_key=range)
    book = d["book"]
    deployed = 0.0  # optional: book deployed_pct if cheap; 0 is a safe posture input
    posture = digest_service.compute_posture(
        regime=d["recap"].get("regime", {}).get("label", "SIDEWAYS"),
        deployed_pct=deployed, book_alpha=book.get("vs_spy_alltime_pct", 0.0))
    return serialize(digest_service.build_digest_narrative(d, posture))
