"""
FAZ 4 — Position Recheck kayıt servisi.

Fonksiyonlar:
  save_position_recheck(recheck: dict) -> str
  load_recent_position_rechecks(limit: int = 50) -> list[dict]

Güvenlik (her zaman zorlanır):
  decision_permission = "NO_EXECUTION"
  execution_mode      = "PAPER_SAFE"
  auto_action_allowed = False   ← summary içinde de zorlanır

JSONL append-only; thread-safe.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Sabitler ──────────────────────────────────────────────────────────────────

_STORE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "position_rechecks.jsonl"
)
_SCHEMA_VERSION = "position_recheck_v1"

_WRITE_LOCK = threading.Lock()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def save_position_recheck(recheck: dict[str, Any]) -> str:
    """
    Recheck dict'ini position_rechecks.jsonl dosyasına ekler.

    Dönüş: recheck_id (UUID4 string)

    Güvenlik: decision_permission, execution_mode ve summary.auto_action_allowed
    her zaman zorlanır — dışarıdan gelen değerleri ezdik.
    """
    _ensure_store_dir()

    recheck_id = recheck.get("recheck_id") or str(uuid.uuid4())

    # summary güvenlik zorlaması
    summary: dict[str, Any] = dict(recheck.get("summary") or {})
    summary["auto_action_allowed"] = False  # her zaman False

    record: dict[str, Any] = {
        "recheck_id":          recheck_id,
        "created_at":          recheck.get("created_at") or _utc_now_iso(),
        "schema_version":      _SCHEMA_VERSION,
        # Güvenlik sabitleri
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        # Position alanları
        "pair":                recheck.get("pair", ""),
        "side":                recheck.get("side", ""),
        "entry_price":         recheck.get("entry_price", 0.0),
        "current_price":       recheck.get("current_price", 0.0),
        "pnl_pct":             recheck.get("pnl_pct", 0.0),
        # Context
        "opening_context":     recheck.get("opening_context") or {},
        "current_context":     recheck.get("current_context") or {},
        # Checks + summary
        "checks":              recheck.get("checks") or [],
        "summary":             summary,
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return recheck_id


def load_recent_position_rechecks(limit: int = 50) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` recheck'i döndürür (read-only).

    Dosya yoksa boş liste döner.
    Bozuk satırlar sessizce atlanır.
    """
    if not _STORE_PATH.exists():
        return []

    records: list[dict[str, Any]] = []
    with _STORE_PATH.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

    return records[-limit:] if limit > 0 else records
