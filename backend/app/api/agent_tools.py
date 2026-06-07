"""
GET  /api/v1/agent/tools             — kayıtlı araç listesi (+input_schema)
POST /api/v1/agent/tools/invoke      — tek araç çağrısı
GET  /api/v1/agent/tools/anthropic   — Anthropic tools formatı (LLM provider için)

Sprint 6 / Item 6. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import agent_tool_registry

router = APIRouter(prefix="/agent/tools", tags=["agent-tools"])


@router.get("")
def list_tools() -> dict:
    items = agent_tool_registry.list_tools()
    return {"status": "ok", "count": len(items), "items": items}


@router.get("/anthropic")
def anthropic_tools() -> dict:
    return {"status": "ok", "tools": agent_tool_registry.to_anthropic_tools()}


class InvokeRequest(BaseModel):
    name: str
    params: dict | None = None


@router.post("/invoke")
def invoke_tool(body: InvokeRequest) -> dict:
    out = agent_tool_registry.invoke(body.name, body.params or {})
    out["execution_mode"] = "OFF / NO_EXECUTION"
    return out


__all__ = ["router"]
