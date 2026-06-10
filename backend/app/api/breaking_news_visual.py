"""
FAZ 15 — Breaking News Visual API.

Read-only endpoint:
  GET /breaking-news/visual

Son hourly snapshot'taki news_headlines'ı event radar modeline çevirir.
Karar üretmez. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter

from app.services.breaking_news_visual_adapter import build_news_visual_payload

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/breaking-news", tags=["breaking-news-visual"])

_CACHE: tuple[float, dict[str, Any]] | None = None
_TTL   = 30.0


@router.get("/visual")
def get_visual() -> dict[str, Any]:
    """Read-only event radar payload. 30sn TTL cache."""
    global _CACHE
    now = time.monotonic()
    if _CACHE is not None and (now - _CACHE[0]) < _TTL:
        return _CACHE[1]

    news: list[dict] = []
    try:
        from app.storage.hourly_snapshot_store import (  # noqa: PLC0415
            load_recent_hourly_snapshots,
        )
        snaps = load_recent_hourly_snapshots(limit=1)
        if snaps:
            report = snaps[-1].get("report") or {}
            news = list(report.get("news_headlines") or [])
    except Exception as exc:  # noqa: BLE001
        _log.warning("breaking_news_visual: snapshot store unavailable: %s", exc)

    payload = build_news_visual_payload(news)
    _CACHE = (now, payload)
    return payload
