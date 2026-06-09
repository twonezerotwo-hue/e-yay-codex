"""
FAZ 5A — Learning Candidate kayıt servisi.

Fonksiyonlar:
  save_learning_candidate(candidate: dict) -> str
  load_recent_learning_candidates(limit: int = 50) -> list[dict]

Güvenlik (her zaman zorlanır):
  decision_permission = "NO_EXECUTION"
  execution_mode      = "PAPER_SAFE"
  record_type         = "candidate"
  is_final            = False

Pozisyon açıkken kesin öğrenme kaydı yazılmaz; sadece aday kaydedilir.
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
    Path(__file__).resolve().parents[3] / "data" / "learning_candidates.jsonl"
)
_SCHEMA_VERSION = "learning_candidate_v1"

_WRITE_LOCK = threading.Lock()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def save_learning_candidate(candidate: dict[str, Any]) -> str:
    """
    Candidate dict'ini learning_candidates.jsonl dosyasına ekler.

    Dönüş: candidate_id (UUID4 string)

    Güvenlik: decision_permission, execution_mode, record_type ve is_final
    her zaman zorlanır — dışarıdan gelen değerleri ezer.
    """
    _ensure_store_dir()

    candidate_id = candidate.get("candidate_id") or str(uuid.uuid4())

    record: dict[str, Any] = {
        "candidate_id":        candidate_id,
        "created_at":          candidate.get("created_at") or _utc_now_iso(),
        "schema_version":      _SCHEMA_VERSION,
        # Güvenlik sabitleri — dışarıdan gelenler ezilir
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "record_type":         "candidate",
        "is_final":            False,
        # Position alanları
        "pair":                candidate.get("pair", ""),
        "side":                candidate.get("side", ""),
        "position_id":         candidate.get("position_id"),
        "entry_price":         candidate.get("entry_price", 0.0),
        "current_price":       candidate.get("current_price", 0.0),
        "pnl_pct":             candidate.get("pnl_pct", 0.0),
        # Kaynak + kanıt
        "source":              candidate.get("source") or {},
        "opening_evidence":    candidate.get("opening_evidence") or {},
        "current_evidence":    candidate.get("current_evidence") or {},
        # Adaylar + özet
        "candidate_labels":    candidate.get("candidate_labels") or [],
        "candidate_summary":   candidate.get("candidate_summary") or {},
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return candidate_id


def load_recent_learning_candidates(limit: int = 50) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` candidate'i döndürür (read-only).

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
