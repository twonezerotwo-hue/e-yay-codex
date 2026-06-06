"""
GET /api/v1/alerts/recent — Son alert event'leri döndür (read-only).

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.alert_event_service import VOICE_ALERT_TYPES, get_recent
from app.services.telegram_alert_service import get_status as telegram_status

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/recent")
def get_recent_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    level: str | None = Query(default=None, description="Seviye filtresi: CRITICAL | ACTION_REQUIRED | TRADE_EVENT | WARNING | INFO"),
) -> dict:
    """En son alert event'leri döndür. Yeni → eski sıralı."""
    alerts = get_recent(limit=limit)
    if level:
        upper = level.upper()
        alerts = [a for a in alerts if a.get("level") == upper]
    return {
        "status":      "ok",
        "count":       len(alerts),
        "alerts":      alerts,
        "voice_types": sorted(VOICE_ALERT_TYPES),
        "telegram":    telegram_status(),
    }


__all__ = ["router"]
