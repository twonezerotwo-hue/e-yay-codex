"""
FAZ 2 — Agent hourly thesis kayıt servisi.

Fonksiyonlar:
  save_agent_thesis(thesis: dict) -> str
  load_recent_agent_theses(limit: int = 24) -> list[dict]

Güvenlik:
  decision_permission = "NO_EXECUTION"  (her zaman zorlanır)
  execution_mode      = "PAPER_SAFE"    (her zaman zorlanır)
  can_open_trade      = False           (her zaman zorlanır)

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
    Path(__file__).resolve().parents[3] / "data" / "agent_hourly_theses.jsonl"
)
_SCHEMA_VERSION = "agent_hourly_thesis_v1"

# Zorunlu üst-düzey alanlar
_REQUIRED_TOP_FIELDS = (
    "thesis_id",
    "created_at",
    "schema_version",
    "decision_permission",
    "execution_mode",
    "market_view",
    "asset_bias",
    "paper_trading_context",
)

_WRITE_LOCK = threading.Lock()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def save_agent_thesis(thesis: dict[str, Any]) -> str:
    """
    Thesis dict'ini agent_hourly_theses.jsonl dosyasına ekler.

    Dönüş: thesis_id (UUID4 string)

    Güvenlik: decision_permission, execution_mode, can_open_trade her zaman
    zorlanır — dışarıdan gelen değerleri ezdik.
    """
    _ensure_store_dir()

    thesis_id = thesis.get("thesis_id") or str(uuid.uuid4())

    # paper_trading_context güvenlik zorlaması
    ptc: dict[str, Any] = dict(thesis.get("paper_trading_context") or {})
    ptc["permission"] = "context_only"
    ptc["can_open_trade"] = False  # her zaman False

    record: dict[str, Any] = {
        "thesis_id":           thesis_id,
        "created_at":          thesis.get("created_at") or _utc_now_iso(),
        "schema_version":      _SCHEMA_VERSION,
        # Güvenlik sabitleri — dışarıdan gelen değerleri ezdik
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        # Thesis alanları
        "source_snapshot_ids":   thesis.get("source_snapshot_ids") or [],
        "lookback_hours":        thesis.get("lookback_hours", 0),
        "market_view":           thesis.get("market_view") or {},
        "asset_bias":            thesis.get("asset_bias") or {},
        "confirmation_health":   thesis.get("confirmation_health") or {},
        "strongest_reasons":     thesis.get("strongest_reasons") or [],
        "main_contradictions":   thesis.get("main_contradictions") or [],
        "watchlist":             thesis.get("watchlist") or [],
        "positions_under_review": thesis.get("positions_under_review") or [],
        "data_quality":          thesis.get("data_quality") or {"status": "unknown", "notes": []},
        "paper_trading_context": ptc,
        "thesis_sanity":         thesis.get("thesis_sanity") or {},
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return thesis_id


def load_recent_agent_theses(limit: int = 24) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` thesis'i döndürür (read-only).

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
