"""
FAZ 5A — Learning Candidate API.

Endpoints:
  POST /learning-candidates/run    → Açık pozisyonlar için audit candidate üretir.
  GET  /learning-candidates/recent → Son N candidate'i döndürür (read-only).

Güvenlik:
  PAPER_SAFE guard aktif.
  Paper trading state'ini mutate ETMEZ.
  is_final = False — pozisyon kapanmadan kesin öğrenme yazılmaz.
  auto_action_allowed = False.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.execution_boundary import require_paper_safe
from app.services import paper_trading_service as pts
from app.services.agent_thesis_context import load_latest_safe_thesis
from app.services.learning_candidate_service import build_learning_candidate
from app.storage.hourly_snapshot_store import load_recent_hourly_snapshots
from app.storage.learning_candidate_store import (
    load_recent_learning_candidates,
    save_learning_candidate,
)
from app.storage.position_recheck_store import load_recent_position_rechecks

router = APIRouter(prefix="/learning-candidates", tags=["learning-candidates"])


@router.post("/run", dependencies=[Depends(require_paper_safe)])
def run_learning_candidates() -> dict:
    """
    Tüm açık pozisyonlar için audit-only learning candidate üretir ve kaydeder.

    • Paper trading state'ini değiştirmez.
    • Karar motorunu etkilemez.
    • is_final = False — pozisyon kapanmadan kesin öğrenme yazılmaz.
    """
    snap_state     = pts.get_snapshot()
    open_positions = snap_state.get("open_positions") or []

    if not open_positions:
        return {
            "status":              "not_created",
            "reason":              "no_open_positions",
            "decision_permission": "NO_EXECUTION",
            "execution_mode":      "PAPER_SAFE",
            "is_final":            False,
        }

    # Gerçek veri kaynakları
    hourly_snaps   = load_recent_hourly_snapshots(limit=1)
    latest_snapshot = hourly_snaps[-1] if hourly_snaps else None
    latest_safe_thesis = load_latest_safe_thesis()

    # Pair başına en son recheck'i bul
    all_rechecks: list[dict] = load_recent_position_rechecks(limit=200)

    def _latest_recheck_for(pair: str) -> dict | None:
        matches = [r for r in all_rechecks if r.get("pair") == pair]
        return matches[-1] if matches else None

    candidate_ids: list[str] = []
    results: list[dict]      = []

    for pos in open_positions:
        pair   = str(pos.get("pair") or "").strip()
        latest_recheck = _latest_recheck_for(pair)

        candidate = build_learning_candidate(
            pos, latest_recheck, latest_snapshot, latest_safe_thesis
        )

        if candidate.get("status") == "not_created":
            results.append({
                "pair":   candidate.get("pair"),
                "status": "not_created",
                "reason": candidate.get("reason"),
            })
            continue

        candidate_id = save_learning_candidate(candidate)
        candidate_ids.append(candidate_id)
        results.append({
            "pair":            pair,
            "candidate_id":    candidate_id,
            "summary_status":  candidate["candidate_summary"]["status"],
            "labels_count":    len(candidate.get("candidate_labels") or []),
            "label_codes":     [lbl["code"] for lbl in (candidate.get("candidate_labels") or [])],
            "is_final":        False,
            "evidence_quality": (candidate.get("source") or {}).get("evidence_quality", "limited"),
        })

    return {
        "status":              "created",
        "count":               len(candidate_ids),
        "candidate_ids":       candidate_ids,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "is_final":            False,
        "results":             results,
    }


@router.get("/recent")
def get_recent_candidates(limit: int = 50) -> dict:
    """Son N learning candidate'i döndürür (read-only)."""
    safe_limit = max(1, min(limit, 500))
    records = load_recent_learning_candidates(limit=safe_limit)
    return {
        "status":     "ok",
        "count":      len(records),
        "candidates": records,
    }
