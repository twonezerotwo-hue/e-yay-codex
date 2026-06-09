"""
FAZ 7 — Auto Tune Store.

İki depolama mekanizması:
  auto_tune_adjustments.jsonl  — append-only adjustment log
  auto_tune_overrides.json     — mevcut parametre override'ları (okuma/yazma)

Fonksiyonlar:
  save_adjustment(adj: dict) -> str
  load_recent_adjustments(limit: int = 50) -> list[dict]
  load_last_applied_adjustment() -> dict | None
  read_overrides() -> dict
  write_overrides(overrides: dict) -> None

Güvenlik (her zaman zorlanır):
  decision_permission    = "NO_EXECUTION"
  execution_mode         = "PAPER_SAFE"
  broker_permission      = "BROKER_NOT_CONNECTED"
  live_execution_allowed = False

JSONL append-only; JSON atomic write; thread-safe.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Sabitler ──────────────────────────────────────────────────────────────────

_ADJ_STORE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "auto_tune_adjustments.jsonl"
)
_OVERRIDES_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "auto_tune_overrides.json"
)

_SCHEMA_ADJ      = "auto_tune_adjustment_v1"
_SCHEMA_OVERRIDES = "auto_tune_overrides_v1"

_WRITE_LOCK = threading.Lock()

# Boş overrides şablonu — her zaman güvenli sınırları zorlar
_OVERRIDES_TEMPLATE: dict[str, Any] = {
    "schema_version":        _SCHEMA_OVERRIDES,
    "decision_permission":   "NO_EXECUTION",
    "execution_mode":        "PAPER_SAFE",
    "broker_permission":     "BROKER_NOT_CONNECTED",
    "live_execution_allowed": False,
    "overrides":             {},
}


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_data_dir() -> None:
    _ADJ_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Adjustment JSONL ──────────────────────────────────────────────────────────

def save_adjustment(adj: dict[str, Any]) -> str:
    """
    Adjustment kaydını JSONL dosyasına ekler.

    Dönüş: adjustment_id (UUID4 string)

    Güvenlik sabitleri dışarıdan gelen değerleri ezer.
    """
    _ensure_data_dir()

    adj_id = adj.get("adjustment_id") or str(uuid.uuid4())

    record: dict[str, Any] = {
        "adjustment_id":        adj_id,
        "created_at":           adj.get("created_at") or _utc_now_iso(),
        "schema_version":       _SCHEMA_ADJ,
        # Güvenlik sabitleri — her zaman zorlanır
        "decision_permission":     "NO_EXECUTION",
        "execution_mode":          "PAPER_SAFE",
        "broker_permission":       "BROKER_NOT_CONNECTED",
        "live_execution_allowed":  False,
        # Kayıt içeriği
        "status":                  adj.get("status", "applied"),
        "target":                  adj.get("target", ""),
        "condition":               adj.get("condition", ""),
        "old_value":               adj.get("old_value"),
        "new_value":               adj.get("new_value"),
        "change":                  adj.get("change"),
        "source_calibration_id":   adj.get("source_calibration_id"),
        "rollback_available":      adj.get("rollback_available", True),
        # Rollback referansı (rollback kaydında kullanılır)
        "rollback_of_adjustment_id": adj.get("rollback_of_adjustment_id"),
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _ADJ_STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return adj_id


def load_recent_adjustments(limit: int = 50) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` adjustment'ı döndürür.

    limit=0 → tüm kayıtlar döner.
    Dosya yoksa boş liste döner.
    Bozuk satırlar sessizce atlanır.
    """
    if not _ADJ_STORE_PATH.exists():
        return []

    records: list[dict[str, Any]] = []
    with _ADJ_STORE_PATH.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

    return records[-limit:] if limit > 0 else records


def load_last_applied_adjustment() -> dict[str, Any] | None:
    """
    Henüz geri alınmamış en son 'applied' adjustment'ı döndürür.

    Rolled-back olan adjustment'lar hariç tutulur.
    Rollback yapılabilecek kayıt yoksa None döner.
    """
    records = load_recent_adjustments(limit=0)

    # Rolled-back kayıtların referans ettiği orijinal adjustment_id'leri
    rolled_back_ids: set[str] = {
        r["rollback_of_adjustment_id"]
        for r in records
        if r.get("status") == "rolled_back"
        and r.get("rollback_of_adjustment_id")
    }

    # En son applied kaydı bul (rolled-back olanları atla)
    for record in reversed(records):
        if (
            record.get("status") == "applied"
            and record.get("adjustment_id") not in rolled_back_ids
        ):
            return record

    return None


# ── Overrides JSON ────────────────────────────────────────────────────────────

def read_overrides() -> dict[str, Any]:
    """
    auto_tune_overrides.json dosyasını okur.

    Dosya yoksa ya da bozuksa güvenli varsayılan şablonu döner.
    """
    if not _OVERRIDES_PATH.exists():
        return {**_OVERRIDES_TEMPLATE, "overrides": {}}

    try:
        with _OVERRIDES_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Güvenlik alanlarını kontrol et
        data["decision_permission"]    = "NO_EXECUTION"
        data["execution_mode"]         = "PAPER_SAFE"
        data["broker_permission"]      = "BROKER_NOT_CONNECTED"
        data["live_execution_allowed"] = False
        return data
    except (json.JSONDecodeError, OSError):
        return {**_OVERRIDES_TEMPLATE, "overrides": {}}


def write_overrides(overrides: dict[str, Any]) -> None:
    """
    Overrides dict'ini auto_tune_overrides.json'a yazar.

    Güvenlik alanları her zaman zorlanır.
    Thread-safe.
    """
    _ensure_data_dir()

    # Güvenlik sabitleri — ezilir
    overrides["schema_version"]      = _SCHEMA_OVERRIDES
    overrides["decision_permission"]   = "NO_EXECUTION"
    overrides["execution_mode"]        = "PAPER_SAFE"
    overrides["broker_permission"]     = "BROKER_NOT_CONNECTED"
    overrides["live_execution_allowed"] = False
    overrides.setdefault("updated_at", _utc_now_iso())
    overrides.setdefault("overrides", {})

    serialized = json.dumps(overrides, ensure_ascii=False, default=str, indent=2)

    with _WRITE_LOCK:
        with _OVERRIDES_PATH.open("w", encoding="utf-8") as fh:
            fh.write(serialized)
