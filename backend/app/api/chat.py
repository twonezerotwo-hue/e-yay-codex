"""
E-YAY Chat — Ajansal piyasa analiz sohbeti.
POST /api/v1/chat

SSE Protokolü:
  data: {"text": "..."}               — metin parçacığı
  data: {"tool": "...", "label": "..."}  — araç çağrısı bildirimi
  data: {"error": "..."}              — hata
  data: [DONE]                        — bitti

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.eyay_agent_service import agent_chat_stream

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request modeli
# ---------------------------------------------------------------------------

class _Msg(BaseModel):
    role: str     # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[_Msg]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("")
def chat(body: ChatRequest) -> StreamingResponse:
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    return StreamingResponse(
        agent_chat_stream(messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = [name for name in globals() if not name.startswith("_")]
