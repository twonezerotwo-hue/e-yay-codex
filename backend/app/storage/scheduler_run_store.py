"""
FAZ 9 — Scheduler Run JSONL kayıt servisi.

Fonksiyonlar:
  save_scheduler_run(run: dict) -> str
  load_recent_scheduler_runs(limit: int = 20) -> list[dict]

Güvenlik (her zaman zorlanır):
  decision_permission    = "NO_EXECUTION"
  execution_mode         = "PAPER_SAFE"
  broker_permission      = "BROKER_NOT_CONNECTED"
  live_execution_allowed = False

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

_STORE_PATH: Path = (
    Path(__file__).resolve().parents[3] / "data" / "scheduler_runs.jsonl"
)
_SCHEMA_VERSION = "scheduler_run_v1"
_WRITE_LOCK = threading.Lock()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def save_scheduler_run(run: dict[str, Any]) -> str:
    """
    Scheduler run kaydını JSONL dosyasına ekler.

    Güvenlik sabitleri dışarıdan gelen değerleri ezer.
    Returns: run_id (UUID4 string)
    """
    _ensure_store_dir()

    run_id = run.get("run_id") or str(uuid.uuid4())

    record: dict[str, Any] = {
        "run_id":              run_id,
        "created_at":          run.get("created_at") or _utc_now_iso(),
        "schema_version":      _SCHEMA_VERSION,
        # Güvenlik sabitleri — her zaman zorlanır
        "decision_permission":    "NO_EXECUTION",
        "execution_mode":         "PAPER_SAFE",
        "broker_permission":      "BROKER_NOT_CONNECTED",
        "live_execution_allowed": False,
        # Çalışma içeriği
        "steps":   run.get("steps") or [],
        "summary": run.get("summary") or {},
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return run_id


def load_recent_scheduler_runs(limit: int = 20) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` run kaydını döndürür.

    limit=0 → tüm kayıtlar.
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
