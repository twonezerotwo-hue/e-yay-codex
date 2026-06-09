"""
FAZ 4 — Position Recheck API.

Endpoints:
  POST /position-rechecks/run    → Tüm açık pozisyonlar için audit recheck üretir.
  GET  /position-rechecks/recent → Son N recheck'i döndürür (read-only).

Güvenlik:
  PAPER_SAFE guard aktif.
  Recheck state'i mutate ETMEZ — sadece recheck JSONL'e yazar.
  auto_action_allowed = False.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.execution_boundary import require_paper_safe
from app.services import paper_trading_service as pts
from app.services.agent_thesis_context import load_latest_safe_thesis
from app.services.position_recheck_service import build_position_recheck
from app.storage.hourly_snapshot_store import load_recent_hourly_snapshots
from app.storage.position_recheck_store import (
    load_recent_position_rechecks,
    save_position_recheck,
)

router = APIRouter(prefix="/position-rechecks", tags=["position-rechecks"])


@router.post("/run", dependencies=[Depends(require_paper_safe)])
def run_position_rechecks() -> dict:
    """
    Tüm açık pozisyonlar için audit-only recheck üretir ve kaydeder.

    • Paper trading state'ini değiştirmez.
    • Karar motorunu etkilemez.
    • auto_action_allowed = False (her recheck'te zorunlu).
    """
    # Gerçek açık pozisyonlar (current_price + pnl_pct dahil)
    snap_state = pts.get_snapshot()
    open_positions = snap_state.get("open_positions") or []

    # Gerçek son hourly snapshot
    hourly_snaps = load_recent_hourly_snapshots(limit=1)
    latest_snapshot = hourly_snaps[-1] if hourly_snaps else None

    # Gerçek son güvenli thesis
    latest_safe_thesis = load_latest_safe_thesis()

    results = []
    saved_count = 0
    skipped_count = 0

    for pos in open_positions:
        recheck = build_position_recheck(pos, latest_snapshot, latest_safe_thesis)
        if recheck.get("status") == "not_created":
            skipped_count += 1
            results.append({
                "pair":   recheck.get("pair"),
                "status": "not_created",
                "reason": recheck.get("reason"),
            })
            continue
        recheck_id = save_position_recheck(recheck)
        saved_count += 1
        results.append({
            "pair":               recheck.get("pair"),
            "side":               recheck.get("side"),
            "recheck_id":         recheck_id,
            "summary_status":     recheck["summary"]["status"],
            "recommended_action": recheck["summary"]["recommended_action"],
            "auto_action_allowed": False,
            "checks_count":       len(recheck.get("checks") or []),
        })

    return {
        "status":              "ok",
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "positions_checked":   len(open_positions),
        "saved_count":         saved_count,
        "skipped_count":       skipped_count,
        "snapshot_used":       bool(latest_snapshot),
        "thesis_used":         bool(latest_safe_thesis),
        "results":             results,
    }


@router.get("/recent")
def get_recent_rechecks(limit: int = 50) -> dict:
    """Son N position recheck'i döndürür (read-only)."""
    safe_limit = max(1, min(limit, 500))
    records = load_recent_position_rechecks(limit=safe_limit)
    return {
        "status":   "ok",
        "count":    len(records),
        "rechecks": records,
    }
