"""
AI Trade Opinion API.

Endpointler:
  GET /agent/trade-opinion          — güncel opinion (read-only, 60sn cache)
  GET /agent/trade-opinion/recent   — store'dan son opinion'lar

GET hiçbir state mutate etmez; opinion store'a yazım scheduler adımında olur.
PAPER_SAFE / NO_EXECUTION — broker yok, emir yok.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Query

from app.services.ai_trade_opinion_service import build_ai_trade_opinion
from app.storage.ai_trade_opinion_store import load_recent_ai_trade_opinions

router = APIRouter(prefix="/agent", tags=["agent-trade-opinion"])

_CACHE: tuple[float, dict[str, Any]] | None = None
_TTL = 60.0


@router.get("/trade-opinion")
def get_trade_opinion() -> dict[str, Any]:
    """Stored data'dan deterministik trade opinion üretir — read-only."""
    global _CACHE
    now = time.monotonic()
    if _CACHE and (now - _CACHE[0]) < _TTL:
        return _CACHE[1]
    result = build_ai_trade_opinion()
    _CACHE = (now, result)
    return result


@router.get("/trade-opinion/recent")
def get_recent_trade_opinions(
    limit: int = Query(default=24, ge=1, le=200),
) -> dict[str, Any]:
    """Store'daki son opinion kayıtları (scheduler tarafından yazılır)."""
    items = load_recent_ai_trade_opinions(limit=limit)
    return {
        "status":         "ok",
        "count":          len(items),
        "items":          items,
        "execution_mode": "PAPER_SAFE",
    }


__all__ = ["router"]
