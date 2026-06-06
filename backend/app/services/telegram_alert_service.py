"""
Telegram Alert Delivery Service — V1.

Yalnızca delivery katmanı. Trading mantığı alert_event_service.emit() kullanır;
bu modül Telegram'a gönderimi üstlenir.

Gerekli env değişkenleri:
  TELEGRAM_BOT_TOKEN  — @BotFather'dan alınan bot token
  TELEGRAM_CHAT_ID    — Hedef chat/kanal ID'si

Eksikse: sessizce devre dışı.
Telegram hatası trading flow'u asla kesmez.
PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import os
from typing import Any

_BOT_TOKEN: str | None = os.environ.get("TELEGRAM_BOT_TOKEN")
_CHAT_ID: str | None = os.environ.get("TELEGRAM_CHAT_ID")

_LEVEL_EMOJI: dict[str, str] = {
    "CRITICAL":        "🔴",
    "ACTION_REQUIRED": "🟠",
    "TRADE_EVENT":     "🟡",
    "WARNING":         "⚠️",
    "INFO":            "ℹ️",
}


def is_configured() -> bool:
    return bool(_BOT_TOKEN and _CHAT_ID)


def get_status() -> dict[str, Any]:
    return {
        "enabled":  is_configured(),
        "chat_id":  _CHAT_ID if is_configured() else None,
    }


def send_alert(event: dict[str, Any]) -> None:
    """Alert'i Telegram'a gönder. Hata olursa sessiz geç — trading etkilenmez."""
    if not is_configured():
        return
    # INFO düzeyini varsayılan olarak atla (spec: Telegram gets all except optionally INFO)
    if event.get("level") == "INFO":
        return
    try:
        text = _format(event)
        _post(text)
    except Exception:
        pass


def _format(event: dict[str, Any]) -> str:
    level = event.get("level", "INFO")
    emoji = _LEVEL_EMOJI.get(level, "📢")
    lines: list[str] = [
        f"{emoji} <b>{event.get('title', '')}</b>",
        event.get("message", ""),
    ]
    if event.get("pair"):
        detail = f"Parite: {event['pair']}"
        if event.get("side"):
            detail += f" · {event['side']}"
        if event.get("price"):
            detail += f" @ ${event['price']:,.2f}"
        if event.get("size_usd"):
            detail += f" · ${event['size_usd']:,.0f}"
        lines.append(detail)
    if event.get("reason"):
        lines.append(f"Neden: {event['reason']}")
    lines.append(f"<code>[{event.get('mode', 'PAPER_SAFE')}]</code>")
    return "\n".join(lines)


def _post(text: str) -> None:
    import httpx  # already in requirements.txt
    httpx.post(
        f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
        json={"chat_id": _CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=5.0,
    )


__all__ = ["send_alert", "is_configured", "get_status"]
