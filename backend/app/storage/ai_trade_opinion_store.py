"""
AI Trade Opinion kayıt servisi.

Fonksiyonlar:
  save_ai_trade_opinion(opinion: dict) -> str
  load_recent_ai_trade_opinions(limit: int = 24) -> list[dict]

Güvenlik:
  execution_mode        = "PAPER_SAFE"  (her zaman zorlanır)
  live_execution_allowed = False        (her zaman zorlanır)

JSONL append-only; thread-safe. Sadece fikir loglar — emir/pozisyon yok.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STORE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "ai_trade_opinions.jsonl"
)
_SCHEMA_VERSION = "ai_trade_opinion_v1"
_MAX_LIMIT = 200

_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def save_ai_trade_opinion(opinion: dict[str, Any]) -> str:
    """Opinion'ı JSONL'e ekler; güvenlik alanlarını zorlar. opinion_id döner."""
    record = dict(opinion)
    opinion_id = str(record.get("opinion_id") or uuid.uuid4())
    record["opinion_id"]             = opinion_id
    record["schema_version"]         = _SCHEMA_VERSION
    record["execution_mode"]         = "PAPER_SAFE"
    record["live_execution_allowed"] = False
    record.setdefault("generated_at", _utc_now_iso())

    line = json.dumps(record, ensure_ascii=False, default=str)
    with _lock:
        _ensure_store_dir()
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return opinion_id


def load_recent_ai_trade_opinions(limit: int = 24) -> list[dict[str, Any]]:
    """Son N opinion'ı (eski → yeni) döner. Bozuk satırlar atlanır."""
    limit = max(1, min(int(limit), _MAX_LIMIT))
    if not _STORE_PATH.exists():
        return []
    records: list[dict[str, Any]] = []
    with _lock, _STORE_PATH.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records[-limit:]


__all__ = ["load_recent_ai_trade_opinions", "save_ai_trade_opinion"]
