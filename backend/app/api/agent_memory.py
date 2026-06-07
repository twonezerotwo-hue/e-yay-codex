"""
GET  /api/v1/agent/memory/recall     — filtreli memory listesi
GET  /api/v1/agent/memory/stats      — sayım + kategori dağılımı
POST /api/v1/agent/memory/remember   — yeni not ekle
POST /api/v1/agent/memory/forget     — id ile sil
GET  /api/v1/agent/memory/context    — LLM prompt için özet blok

Sprint 7 / Item 7. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import agent_memory_service

router = APIRouter(prefix="/agent/memory", tags=["agent-memory"])


@router.get("/recall")
def recall(
    limit: int = Query(default=20, ge=1, le=200),
    category: str | None = Query(default=None),
    regime: str | None = Query(default=None),
    contains: str | None = Query(default=None),
) -> dict:
    items = agent_memory_service.recall(
        limit=limit, category=category, regime=regime, contains=contains,
    )
    return {"status": "ok", "count": len(items), "items": items}


@router.get("/stats")
def stats() -> dict:
    return {"status": "ok", **agent_memory_service.stats()}


@router.get("/context")
def context_block(
    regime: str | None = Query(default=None),
    max_chars: int = Query(default=1200, ge=200, le=4000),
    max_items: int = Query(default=8, ge=1, le=20),
) -> dict:
    text = agent_memory_service.context_for_prompt(
        regime=regime, max_chars=max_chars, max_items=max_items,
    )
    return {"status": "ok", "context": text, "length": len(text)}


class RememberRequest(BaseModel):
    category: str = "observation"
    text: str
    regime: str | None = None
    snapshot_id: str | None = None
    confidence_pct: float | None = None
    tags: list[str] | None = None


@router.post("/remember")
def remember(body: RememberRequest) -> dict:
    entry = agent_memory_service.remember(
        category=body.category,
        text=body.text,
        regime=body.regime,
        snapshot_id=body.snapshot_id,
        confidence_pct=body.confidence_pct,
        tags=body.tags,
    )
    return {"status": "ok", "entry": entry}


class ForgetRequest(BaseModel):
    id: str


@router.post("/forget")
def forget(body: ForgetRequest) -> dict:
    removed = agent_memory_service.forget(body.id)
    return {"status": "ok", "removed": removed}


__all__ = ["router"]
