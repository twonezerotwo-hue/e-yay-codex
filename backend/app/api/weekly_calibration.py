"""
FAZ 6 — Weekly Calibration API.

Endpoints:
  POST /weekly-calibration/build        → Calibration raporu üretir ve kaydeder.
  GET  /weekly-calibration/recent       → Son N raporu döndürür (read-only).

Güvenlik:
  PAPER_SAFE guard aktif.
  Paper trading state'ini mutate ETMEZ.
  auto_changes_allowed = False.
  auto_apply_now       = False (her zaman).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.execution_boundary import require_paper_safe
from app.services.weekly_calibration_service import build_weekly_calibration
from app.storage.learning_candidate_store import load_recent_learning_candidates
from app.storage.mistake_memory_store import load_recent_mistake_memory
from app.storage.position_recheck_store import load_recent_position_rechecks
from app.storage.weekly_calibration_store import (
    load_recent_weekly_calibrations,
    save_weekly_calibration,
)

router = APIRouter(prefix="/weekly-calibration", tags=["weekly-calibration"])


@router.post("/build", dependencies=[Depends(require_paper_safe)])
def build_calibration_report(lookback_days: int = 7) -> dict:
    """
    Son `lookback_days` günlük veriden calibration raporu üretir.

    • Paper trading state'ini değiştirmez.
    • Karar motorunu etkilemez.
    • auto_apply_now = False (her zaman).
    • lookback_days: 1–90 arası; varsayılan 7.
    """
    safe_lookback = max(1, min(lookback_days, 90))

    memories   = load_recent_mistake_memory(limit=0)
    candidates = load_recent_learning_candidates(limit=0)
    rechecks   = load_recent_position_rechecks(limit=500)

    calibration = build_weekly_calibration(
        memories=memories,
        candidates=candidates,
        rechecks=rechecks,
        lookback_days=safe_lookback,
    )

    if calibration.get("status") == "not_created":
        return calibration

    calibration_id = save_weekly_calibration(calibration)
    calibration["calibration_id"] = calibration_id
    return calibration


@router.get("/recent")
def get_recent_calibrations(limit: int = 10) -> dict:
    """Son N calibration raporunu döndürür (read-only)."""
    safe_limit = max(1, min(limit, 100))
    reports = load_recent_weekly_calibrations(limit=safe_limit)
    return {
        "status":  "ok",
        "count":   len(reports),
        "reports": reports,
    }
