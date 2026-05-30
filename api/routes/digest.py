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
def get_digest_narrative(range: str = Query("3M", pattern="^(1W|1M|3M|YTD|ALL)$"),
                         regenerate: bool = False):
    return serialize(digest_service.get_or_build_narrative(range_key=range, regenerate=regenerate))
