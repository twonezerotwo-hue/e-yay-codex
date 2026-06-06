"""
Alert Event Service — V1.

Thread-safe in-memory ring buffer (200 event).
Trading logic emits events via emit(); delivery (voice/Telegram) is separate.

Kurallar:
  • Trading mantığı emit() çağırır — delivery mekanizmaları bağımsız.
  • Telegram failure asla trading flow'u kesmez.
  • PAPER_SAFE / NO_EXECUTION — gerçek emir YOK.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any, Literal

AlertEventType = Literal[
    "pending_trade_created",
    "pending_trade_rejected",
    "paper_trade_opened",
    "paper_trade_closed",
    "market_closed_trade_blocked",
    "daily_loss_limit_warning",
    "agent_self_validation_failed",
    "paper_live_boundary_violation",
]

AlertLevel = Literal["CRITICAL", "ACTION_REQUIRED", "TRADE_EVENT", "WARNING", "INFO"]

# Ses uyarısı verilecek event türleri (spec v1)
VOICE_ALERT_TYPES: frozenset[str] = frozenset({
    "pending_trade_created",
    "paper_trade_opened",
    "paper_trade_closed",
    "market_closed_trade_blocked",
    "daily_loss_limit_warning",
    "agent_self_validation_failed",
    "paper_live_boundary_violation",
})

_RING: deque[dict[str, Any]] = deque(maxlen=200)
_LOCK = threading.Lock()
_COUNTER = 0


def emit(
    event_type: AlertEventType,
    level: AlertLevel,
    title: str,
    message: str,
    *,
    mode: str = "PAPER_SAFE",
    pair: str | None = None,
    side: str | None = None,
    size_usd: float | None = None,
    price: float | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Alert event oluştur ve ring buffer'a ekle. Telegram'a async ilet."""
    global _COUNTER
    with _LOCK:
        _COUNTER += 1
        event: dict[str, Any] = {
            "id":         _COUNTER,
            "uid":        str(uuid.uuid4()),
            "type":       event_type,
            "level":      level,
            "title":      title,
            "message":    message,
            "created_at": datetime.now(UTC).isoformat(),
            "mode":       mode,
            "pair":       pair,
            "side":       side,
            "size_usd":   size_usd,
            "price":      price,
            "reason":     reason,
            "metadata":   metadata or {},
            "voice":      event_type in VOICE_ALERT_TYPES,
        }
        _RING.append(event)

    _deliver_telegram_async(event)
    return event


def get_recent(limit: int = 50) -> list[dict[str, Any]]:
    """En son alert'leri yeni → eski sırasıyla döndür."""
    with _LOCK:
        items = list(_RING)
    items.reverse()
    return items[:max(1, min(limit, 200))]


def _deliver_telegram_async(event: dict[str, Any]) -> None:
    """Telegram'a fire-and-forget daemon thread ile gönder."""
    try:
        from app.services.telegram_alert_service import send_alert
        threading.Thread(target=send_alert, args=(event,), daemon=True).start()
    except Exception:
        pass  # import hatası da sessiz geçmeli


__all__ = ["emit", "get_recent", "VOICE_ALERT_TYPES", "AlertEventType", "AlertLevel"]
