"""
FAZ 6 — Weekly Calibration JSONL kayıt servisi.

Fonksiyonlar:
  save_weekly_calibration(calibration: dict) -> str
  load_recent_weekly_calibrations(limit: int = 10) -> list[dict]

Güvenlik (her zaman zorlanır):
  decision_permission  = "NO_EXECUTION"
  execution_mode       = "PAPER_SAFE"
  auto_changes_allowed = False

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
    Path(__file__).resolve().parents[3] / "data" / "weekly_calibrations.jsonl"
)
_SCHEMA_VERSION = "weekly_calibration_v1"

_WRITE_LOCK = threading.Lock()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def save_weekly_calibration(calibration: dict[str, Any]) -> str:
    """
    Calibration raporunu weekly_calibrations.jsonl dosyasına ekler.

    Dönüş: calibration_id (UUID4 string)

    Güvenlik: decision_permission, execution_mode ve auto_changes_allowed
    her zaman zorlanır — dışarıdan gelen değerleri ezer.
    """
    _ensure_store_dir()

    calibration_id = calibration.get("calibration_id") or str(uuid.uuid4())

    record: dict[str, Any] = {
        "calibration_id":      calibration_id,
        "created_at":          calibration.get("created_at") or _utc_now_iso(),
        "schema_version":      _SCHEMA_VERSION,
        # Güvenlik sabitleri — dışarıdan gelenler ezilir
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "auto_changes_allowed": False,
        # Rapor meta
        "report_type":         calibration.get("report_type", "performance_learning_report"),
        "lookback_days":       calibration.get("lookback_days", 7),
        # Rapor içeriği
        "sample":              calibration.get("sample") or {},
        "performance":         calibration.get("performance") or {},
        "by_asset":            calibration.get("by_asset") or {},
        "by_label":            calibration.get("by_label") or {},
        "by_timeframe":        calibration.get("by_timeframe") or {},
        "by_regime":           calibration.get("by_regime") or {},
        "learning_signals":    calibration.get("learning_signals") or [],
        "auto_tune_candidates": calibration.get("auto_tune_candidates") or [],
        "risk_notes":          calibration.get("risk_notes") or [],
        "recommendations":     calibration.get("recommendations") or [],
    }

    line = json.dumps(record, ensure_ascii=False, default=str)

    with _WRITE_LOCK:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return calibration_id


def load_recent_weekly_calibrations(limit: int = 10) -> list[dict[str, Any]]:
    """
    JSONL dosyasından son `limit` calibration raporunu döndürür (read-only).

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
