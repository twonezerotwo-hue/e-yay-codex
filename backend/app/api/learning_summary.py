"""
FAZ 8 — Learning Summary API.

Tek read-only endpoint:
  GET /learning/summary

Dört store'u bir araya getirir ve dashboard'a kompakt özet döndürür:
  latest_calibration  — en son weekly calibration özeti
  active_overrides    — auto_tune_overrides.json içindeki aktif koşullar
  latest_adjustment   — en son auto-tune adjustment kaydı
  latest_memory       — en son mistake memory kaydı
  safety              — güvenlik sabitleri (NO_EXECUTION / PAPER_SAFE)

Güvenlik:
  Read-only — hiçbir şey yazılmaz, değiştirilmez.
  Trade logic, paper trading ve auto-tune servisleri bu endpoint tarafından
  değiştirilmez.
  broker_permission = BROKER_NOT_CONNECTED
  live_execution_allowed = False
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.storage.auto_tune_store import load_recent_adjustments, read_overrides
from app.storage.mistake_memory_store import load_recent_mistake_memory
from app.storage.weekly_calibration_store import load_recent_weekly_calibrations

router = APIRouter(prefix="/learning", tags=["learning"])

# ── Güvenlik sabitleri ────────────────────────────────────────────────────────

_SAFETY = {
    "decision_permission":    "NO_EXECUTION",
    "execution_mode":         "PAPER_SAFE",
    "broker_permission":      "BROKER_NOT_CONNECTED",
    "live_execution_allowed": False,
    "override_scope":         "position_size_multiplier only (paper trading size modifier)",
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _build_calibration_summary(calibration: dict[str, Any]) -> dict[str, Any]:
    """Calibration dict'inden dashboard için minimal özet çıkar."""
    perf = calibration.get("performance") or {}
    sample = calibration.get("sample") or {}
    return {
        "calibration_id":  calibration.get("calibration_id"),
        "created_at":      calibration.get("created_at"),
        "lookback_days":   calibration.get("lookback_days"),
        "performance": {
            "win_rate":      perf.get("win_rate"),
            "profit_factor": perf.get("profit_factor"),
            "expectancy_usd": perf.get("expectancy_usd"),
        },
        "evidence_quality": sample.get("evidence_quality"),
    }


def _build_active_overrides(overrides: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Override dosyasından aktif koşulları listeler.
    position_size_multiplier koşullarını çıkarır.
    """
    overrides_map = overrides.get("overrides") or {}
    last_updated = overrides.get("updated_at")

    result: list[dict[str, Any]] = []
    for target, conditions in overrides_map.items():
        if not isinstance(conditions, dict):
            continue
        for condition, value in conditions.items():
            result.append({
                "target":       target,
                "condition":    condition,
                "value":        value,
                "last_updated": last_updated,
            })
    return result


def _build_adjustment_summary(adj: dict[str, Any]) -> dict[str, Any]:
    """Adjustment kaydından dashboard özeti çıkar."""
    return {
        "adjustment_id":         adj.get("adjustment_id"),
        "status":                adj.get("status"),
        "target":                adj.get("target"),
        "condition":             adj.get("condition"),
        "old_value":             adj.get("old_value"),
        "new_value":             adj.get("new_value"),
        "source_calibration_id": adj.get("source_calibration_id"),
        "created_at":            adj.get("created_at"),
    }


def _build_memory_summary(memory: dict[str, Any]) -> dict[str, Any]:
    """Mistake memory kaydından dashboard özeti çıkar."""
    trade = memory.get("trade") or {}
    final_summary = memory.get("final_summary") or {}
    final_labels_raw = memory.get("final_labels") or []
    # Sadece code string listesi — UI her label'ı ayrı ayrı göstermez
    label_codes = [
        lbl["code"]
        for lbl in final_labels_raw
        if isinstance(lbl, dict) and lbl.get("code")
    ]
    return {
        "memory_id":    memory.get("memory_id"),
        "pair":         trade.get("pair"),
        "result":       (trade.get("verdict") or "").upper(),
        "final_labels": label_codes,
        "main_lesson":  final_summary.get("main_lesson"),
        "created_at":   memory.get("created_at"),
    }


# ── Public endpoint ───────────────────────────────────────────────────────────

@router.get("/summary")
def get_learning_summary() -> dict[str, Any]:
    """
    Öğrenme sistemi özeti — read-only.

    Dört store'u birleştirip kompakt bir snapshot döndürür.
    Hiçbir şeyi değiştirmez.
    """
    # ── latest_calibration ────────────────────────────────────────────────────
    calibrations = load_recent_weekly_calibrations(limit=1)
    latest_calibration = (
        _build_calibration_summary(calibrations[0])
        if calibrations
        else None
    )

    # ── active_overrides ─────────────────────────────────────────────────────
    overrides = read_overrides()
    active_overrides = _build_active_overrides(overrides)

    # ── latest_adjustment ────────────────────────────────────────────────────
    adjustments = load_recent_adjustments(limit=1)
    latest_adjustment = (
        _build_adjustment_summary(adjustments[-1])
        if adjustments
        else None
    )

    # ── latest_memory ─────────────────────────────────────────────────────────
    memories = load_recent_mistake_memory(limit=1)
    latest_memory = (
        _build_memory_summary(memories[-1])
        if memories
        else None
    )

    return {
        "latest_calibration": latest_calibration,
        "active_overrides":   active_overrides,
        "latest_adjustment":  latest_adjustment,
        "latest_memory":      latest_memory,
        "safety":             _SAFETY,
    }
