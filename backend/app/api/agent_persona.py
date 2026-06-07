"""
GET /api/v1/agent/personas             — kayıtlı persona listesi
GET /api/v1/agent/personas/{key}       — tek persona detayı + sistem promptu önizleme

Sprint 9 / Item 9. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import agent_persona

router = APIRouter(prefix="/agent/personas", tags=["agent-persona"])


@router.get("")
def list_personas() -> dict:
    items = agent_persona.list_personas()
    return {"status": "ok", "count": len(items), "items": items}


@router.get("/{key}")
def get_persona(
    key: str,
    regime: str | None = Query(default=None, description="Bellek bloğunu rejimle filtrele"),
) -> dict:
    p = agent_persona.get_persona(key)
    if p.key != key and key != "analyst":
        raise HTTPException(status_code=404, detail=f"persona bulunamadı: {key}")
    preview = agent_persona.build_system_prompt(persona_key=key, regime=regime)
    return {
        "status":      "ok",
        "persona": {
            "key":         p.key,
            "title":       p.title,
            "voice":       p.voice,
            "framing":     p.framing,
            "temperature": p.temperature,
        },
        "system_prompt_preview": preview,
    }


__all__ = ["router"]
