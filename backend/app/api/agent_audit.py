"""
GET /api/v1/agent/audit/recent — Son agent audit kayıtları
GET /api/v1/agent/audit/stats  — Kayıt dağılımı

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.agent_audit_log import get_recent, stats

router = APIRouter(prefix="/agent/audit", tags=["agent-audit"])


@router.get("/recent")
def get_recent_audit(
    limit: int = Query(default=50, ge=1, le=500),
    endpoint: str | None = Query(default=None, description="Endpoint filtresi (örn: agent.insight)"),
) -> dict:
    items = get_recent(limit=limit, endpoint=endpoint)
    return {
        "status": "ok",
        "count":  len(items),
        "items":  items,
    }


@router.get("/stats")
def get_audit_stats() -> dict:
    return {"status": "ok", **stats()}


__all__ = ["router"]
