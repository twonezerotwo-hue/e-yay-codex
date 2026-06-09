"""
FAZ 5B — Mistake Memory (Final) kayıt servisi.

Fonksiyonlar:
  save_mistake_memory(memory: dict) -> str
  load_recent_mistake_memory(limit: int = 50) -> list[dict]
  load_finalized_fingerprints() -> set[str]

Güvenlik (her zaman zorlanır):
  decision_permission = "NO_EXECUTION"
  execution_mode      = "PAPER_SAFE"
  record_type         = "final_memory"
  is_final            = True

Duplicate önleme:
  load_finalized_fingerprints() ile daha önce finalize edilmiş trade'ler tespit edilir.

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
    Path(__file__).resolve().parents[3] / "data" / "mistake_memory.jsonl"
)
_SCHEMA_VERSION = "mistake_memory_v1"

_WRITE_LOCK = threading.Lock()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def save_mistake_memory(memory: dict[str, Any]) -> str:
    """
    Final memory dict'ini mistake_memory.jsonl dosyasına ekler.

    Dönüş: memory_id (UUID4 string)

    Güvenlik: decision_permission, execution_mode, record_type ve is_final
    her zaman zorlanır — dışarıdan gelen değerleri ezer.
    """
    _ensure_store_dir()

    memory_id = memory.get("memory_id") or str(uuid.uuid4())

    record: dict[str, Any] = {
        "memory_id":               memory_id,
        "created_at":              memory.get("created_at") or _utc_now_iso(),
        "schema_version":          _SCHEMA_VERSION,
        # Güvenlik sabitleri — dışarıdan gelenler ezilir
        "decision_permission":     "NO_EXECUTION",
        "execution_mode":          "PAPER_SAFE",
        "record_type":             "final_memory",
        "is_final":                True,
        # Duplicate önleme anahtarı
        "source_trade_fingerprint": memory.get("source_trade_fingerprint", ""),
        # Trade özeti
        "trade":                   memory.get("trade") or {},
        # Kanıt
        "opening_context":         memory.get("opening_context") or {},
        "candidate_evidence":      memory.get("candidate_evidence") or {},
        "recheck_evidence":        memory.get("recheck_evidence") or {},
        # Final analiz
        "final_labels":            memory.get("final_labels") or [],
        "final_summary":           memory.get("final_summary") or {},
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return memory_id


def load_recent_mistake_memory(limit: int = 50) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` memory'yi döndürür (read-only).

    limit=0 → tüm kayıtlar döner.
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


def load_finalized_fingerprints() -> set[str]:
    """
    Daha önce finalize edilmiş trade fingerprint'lerini döndürür.

    Duplicate önleme için /finalize endpoint'inde kullanılır.
    """
    records = load_recent_mistake_memory(limit=0)
    return {
        r["source_trade_fingerprint"]
        for r in records
        if r.get("source_trade_fingerprint")
    }
