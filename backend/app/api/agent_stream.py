"""
GET /api/v1/agent/insight/stream     — rule-based insight'ları SSE ile akış
GET /api/v1/ai-report/stream         — AI raporu paragraf-paragraf akış

Server-Sent Events formatı:
  event: <type>
  data: <json>

Tipler: heartbeat | meta | insight | chunk | done | error

Sprint 8 / Item 8. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import asyncio
import json
import time as _time
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["agent-stream"])


def _sse(event: str, data: dict | str) -> bytes:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


# ────────────────────────────────────────────────────────────────────────────
# Insight stream — rule-based pipeline'ı çalıştır, insight'ları teker teker yay
# ────────────────────────────────────────────────────────────────────────────

@router.get("/agent/insight/stream")
async def stream_insights() -> StreamingResponse:
    """Insight'ları üretildikleri sırayla akış.

    Pipeline tek seferlik koşar; sonuçları küçük parçalara böleriz ki
    frontend kullanıcıya cevabın gelişini hissettirsin.
    """

    async def gen():
        yield _sse("meta", {
            "execution_mode": "OFF / NO_EXECUTION",
            "started_at":     datetime.now(UTC).isoformat(),
        })
        # Heartbeat — uzun pipeline'da bağlantı düşmesin
        hb_task = None
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(8)
                    await queue.put(("heartbeat", {"ts": datetime.now(UTC).isoformat()}))
            except asyncio.CancelledError:
                return

        async def runner():
            try:
                # off-thread'de tam pipeline koşar
                from app.api.agent_insight import get_agent_insight
                response = await loop.run_in_executor(None, get_agent_insight)
                await queue.put(("status", {
                    "status": response.get("status"),
                    "snapshot_id": response.get("snapshot_id"),
                    "decision": response.get("decision"),
                }))
                insights = response.get("insights") or []
                for ins in insights:
                    await queue.put(("insight", ins))
                    await asyncio.sleep(0.06)  # akış hissi
                await queue.put(("done", {
                    "count":       len(insights),
                    "confidence":  response.get("confidence"),
                    "validation":  response.get("validation"),
                    "finished_at": datetime.now(UTC).isoformat(),
                }))
            except Exception as exc:
                await queue.put(("error", {"error": str(exc)[:240]}))
            finally:
                await queue.put((None, None))

        hb_task = asyncio.create_task(heartbeat())
        run_task = asyncio.create_task(runner())
        try:
            while True:
                event, data = await queue.get()
                if event is None:
                    break
                yield _sse(event, data)
        finally:
            hb_task.cancel()
            run_task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ────────────────────────────────────────────────────────────────────────────
# AI Report stream — paragrafları teker teker yay
# ────────────────────────────────────────────────────────────────────────────

@router.get("/ai-report/stream")
async def stream_ai_report() -> StreamingResponse:
    """AI raporunu üret ve narrative'i cümle/paragraf parçalarıyla akış.

    NOT: Anthropic SDK gerçek streaming verir; bu V1 sürümde rapor önce üretilir
    sonra parçalanır — frontend SSE UX'ini koruruz, sonraki sürümde true stream'e
    bağlanacak.
    """

    async def gen():
        yield _sse("meta", {
            "execution_mode": "OFF / NO_EXECUTION",
            "started_at":     datetime.now(UTC).isoformat(),
        })
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(10)
                    await queue.put(("heartbeat", {"ts": datetime.now(UTC).isoformat()}))
            except asyncio.CancelledError:
                return

        async def runner():
            try:
                from app.api.ai_report import _run_ai_report_job
                start = _time.monotonic()
                # AI raporu pahalı — off-thread'e at
                payload = await loop.run_in_executor(None, _run_ai_report_job, False)
                duration = _time.monotonic() - start
                await queue.put(("status", {
                    "status":      payload.get("status"),
                    "data_mode":   payload.get("data_mode"),
                    "duration_s":  round(duration, 2),
                }))
                ai = payload.get("ai_report") or {}
                narrative = ai.get("narrative") or ""
                # Cümle bazlı parçala
                chunks = _split_sentences(narrative)
                for c in chunks:
                    await queue.put(("chunk", {"text": c}))
                    await asyncio.sleep(0.08)
                # Anahtar sinyaller + verdict
                key_signals = ai.get("key_signals") or []
                if key_signals:
                    await queue.put(("key_signals", {"items": key_signals}))
                verdict = ai.get("verdict")
                if verdict:
                    await queue.put(("verdict", {"text": verdict}))
                await queue.put(("done", {
                    "confidence":  payload.get("confidence"),
                    "validation":  payload.get("validation"),
                    "finished_at": datetime.now(UTC).isoformat(),
                }))
            except Exception as exc:
                await queue.put(("error", {"error": str(exc)[:240]}))
            finally:
                await queue.put((None, None))

        hb_task = asyncio.create_task(heartbeat())
        run_task = asyncio.create_task(runner())
        try:
            while True:
                event, data = await queue.get()
                if event is None:
                    break
                yield _sse(event, data)
        finally:
            hb_task.cancel()
            run_task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


def _split_sentences(text: str) -> list[str]:
    """Çok ufak heuristic cümle bölücü — token akış hissi için yeterli."""
    if not text:
        return []
    import re
    parts = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÇĞİÖŞÜA-Z])", text.strip())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Çok uzun cümleyi virgülde ikiye ayır
        if len(p) > 240 and "," in p:
            sub = p.split(", ")
            buf = ""
            for s in sub:
                buf = (buf + ", " + s) if buf else s
                if len(buf) > 200:
                    out.append(buf)
                    buf = ""
            if buf:
                out.append(buf)
        else:
            out.append(p)
    return out


__all__ = ["router"]
