"""
Saatlik pipeline snapshot kayıt servisi.

FAZ 1: Kayıt altyapısı — scheduler/cron bu fazda YOK.
Çağıran taraf (ilerideki cron / POST endpoint) save_hourly_snapshot()'u çağırır.

Güvenlik:
  decision_permission = "NO_EXECUTION"   (her zaman zorlanır)
  execution_mode      = "PAPER_SAFE"     (her zaman zorlanır)
  Canlı broker entegrasyonu yok; gerçek emir gönderme yok.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Sabitler ──────────────────────────────────────────────────────────────────

_STORE_PATH = Path(__file__).resolve().parents[3] / "data" / "hourly_snapshots.jsonl"
_SCHEMA_VERSION = "hourly_snapshot_v1"

# Zorunlu üst-düzey alanlar — eksikse crash etme; data_quality.notes'a yaz.
_REQUIRED_TOP_FIELDS = (
    "report",
    "rotation",
    "mtf",
    "paper_trading",
    "data_quality",
)

# Thread-safe yazma kilidi
_WRITE_LOCK = threading.Lock()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _check_missing_fields(payload: dict[str, Any]) -> list[str]:
    """Hangi zorunlu alanlar eksik — liste döner (boş → tümü tamam)."""
    return [f for f in _REQUIRED_TOP_FIELDS if f not in payload or payload[f] is None]


# ── Public API ────────────────────────────────────────────────────────────────

def save_hourly_snapshot(payload: dict[str, Any]) -> str:
    """
    Pipeline snapshot'ını hourly_snapshots.jsonl dosyasına ekler.

    Dönüş: snapshot_id (UUID4 string)

    Güvenlik: decision_permission / execution_mode her zaman ZORLANIR.
    Eksik alan varsa crash etmez; data_quality.notes listesine yazar.
    """
    _ensure_store_dir()

    snapshot_id = str(uuid.uuid4())
    now_iso = _utc_now_iso()

    # Eksik alan kontrolü
    missing = _check_missing_fields(payload)

    # data_quality bloğunu güvenli şekilde al/oluştur
    dq: dict[str, Any] = dict(payload.get("data_quality") or {})
    if missing:
        notes: list[str] = list(dq.get("notes") or [])
        notes.append(f"missing_fields: {missing}")
        dq["notes"] = notes

    record: dict[str, Any] = {
        "snapshot_id":        snapshot_id,
        "created_at":         now_iso,
        "schema_version":     _SCHEMA_VERSION,
        # Güvenlik — dışarıdan gelen değerleri ezdik
        "decision_permission": "NO_EXECUTION",
        "execution_mode":     "PAPER_SAFE",
        # Payload alanları (None → boş dict)
        "report":         payload.get("report") or {},
        "rotation":       payload.get("rotation") or {},
        "mtf":            payload.get("mtf") or {},
        "paper_trading":  payload.get("paper_trading") or {},
        "data_quality":   dq,
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return snapshot_id


def load_recent_hourly_snapshots(limit: int = 24) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` snapshot'ı döndürür.

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
                # Bozuk satır — atla
                continue

    # Son N kayıt (en yeni sonda)
    return records[-limit:] if limit > 0 else records
