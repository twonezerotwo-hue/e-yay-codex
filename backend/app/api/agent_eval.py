"""
GET  /api/v1/agent/eval/recent       — son eval kayıtları
GET  /api/v1/agent/eval/stats        — toplam + ring durumu
POST /api/v1/agent/eval/run          — eval pass tetikle (audit → puan)

Sprint 4 / Item 4. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import agent_eval_service

router = APIRouter(prefix="/agent/eval", tags=["agent-eval"])


@router.get("/recent")
def list_recent_evals(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    items = agent_eval_service.get_recent_evals(limit=limit)
    return {"status": "ok", "count": len(items), "items": items}


@router.get("/stats")
def eval_stats() -> dict:
    return {"status": "ok", **agent_eval_service.stats()}


@router.post("/run")
def run_eval(
    limit: int = Query(default=100, ge=1, le=500),
    endpoint: str | None = Query(default=None),
    min_horizon_minutes: float = Query(default=5.0, ge=0.5, le=720.0),
) -> dict:
    """Audit log'tan son N kaydı al, puanla, sonucu döndür + persist et."""
    summary = agent_eval_service.run_eval_pass(
        limit=limit,
        endpoint=endpoint,
        min_horizon_minutes=min_horizon_minutes,
        persist=True,
    )
    summary["execution_mode"] = "OFF / NO_EXECUTION"
    return summary


__all__ = ["router"]
